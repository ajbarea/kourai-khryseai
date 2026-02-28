"""Retry utilities with exponential backoff for A2A and LLM calls."""

from __future__ import annotations

import asyncio
import logging
from functools import wraps
from typing import Any

import httpx

log = logging.getLogger(__name__)


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: tuple[type[Exception], ...] = (
        httpx.ConnectError,
        httpx.TimeoutException,
    ),
) -> Any:
    """Decorator for retrying async calls on transient failures.

    Args:
        max_attempts: Maximum number of attempts before giving up.
        base_delay: Base delay in seconds (doubles each attempt).
        retryable_exceptions: Exception types that trigger a retry.
    """
    def decorator(fn: Any) -> Any:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(max_attempts):
                try:
                    return await fn(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exc = e
                    delay = base_delay * (2 ** attempt)
                    log.warning(
                        f"{fn.__name__} failed (attempt {attempt + 1}/{max_attempts}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator
