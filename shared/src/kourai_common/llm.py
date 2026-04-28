"""LiteLLM wrapper for model-agnostic LLM calls."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING, Any, cast

import httpx
import litellm

from kourai_common.config import AGENT_TIMEOUTS, get_model
from kourai_common.memory import (
    add_message,
    get_agent_state,
    get_max_unsummarized_idx,
    get_unsummarized_messages,
    mark_messages_summarized,
    save_agent_state,
)
from kourai_common.retry import with_retry
from kourai_common.usage import record_usage

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable, Callable, Mapping, Sequence

log = logging.getLogger(__name__)

# Suppress litellm's verbose logging
litellm.suppress_debug_info = True

WORKING_MEMORY_LIMIT = 5

# Anthropic prompt caching (see ROADMAP.md M4).
# LiteLLM forwards `cache_control` blocks to Anthropic / Gemini / Vertex and
# silently drops them on other providers, so the markers below are safe to
# emit unconditionally. Min cacheable prefix tokens (April 2026):
# Sonnet 4.6 = 2048, Opus 4.6 / 4.7 = 4096 — sub-threshold prefixes are
# silently ignored by Anthropic with no charge, so marking small prompts
# costs nothing.
_EPHEMERAL_CACHE: dict[str, str] = {"type": "ephemeral"}


class LLMError(Exception):
    """Base exception for LLM call failures."""


class LLMTimeoutError(LLMError):
    """Raised when an LLM call exceeds its timeout."""

    def __init__(self, agent_name: str, timeout: float):
        self.agent_name = agent_name
        self.timeout = timeout
        super().__init__(f"LLM call for {agent_name} timed out after {timeout:.0f}s")


class LLMResponseError(LLMError):
    """Raised when the LLM returns a malformed or empty response."""

    def __init__(self, agent_name: str, detail: str = ""):
        self.agent_name = agent_name
        super().__init__(f"LLM response error for {agent_name}: {detail}")


@with_retry(
    max_attempts=4,
    base_delay=2.0,
    retryable_exceptions=(
        TimeoutError,
        httpx.ConnectError,
        httpx.TimeoutException,
        litellm.exceptions.RateLimitError,
        litellm.exceptions.InternalServerError,
        litellm.exceptions.APIConnectionError,
        litellm.exceptions.Timeout,
    ),
)
async def _execute_completion(timeout_seconds: float, **kwargs: Any) -> Any:
    """Execute acompletion with built-in retries for capacity/network issues."""
    # Route all requests through a proxy when configured (e.g. litellm mock in tests).
    # Without this, litellm routes anthropic/ models directly to the Anthropic API,
    # bypassing OPENAI_API_BASE entirely.
    # For Ollama, OLLAMA_API_BASE overrides the default http://localhost:11434.
    api_base = os.getenv("OPENAI_API_BASE")
    if not api_base and kwargs.get("model", "").startswith("ollama/"):
        api_base = os.getenv("OLLAMA_API_BASE")
    if api_base and "api_base" not in kwargs:
        kwargs["api_base"] = api_base
    # Belt-and-braces with the asyncio.timeout below: ``request_timeout`` is
    # what propagates into LiteLLM's underlying httpx/aiohttp transport, so a
    # stuck TCP connect actually surfaces as a Timeout instead of a hanging
    # task that asyncio.timeout has to forcibly cancel. The wrapper stays as
    # the outer guard for cases where the transport itself doesn't honor the
    # deadline (older aiohttp versions had bugs around this).
    kwargs.setdefault("request_timeout", timeout_seconds)
    async with asyncio.timeout(timeout_seconds):
        return await litellm.acompletion(**kwargs)


async def _manage_memory(context_id: str, agent_name: str, *, force: bool = False) -> int:
    """Progressively summarize older messages to maintain a lean working memory.

    Returns the count of messages folded into the semantic summary on this
    call (0 if nothing was eligible). When ``force=True``, the
    ``WORKING_MEMORY_LIMIT`` threshold is bypassed so the player-triggered
    ``/compact`` slash command can consolidate even short conversations.
    The "keep the last 2 unsummarized for immediate context fluidity" rule
    holds either way.
    """
    unsummarized = get_unsummarized_messages(context_id, agent_name)
    if not (force or len(unsummarized) > WORKING_MEMORY_LIMIT):
        return 0
    if len(unsummarized) <= 2:
        return 0
    # Keep the last 2 unsummarized (to maintain immediate context fluidity)
    to_summarize = unsummarized[:-2]
    max_idx = get_max_unsummarized_idx(context_id, agent_name) - 2

    state = get_agent_state(context_id, agent_name)

    # Build prompt for summarization
    text_to_summarize = "\n".join([f"{msg['role']}: {msg['content']}" for msg in to_summarize])
    prompt = (
        "Summarize the following conversation snippet concisely. "
        "Focus on the user's intent, the agent's decisions, and any code/files modified. "
        "If there is an existing summary, integrate this new information into it.\n\n"
    )
    if state["semantic_summary"]:
        prompt += f"Existing Summary:\n{state['semantic_summary']}\n\n"
    prompt += f"New Conversation to Incorporate:\n{text_to_summarize}"

    try:
        # We use the same model but could theoretically use a cheaper/faster one
        model = get_model(agent_name)
        response = await _execute_completion(
            timeout_seconds=60.0,
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a memory condensation module.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        new_summary = response.choices[0].message.content
        if new_summary:
            state["semantic_summary"] = new_summary
            save_agent_state(context_id, agent_name, state)
            mark_messages_summarized(context_id, agent_name, max_idx)
            log.info(
                "Summarized %d messages for %s in %s",
                len(to_summarize),
                agent_name,
                context_id,
            )
            return len(to_summarize)
    except Exception as e:  # pragma: no cover
        log.warning("Failed to summarize memory for %s: %s", agent_name, e)
    return 0


async def compact_memory(context_id: str, agent_name: str) -> int:
    """Public wrapper: force a player-triggered compaction for one agent.

    Always runs regardless of ``WORKING_MEMORY_LIMIT``; returns the count
    of messages folded into the semantic summary. Used by the CLI's
    ``/compact`` slash command which iterates every agent that has
    history under the current ``context_id`` and totals the counts for a
    Mneme comms-window report.
    """
    return await _manage_memory(context_id, agent_name, force=True)


def _mark_system_cacheable(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert a string-content system message into one cache-marked text block.

    No-op when there is no leading system message or when the system content is
    already a structured list (caller has already chosen its breakpoints).
    """
    if not messages or messages[0].get("role") != "system":
        return messages
    sys = messages[0]
    content = sys.get("content")
    if not isinstance(content, str):
        return messages
    new_sys = {
        **sys,
        "content": [{"type": "text", "text": content, "cache_control": _EPHEMERAL_CACHE}],
    }
    return [new_sys, *messages[1:]]


def _mark_first_user_cacheable(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark the first user message as a cache breakpoint.

    Used inside chat_with_tools so the [system + tools + initial-user] prefix
    is cached once and reused across every iteration of the agentic loop. For
    multimodal user content (text + images), the marker attaches to the last
    text block — Anthropic only accepts cache_control on text blocks.
    """
    out = list(messages)
    for i, msg in enumerate(out):
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            out[i] = {
                **msg,
                "content": [
                    {"type": "text", "text": content, "cache_control": _EPHEMERAL_CACHE},
                ],
            }
        elif isinstance(content, list):
            new_content = list(content)
            for j in range(len(new_content) - 1, -1, -1):
                block = new_content[j]
                # ty narrows the list element type unhelpfully through the
                # isinstance, so .get("type") trips invalid-argument-type
                # even though the runtime is fine.
                if isinstance(block, dict) and block.get("type") == "text":  # ty: ignore[invalid-argument-type]
                    new_content[j] = {**block, "cache_control": _EPHEMERAL_CACHE}
                    break
            out[i] = {**msg, "content": new_content}
        return out
    return out


def _mark_last_tool_cacheable(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark cache_control on the final tool's function dict.

    Per Anthropic's spec the marker on the last tool caches the entire tool
    array as one prefix block, so we get tool caching with a single annotation.
    """
    if not tools:
        return tools
    last = tools[-1]
    fn = last.get("function") if isinstance(last, dict) else None
    if not isinstance(fn, dict) or "cache_control" in fn:
        return tools
    out = list(tools)
    out[-1] = {**last, "function": {**fn, "cache_control": _EPHEMERAL_CACHE}}
    return out


def _log_cache_usage(agent_name: str, response: Any) -> None:
    """Debug-log cache read/write tokens from a LiteLLM response.usage.

    Silent when usage is missing or the cached/written counts are not real
    ints (so MagicMock-based unit tests don't trip false log lines).
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    cached = 0
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        val = getattr(details, "cached_tokens", None)
        if isinstance(val, int):
            cached = val
    written_val = getattr(usage, "cache_creation_input_tokens", None)
    written = written_val if isinstance(written_val, int) else 0
    if cached or written:
        log.debug("cache %s read=%d write=%d", agent_name, cached, written)


async def _build_contextual_messages(
    agent_name: str, messages: Sequence[dict[str, Any]], context_id: str | None
) -> list[dict[str, Any]]:
    full_messages = list(messages)
    if not context_id:
        return full_messages

    # Trigger background memory janitor (we await it here to ensure context is updated,
    # but could be detached)
    await _manage_memory(context_id, agent_name)

    # 1. Fetch State (Semantic Memory)
    state = get_agent_state(context_id, agent_name)

    # 2. Inject Semantic Summary into System Prompt
    if state["semantic_summary"] and full_messages and full_messages[0]["role"] == "system":
        original_system = full_messages[0]["content"]
        injected_system = (
            f"{original_system}\n\n"
            "=== SEMANTIC MEMORY (PREVIOUS CONTEXT) ===\n"
            f"{state['semantic_summary']}"
        )
        full_messages[0]["content"] = injected_system

    # 3. Inject Working Memory (Only Unsummarized Recent Messages)
    recent_history = get_unsummarized_messages(context_id, agent_name)
    if recent_history:
        insert_idx = 1 if full_messages and full_messages[0]["role"] == "system" else 0
        full_messages[insert_idx:insert_idx] = recent_history

    # 4. Save the new user message to Episodic Memory
    if full_messages and full_messages[-1]["role"] == "user":
        add_message(context_id, agent_name, "user", full_messages[-1]["content"])

    return full_messages


async def chat(
    agent_name: str,
    messages: Sequence[dict[str, Any]],
    temperature: float = 0.3,
    max_tokens: int = 4096,
    context_id: str | None = None,
    tier: str | None = None,
) -> str:
    """Send a chat completion request and return the response text.

    ``tier`` overrides the env-set ``KOURAI_MODEL_TIER`` for this single
    call — pass ``"cheap"`` to pin a quick auxiliary call to the cheap
    tier even when the active pipeline is on smart/standard. Used by
    Metis's M14 ``discuss_tradeoffs`` so the parallel discussion runs
    on Haiku regardless of pipeline tier (saves ongoing token spend on
    every tier-1 confirmation where the discussion is dropped silently).
    """
    model = get_model(agent_name, tier=tier)
    timeout = AGENT_TIMEOUTS.get(agent_name, 120.0)

    full_messages = await _build_contextual_messages(agent_name, messages, context_id)
    full_messages = _mark_system_cacheable(full_messages)

    log.debug("LLM call: %s -> %s (%d messages)", agent_name, model, len(full_messages))

    try:
        response = await _execute_completion(
            timeout_seconds=timeout,
            model=model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except TimeoutError:
        raise LLMTimeoutError(agent_name, timeout) from None

    _log_cache_usage(agent_name, response)
    record_usage(agent_name, response, model=model)
    content = response.choices[0].message.content
    if not content:
        raise LLMResponseError(agent_name, "empty response")

    if context_id:
        add_message(context_id, agent_name, "assistant", content)

    return content


def _coerce_chunk_content(content: object) -> str:
    """Normalize provider-specific content payloads to plain text."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = cast("dict[str, Any]", item).get("text")
                if isinstance(text, str):
                    parts.append(text)
            else:
                text = getattr(item, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)

    if isinstance(content, dict):
        content_dict = cast("dict[str, Any]", content)
        text = content_dict.get("text")
        if isinstance(text, str):
            return text
        nested_content = content_dict.get("content")
        if nested_content is not None:
            return _coerce_chunk_content(nested_content)

    text = getattr(content, "text", None)
    if isinstance(text, str):
        return text

    return ""


def _extract_stream_chunk_text(chunk: object) -> str:
    """Extract text from a streamed chunk across provider/proxy payload formats."""
    choices = getattr(chunk, "choices", None)
    if not isinstance(choices, list) or not choices:
        return ""

    choice = choices[0]
    delta = getattr(choice, "delta", None)
    delta_text = _coerce_chunk_content(getattr(delta, "content", None))
    if delta_text:
        return delta_text

    message = getattr(choice, "message", None)
    message_text = _coerce_chunk_content(getattr(message, "content", None))
    if message_text:
        return message_text

    return _coerce_chunk_content(getattr(choice, "text", None))


async def chat_stream(
    agent_name: str,
    messages: Sequence[dict[str, Any]],
    temperature: float = 0.3,
    max_tokens: int = 4096,
    context_id: str | None = None,
    tier: str | None = None,
) -> AsyncIterable[str]:
    """Stream a chat completion, yielding text chunks.

    ``tier`` overrides the env-set ``KOURAI_MODEL_TIER`` for this single
    streaming call — same semantics as ``chat()``. Symmetrical kwarg
    so callers don't have to switch APIs to pin a tier.
    """
    model = get_model(agent_name, tier=tier)
    timeout = AGENT_TIMEOUTS.get(agent_name, 120.0)

    full_messages = await _build_contextual_messages(agent_name, messages, context_id)
    full_messages = _mark_system_cacheable(full_messages)

    log.debug("LLM stream: %s -> %s (%d messages)", agent_name, model, len(full_messages))

    try:
        response = await _execute_completion(
            timeout_seconds=timeout,
            model=model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
    except TimeoutError:
        raise LLMTimeoutError(agent_name, timeout) from None

    full_response = []
    async for chunk in response:
        chunk_text = _extract_stream_chunk_text(chunk)
        if chunk_text:
            full_response.append(chunk_text)
            yield chunk_text

    if not full_response:
        log.warning(
            "LLM stream for %s yielded no text chunks; retrying without streaming",
            agent_name,
        )
        fallback_response = await _execute_completion(
            timeout_seconds=timeout,
            model=model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        fallback_content = _coerce_chunk_content(fallback_response.choices[0].message.content)
        if not fallback_content:
            raise LLMResponseError(agent_name, "empty streamed response")
        full_response.append(fallback_content)
        yield fallback_content

    if context_id:
        add_message(context_id, agent_name, "assistant", "".join(full_response))


def _normalize_tool_calls(message: Any) -> list[dict[str, Any]]:
    """Extract OpenAI-style tool_calls from a LiteLLM message, regardless of source provider."""
    raw_calls = getattr(message, "tool_calls", None) or []
    normalized: list[dict[str, Any]] = []
    for tc in raw_calls:
        tc_id = getattr(tc, "id", None) or (tc.get("id") if isinstance(tc, dict) else None)
        fn = getattr(tc, "function", None) or (tc.get("function") if isinstance(tc, dict) else None)
        if fn is None:
            continue
        name = getattr(fn, "name", None) or (fn.get("name") if isinstance(fn, dict) else None)
        args = getattr(fn, "arguments", None)
        if args is None and isinstance(fn, dict):
            args = fn.get("arguments")
        if not name:
            continue
        normalized.append({"id": tc_id, "name": name, "arguments": args or "{}"})
    return normalized


async def chat_with_tools(
    agent_name: str,
    messages: Sequence[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_handlers: Mapping[str, Callable[..., Awaitable[str]]],
    *,
    handler_context: dict[str, Any] | None = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    max_iters: int = 10,
    context_id: str | None = None,
    on_tool_call: Callable[[str, dict[str, Any], str], Awaitable[None]] | None = None,
    tier: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Drive an agentic tool-use loop until the model stops calling tools.

    Returns (final_assistant_text, tool_call_log). Each log entry is
    ``{"name": str, "args": dict, "result": str}``. ``handler_context`` is
    merged into every handler call as keyword arguments and takes precedence
    over model-supplied args (so the model can't override server-trusted
    values like ``project_root``).

    ``tier`` overrides the env-set ``KOURAI_MODEL_TIER`` for this single
    tool loop — same semantics as ``chat()``. Symmetrical kwarg so a
    future caller can pin (e.g.) a low-stakes lint-fix loop to cheap.
    """
    model = get_model(agent_name, tier=tier)
    timeout = AGENT_TIMEOUTS.get(agent_name, 120.0)

    working_messages = await _build_contextual_messages(agent_name, messages, context_id)
    working_messages = _mark_system_cacheable(working_messages)
    working_messages = _mark_first_user_cacheable(working_messages)
    cached_tools = _mark_last_tool_cacheable(tools)
    handler_ctx = handler_context or {}
    tool_call_log: list[dict[str, Any]] = []
    final_text = ""
    finished_cleanly = False

    for iteration in range(max_iters):
        log.debug(
            "LLM tool loop %s iter=%d (%d messages, %d tools)",
            agent_name,
            iteration,
            len(working_messages),
            len(cached_tools),
        )
        try:
            response = await _execute_completion(
                timeout_seconds=timeout,
                model=model,
                messages=working_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=cached_tools,
                tool_choice="auto",
            )
        except TimeoutError:
            raise LLMTimeoutError(agent_name, timeout) from None

        _log_cache_usage(agent_name, response)
        record_usage(agent_name, response, model=model)
        choice = response.choices[0]
        message = choice.message
        text_content = _coerce_chunk_content(getattr(message, "content", None))
        normalized = _normalize_tool_calls(message)

        if text_content:
            final_text = text_content

        if not normalized:
            finished_cleanly = True
            break

        working_messages.append(
            {
                "role": "assistant",
                "content": text_content,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    for tc in normalized
                ],
            }
        )

        for tc in normalized:
            name = tc["name"]
            raw_args = tc["arguments"]
            args: dict[str, Any]
            result: str
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                args = {}
                result = f"ERROR: invalid tool arguments: {exc}"
            else:
                handler = tool_handlers.get(name)
                if handler is None:
                    result = f"ERROR: unknown tool {name!r}"
                else:
                    try:
                        result = await handler(**{**args, **handler_ctx})
                    except Exception as exc:
                        log.warning("Tool %s failed for %s: %s", name, agent_name, exc)
                        result = f"ERROR: {type(exc).__name__}: {exc}"

            log.debug("tool_use %s args=%s result=%s", name, args, result[:200])
            working_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                }
            )
            tool_call_log.append({"name": name, "args": args, "result": result})

            if on_tool_call is not None:
                await on_tool_call(name, args, result)

    if not finished_cleanly:
        log.warning(
            "chat_with_tools for %s hit max_iters=%d before model stopped calling tools",
            agent_name,
            max_iters,
        )

    if context_id and final_text:
        add_message(context_id, agent_name, "assistant", final_text)

    return final_text, tool_call_log
