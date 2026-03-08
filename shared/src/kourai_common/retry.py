"""Retry utilities with exponential backoff for A2A and LLM calls."""

from __future__ import annotations

import asyncio
import logging
import re
from functools import wraps
from typing import Any

import httpx

log = logging.getLogger(__name__)


def _extract_retry_delay(exc: Exception) -> float | None:
    """Attempt to extract a specific retry delay from an exception message."""
    msg = str(exc)
    match = re.search(r"Please retry in ([\d\.]+)s", msg)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: tuple[type[Exception], ...] = (
        httpx.ConnectError,
        httpx.TimeoutException,
    ),
) -> Any:
    """Decorator for retrying async calls on transient failures.

    Rate limits (429 / RateLimitError) get extra retries (up to 3x max_attempts)
    using the API's requested delay when present.

    Args:
        max_attempts: Maximum number of attempts for normal transient errors.
        base_delay: Base delay in seconds (doubles each attempt).
        retryable_exceptions: Exception types that trigger a retry.
    """

    def decorator(fn: Any) -> Any:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            attempt = 0

            max_rate_limit_attempts = max_attempts * 3

            while True:
                try:
                    return await fn(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exc = e
                    exc_name = type(e).__name__

                    # Detect if it is a capacity/quota rate limit error
                    is_rate_limit = "RateLimit" in exc_name or "429" in str(e)

                    attempt += 1
                    if is_rate_limit:
                        if attempt >= max_rate_limit_attempts:
                            raise last_exc from e
                    elif attempt >= max_attempts:
                        raise last_exc from e

                    requested_delay = _extract_retry_delay(e)
                    if requested_delay is not None:
                        delay = requested_delay + 0.5  # Add a small 500ms buffer
                        log.warning(
                            "%s hit rate limit, API requested wait of %.1fs. "
                            "Pausing until quota refreshes...",
                            fn.__name__, delay,
                        )
                    else:
                        # Cap exponential backoff at a reasonable max (e.g. ~64s) for rate limits
                        exp_attempt = min(attempt, 6) if is_rate_limit else attempt
                        delay = base_delay * (2**exp_attempt)
                        log.warning(
                            "%s failed (attempt %d), retrying in %.1fs: %s",
                            fn.__name__, attempt + 1, delay, exc_name,
                        )

                    await asyncio.sleep(delay)

        return wrapper

    return decorator
