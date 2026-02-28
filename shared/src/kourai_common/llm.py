"""LiteLLM wrapper for model-agnostic LLM calls."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterable

import litellm

from kourai_common.config import get_model

log = logging.getLogger(__name__)

# Suppress litellm's verbose logging
litellm.suppress_debug_info = True


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
    """
    model = get_model(agent_name)
    log.debug(f"LLM call: {agent_name} -> {model} ({len(messages)} messages)")

    response = await litellm.acompletion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


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
    """
    model = get_model(agent_name)
    log.debug(f"LLM stream: {agent_name} -> {model} ({len(messages)} messages)")

    response = await litellm.acompletion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    async for chunk in response:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content
