"""LiteLLM wrapper for model-agnostic LLM calls."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterable

import litellm

from kourai_common.config import AGENT_TIMEOUTS, get_model

log = logging.getLogger(__name__)

# Suppress litellm's verbose logging
litellm.suppress_debug_info = True


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


async def chat(
    agent_name: str,
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    """Send a chat completion request and return the response text.

    Args:
        agent_name: Agent name used to resolve the model ID.
        messages: List of message dicts with "role" and "content" keys.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens in the response.

    Returns:
        The assistant's response text.

    Raises:
        LLMTimeoutError: If the call exceeds the agent's configured timeout.
        LLMResponseError: If the response is empty or malformed.
    """
    model = get_model(agent_name)
    timeout = AGENT_TIMEOUTS.get(agent_name, 120.0)
    log.debug(f"LLM call: {agent_name} -> {model} ({len(messages)} messages)")

    try:
        response = await asyncio.wait_for(
            litellm.acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        raise LLMTimeoutError(agent_name, timeout)

    content = response.choices[0].message.content
    if not content:
        raise LLMResponseError(agent_name, "empty response")
    return content


async def chat_stream(
    agent_name: str,
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> AsyncIterable[str]:
    """Stream a chat completion, yielding text chunks.

    Args:
        agent_name: Agent name used to resolve the model ID.
        messages: List of message dicts with "role" and "content" keys.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens in the response.

    Yields:
        Text chunks as they arrive from the LLM.

    Raises:
        LLMTimeoutError: If the initial connection exceeds the agent's timeout.
    """
    model = get_model(agent_name)
    timeout = AGENT_TIMEOUTS.get(agent_name, 120.0)
    log.debug(f"LLM stream: {agent_name} -> {model} ({len(messages)} messages)")

    try:
        response = await asyncio.wait_for(
            litellm.acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        raise LLMTimeoutError(agent_name, timeout)

    async for chunk in response:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content
