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


class TestJitter:
    """Verify exponential backoff carries ±20% jitter to prevent thundering
    herd retries when multiple concurrent agents hit a 429 at once.

    research(2026-05): Anthropic's rate-limit guidance + AWS retry-pattern
    docs both recommend exponential backoff WITH jitter — without it, every
    caller that hit the 429 at the same instant retries at the same instant,
    re-overwhelming the upstream and turning a transient rate-limit into a
    sustained outage. Forge Party pipelines run 4-5 specialist agents
    concurrently, so this is a real (not theoretical) concern at kourai's
    operating point.

    Sources: tokencalculator.com Claude API rate limits 2026, fast.io AI
    Agent Retry Patterns 2026.
    """

    @pytest.mark.asyncio
    async def test_jitter_applied_to_exponential_backoff(self):
        """The computed exponential delay carries random jitter so two
        retries with the same attempt number don't sleep for the same
        wall-clock duration."""
        import httpx

        from kourai_common import retry as retry_mod

        captured_delays: list[float] = []

        async def _fake_sleep(delay: float) -> None:
            captured_delays.append(delay)

        @with_retry(max_attempts=3, base_delay=1.0)
        async def fn():
            raise httpx.ConnectError("refused")

        with (
            pytest.raises(httpx.ConnectError),
            __import__("unittest.mock", fromlist=["patch"]).patch.object(
                retry_mod.asyncio, "sleep", new=_fake_sleep
            ),
            __import__("unittest.mock", fromlist=["patch"]).patch.object(
                retry_mod.random, "uniform", side_effect=[0.85, 1.15]
            ),
        ):
            await fn()

        # Two retries before giving up (max_attempts=3 → 3 total attempts → 2 sleeps).
        # Without jitter both delays would equal 2.0 and 4.0 (base × 2^attempt
        # with attempt=1, 2). With ±20% jitter via mocked uniform(0.8, 1.2):
        #   attempt 1: 1.0 × 2^1 × 0.85 = 1.7
        #   attempt 2: 1.0 × 2^2 × 1.15 = 4.6
        assert len(captured_delays) == 2
        assert captured_delays[0] == pytest.approx(1.7)
        assert captured_delays[1] == pytest.approx(4.6)

    @pytest.mark.asyncio
    async def test_jitter_within_20_percent_band(self):
        """The jitter multiplier stays inside [0.8, 1.2] — bounded so the
        delay can't accidentally collapse to ~0 (re-overwhelming the
        upstream) nor inflate beyond reason."""
        import httpx

        from kourai_common import retry as retry_mod

        captured_jitters: list[tuple[float, float]] = []

        original_uniform = retry_mod.random.uniform

        def _capture_uniform(low: float, high: float) -> float:
            captured_jitters.append((low, high))
            return original_uniform(low, high)

        @with_retry(max_attempts=3, base_delay=0.001)  # tiny so test is fast
        async def fn():
            raise httpx.ConnectError("refused")

        with (
            pytest.raises(httpx.ConnectError),
            __import__("unittest.mock", fromlist=["patch"]).patch.object(
                retry_mod.random, "uniform", side_effect=_capture_uniform
            ),
        ):
            await fn()

        # Every uniform() call to compute jitter must request the
        # documented ±20% band — never a wider window that could over- or
        # under-shoot the intended de-correlation.
        assert all(low == 0.8 and high == 1.2 for low, high in captured_jitters), (
            f"jitter band drifted: {captured_jitters}"
        )

    @pytest.mark.asyncio
    async def test_api_provided_delay_not_jittered(self):
        """When the upstream sends 'Please retry in Xs', that's a
        deterministic instruction — applying jitter would either undershoot
        (re-overwhelming the upstream) or overshoot (wasted wall time).
        The current 0.5s buffer stays; jitter only applies to the
        exponential-backoff path where there's no server guidance."""

        from kourai_common import retry as retry_mod

        captured_delays: list[float] = []

        async def _fake_sleep(delay: float) -> None:
            captured_delays.append(delay)

        # Custom rate-limit exception class with the 'Please retry in Xs'
        # marker in its message (matches the _extract_retry_delay regex).
        class FakeRateLimit(Exception):
            pass

        attempt_count = 0

        @with_retry(
            max_attempts=2,
            base_delay=1.0,
            retryable_exceptions=(FakeRateLimit,),
        )
        async def fn():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise FakeRateLimit("RateLimitError: Please retry in 3.0s")
            return "ok"

        # uniform must NOT be called at all — the API path doesn't go
        # through the exponential branch. side_effect raising AssertionError
        # means any unexpected call surfaces immediately.
        def _unexpected_uniform(*args, **kwargs):
            raise AssertionError("random.uniform must not be called when API supplies a delay")

        with (
            __import__("unittest.mock", fromlist=["patch"]).patch.object(
                retry_mod.asyncio, "sleep", new=_fake_sleep
            ),
            __import__("unittest.mock", fromlist=["patch"]).patch.object(
                retry_mod.random, "uniform", side_effect=_unexpected_uniform
            ),
        ):
            result = await fn()

        assert result == "ok"
        # API-provided 3.0s + the 0.5s buffer = 3.5s, no jitter.
        assert captured_delays == [pytest.approx(3.5)]
