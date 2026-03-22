"""LiteLLM wrapper for model-agnostic LLM calls."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

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
    from collections.abc import AsyncIterable, Sequence

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
        except Exception as e:
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
        delta = chunk.choices[0].delta
        if delta and delta.content:
            full_response.append(delta.content)
            yield delta.content

    if context_id:
        add_message(context_id, agent_name, "assistant", "".join(full_response))
