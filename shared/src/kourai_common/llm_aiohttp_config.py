"""LiteLLM aiohttp configuration for concurrent streaming.

Addresses M14 parallel timeout: tuned TCPConnector pool + streaming timeout disabled.
Based on May 2026 best practices from LiteLLM and Anthropic API docs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


def create_aiohttp_session() -> aiohttp.ClientSession:
    """Create optimized ClientSession for concurrent LLM streaming.

    Configuration addresses two issues:
    1. M14 parallel timeout: TCPConnector pool sized for concurrent requests
       Per LiteLLM best practice (May 2026), use limit_per_host=75 to handle
       multiple simultaneous streams to the same API endpoint without pool
       contention. Baseline aiohttp defaults (limit_per_host=10) cause timeouts
       when 2+ concurrent requests contend for slots.

    2. SSE stream timeout: Request timeout disabled for streaming responses
       Per Anthropic API docs (May 2026), SSE streams must not timeout
       mid-body. Timeout clock starts before pool.acquire() completes
       (aiohttp issue #10313), so `request_timeout` must be None or
       streams will abort while waiting for chunks.

    Returns:
        ClientSession configured for reliable concurrent streaming.
    """
    connector = aiohttp.TCPConnector(
        limit=300,  # Total concurrent connections (per LiteLLM docs)
        limit_per_host=75,  # Per-host limit (default 10 was too restrictive for M14)
        ttl_dns_cache=300,
        ssl=True,  # Use default SSL context
    )

    # No request_timeout here; will be set per-call in _execute_completion()
    # to None for streaming, finite for non-streaming.
    session = aiohttp.ClientSession(connector=connector)

    log.info(
        f"Created optimized aiohttp.ClientSession: "
        f"limit={connector._limit}, limit_per_host={connector._limit_per_host}"
    )

    return session


# Global session instance (singleton per process)
_global_session: aiohttp.ClientSession | None = None


def get_aiohttp_session() -> aiohttp.ClientSession:
    """Get or create the global aiohttp session.

    Lazily initializes on first call. Ensures all LiteLLM calls through
    _execute_completion() share the same tuned connector pool.
    """
    global _global_session
    if _global_session is None:
        _global_session = create_aiohttp_session()
    return _global_session


async def close_aiohttp_session() -> None:
    """Close the global session (called on shutdown)."""
    global _global_session
    if _global_session is not None:
        await _global_session.close()
        _global_session = None
        log.info("Closed global aiohttp.ClientSession")
