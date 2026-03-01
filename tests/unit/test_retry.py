"""Retry decorator: exponential backoff on transient failures."""

from __future__ import annotations

import pytest

from kourai_common.retry import with_retry


class TestWithRetry:
    """Retry decorator behavior."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self):
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await fn()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_transient_error(self):
        import httpx

        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("refused")
            return "recovered"

        result = await fn()
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self):
        import httpx

        @with_retry(max_attempts=2, base_delay=0.01)
        async def fn():
            raise httpx.TimeoutException("timeout")

        with pytest.raises(httpx.TimeoutException):
            await fn()

    @pytest.mark.asyncio
    async def test_non_retryable_error_raises_immediately(self):
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def fn():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            await fn()

        assert call_count == 1
