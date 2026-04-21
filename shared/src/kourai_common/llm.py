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

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable, Callable, Sequence

log = logging.getLogger(__name__)

# Suppress litellm's verbose logging
litellm.suppress_debug_info = True

WORKING_MEMORY_LIMIT = 5


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
    async with asyncio.timeout(timeout_seconds):
        return await litellm.acompletion(**kwargs)


async def _manage_memory(context_id: str, agent_name: str) -> None:
    """Progressively summarize older messages to maintain a lean working memory."""
    unsummarized = get_unsummarized_messages(context_id, agent_name)
    if len(unsummarized) > WORKING_MEMORY_LIMIT:
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
        except Exception as e:  # pragma: no cover
            log.warning("Failed to summarize memory for %s: %s", agent_name, e)


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
) -> str:
    """Send a chat completion request and return the response text."""
    model = get_model(agent_name)
    timeout = AGENT_TIMEOUTS.get(agent_name, 120.0)

    full_messages = await _build_contextual_messages(agent_name, messages, context_id)

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
) -> AsyncIterable[str]:
    """Stream a chat completion, yielding text chunks."""
    model = get_model(agent_name)
    timeout = AGENT_TIMEOUTS.get(agent_name, 120.0)

    full_messages = await _build_contextual_messages(agent_name, messages, context_id)

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
    tool_handlers: dict[str, Callable[..., Awaitable[str]]],
    *,
    handler_context: dict[str, Any] | None = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    max_iters: int = 10,
    context_id: str | None = None,
    on_tool_call: Callable[[str, dict[str, Any], str], Awaitable[None]] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Drive an agentic tool-use loop until the model stops calling tools.

    Returns (final_assistant_text, tool_call_log). Each log entry is
    ``{"name": str, "args": dict, "result": str}``. ``handler_context`` is
    merged into every handler call as keyword arguments and takes precedence
    over model-supplied args (so the model can't override server-trusted
    values like ``project_root``).
    """
    model = get_model(agent_name)
    timeout = AGENT_TIMEOUTS.get(agent_name, 120.0)

    working_messages = await _build_contextual_messages(agent_name, messages, context_id)
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
            len(tools),
        )
        try:
            response = await _execute_completion(
                timeout_seconds=timeout,
                model=model,
                messages=working_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice="auto",
            )
        except TimeoutError:
            raise LLMTimeoutError(agent_name, timeout) from None

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
