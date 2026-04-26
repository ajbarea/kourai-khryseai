"""Per-session token usage accumulator + April 2026 pricing constants.

Surfaces what every ``chat()`` / ``chat_with_tools()`` call costs so
the CLI's ``/usage`` slash command can show a per-agent breakdown
during long pipelines. Tests cover:

- ``record_usage`` accumulates real int counts and silently skips
  MagicMock attribute access (so unit-tested call sites can't
  inflate session totals with sentinel objects).
- The accumulator is per-agent and survives across calls.
- ``compute_cost`` matches the published per-million-token rates
  for every model in :data:`ANTHROPIC_PRICING` and returns ``None``
  for unknown models so the CLI can render ``$ — `` instead of an
  inflated zero.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from kourai_common.pricing import ANTHROPIC_PRICING, ModelPricing, compute_cost, get_model_pricing
from kourai_common.usage import (
    AgentUsage,
    record_usage,
    reset_session_usage,
)


@pytest.fixture(autouse=True)
def _isolate_session_usage():
    """Reset the module-level accumulator before AND after every test.

    Tests run in arbitrary order; without isolation a record_usage call
    in one test can bleed totals into a later assertion. The teardown
    pass keeps the autouse module clean for any non-usage test that
    happens to import the module.
    """
    reset_session_usage()
    yield
    reset_session_usage()


def _fake_response(
    *,
    prompt_tokens=0,
    completion_tokens=0,
    cache_creation_input_tokens=0,
    cached_tokens=0,
):
    """Build a minimal LiteLLM-shaped response for ``record_usage`` to read."""
    details = SimpleNamespace(cached_tokens=cached_tokens)
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        prompt_tokens_details=details,
    )
    return SimpleNamespace(usage=usage)


# ---------------------------------------------------------------------------
# record_usage — accumulator behavior
# ---------------------------------------------------------------------------


class TestRecordUsage:
    def test_first_call_creates_bucket_with_real_counts(self):
        from kourai_common.usage import get_session_usage

        record_usage(
            "techne",
            _fake_response(
                prompt_tokens=1500,
                completion_tokens=400,
                cached_tokens=900,
                cache_creation_input_tokens=200,
            ),
            model="anthropic/claude-sonnet-4-6",
        )

        bucket = get_session_usage().agents["techne"]
        assert bucket.input_tokens == 1500
        assert bucket.output_tokens == 400
        assert bucket.cache_read_tokens == 900
        assert bucket.cache_write_tokens == 200
        assert bucket.calls == 1
        assert bucket.model == "anthropic/claude-sonnet-4-6"

    def test_subsequent_calls_accumulate(self):
        from kourai_common.usage import get_session_usage

        for _ in range(3):
            record_usage(
                "kallos",
                _fake_response(prompt_tokens=100, completion_tokens=50),
                model="anthropic/claude-haiku-4-5-20251001",
            )

        bucket = get_session_usage().agents["kallos"]
        assert bucket.calls == 3
        assert bucket.input_tokens == 300
        assert bucket.output_tokens == 150

    def test_per_agent_isolation(self):
        from kourai_common.usage import get_session_usage

        record_usage(
            "techne",
            _fake_response(prompt_tokens=1000, completion_tokens=200),
            model="anthropic/claude-sonnet-4-6",
        )
        record_usage(
            "kallos",
            _fake_response(prompt_tokens=500, completion_tokens=100),
            model="anthropic/claude-haiku-4-5-20251001",
        )

        agents = get_session_usage().agents
        assert agents["techne"].input_tokens == 1000
        assert agents["kallos"].input_tokens == 500
        assert agents["techne"].model != agents["kallos"].model

    def test_first_model_wins_per_agent(self):
        from kourai_common.usage import get_session_usage

        record_usage(
            "techne",
            _fake_response(prompt_tokens=100),
            model="anthropic/claude-sonnet-4-6",
        )
        # Second call passes a different model id (e.g. tier swap mid-session) —
        # the existing bucket keeps its first model so the cost row stays
        # attributable. Mixed-model agents are out of scope.
        record_usage(
            "techne",
            _fake_response(prompt_tokens=50),
            model="anthropic/claude-opus-4-7",
        )
        assert get_session_usage().agents["techne"].model == "anthropic/claude-sonnet-4-6"

    def test_no_usage_attr_is_silent_noop(self):
        from kourai_common.usage import get_session_usage

        record_usage("techne", SimpleNamespace(), model="anthropic/claude-sonnet-4-6")
        assert "techne" not in get_session_usage().agents

    def test_all_zero_counts_does_not_create_bucket(self):
        from kourai_common.usage import get_session_usage

        record_usage("techne", _fake_response(), model="anthropic/claude-sonnet-4-6")
        assert "techne" not in get_session_usage().agents

    def test_magicmock_counts_are_silently_dropped(self):
        from unittest.mock import MagicMock

        from kourai_common.usage import get_session_usage

        # MagicMock attribute access returns a Mock that's truthy and not int.
        # The counter must not coerce it to a sentinel — otherwise unit tests
        # that mock out the LLM response would inflate session totals.
        record_usage("techne", MagicMock(), model="anthropic/claude-sonnet-4-6")
        assert "techne" not in get_session_usage().agents


# ---------------------------------------------------------------------------
# pricing — table sanity + compute_cost math
# ---------------------------------------------------------------------------


class TestPricingTable:
    def test_every_entry_has_5x_output_to_input_ratio(self):
        # Anthropic's tier-uniform 5x output-to-input ratio is the load-bearing
        # invariant of the pricing table. If a future minor breaks it, we
        # want a loud test failure, not a silent under-quote.
        for model_id, rates in ANTHROPIC_PRICING.items():
            assert rates.output_per_m == pytest.approx(rates.input_per_m * 5.0), (
                f"{model_id}: output rate is not 5x input"
            )

    def test_cache_read_is_one_tenth_input(self):
        for model_id, rates in ANTHROPIC_PRICING.items():
            assert rates.cache_read_per_m == pytest.approx(rates.input_per_m * 0.1), (
                f"{model_id}: cache_read rate is not 0.1x input"
            )

    def test_cache_write_5min_is_125_percent_input(self):
        for model_id, rates in ANTHROPIC_PRICING.items():
            assert rates.cache_write_5min_per_m == pytest.approx(rates.input_per_m * 1.25), (
                f"{model_id}: 5-min cache write is not 1.25x input"
            )

    def test_known_april_2026_rates(self):
        """Spot-check the absolute USD values against published rates."""
        haiku = ANTHROPIC_PRICING["anthropic/claude-haiku-4-5-20251001"]
        sonnet = ANTHROPIC_PRICING["anthropic/claude-sonnet-4-6"]
        opus = ANTHROPIC_PRICING["anthropic/claude-opus-4-7"]
        assert (haiku.input_per_m, haiku.output_per_m) == (1.0, 5.0)
        assert (sonnet.input_per_m, sonnet.output_per_m) == (3.0, 15.0)
        assert (opus.input_per_m, opus.output_per_m) == (5.0, 25.0)


class TestGetModelPricing:
    def test_known_model_returns_rates(self):
        rates = get_model_pricing("anthropic/claude-sonnet-4-6")
        assert isinstance(rates, ModelPricing)
        assert rates.input_per_m == 3.0

    def test_unknown_model_returns_none(self):
        assert get_model_pricing("ollama/llama3.3:70b") is None
        assert get_model_pricing("gemini/gemini-2.5-pro") is None
        assert get_model_pricing("") is None


class TestComputeCost:
    def test_input_only_cost_matches_rate(self):
        usage = AgentUsage(
            model="anthropic/claude-sonnet-4-6",
            input_tokens=1_000_000,
        )
        cost = compute_cost("anthropic/claude-sonnet-4-6", usage)
        assert cost == pytest.approx(3.0)

    def test_full_cost_combines_all_four_rates(self):
        # 1M input → $3 + 1M output → $15 + 1M cache_read → $0.30
        # + 1M cache_write_5min → $3.75 = $22.05
        usage = AgentUsage(
            model="anthropic/claude-sonnet-4-6",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cache_read_tokens=1_000_000,
            cache_write_tokens=1_000_000,
        )
        cost = compute_cost("anthropic/claude-sonnet-4-6", usage)
        assert cost == pytest.approx(3.0 + 15.0 + 0.30 + 3.75)

    def test_partial_million_pro_rates(self):
        # 250K input on Haiku → 0.25 * $1 = $0.25
        usage = AgentUsage(model="anthropic/claude-haiku-4-5-20251001", input_tokens=250_000)
        cost = compute_cost("anthropic/claude-haiku-4-5-20251001", usage)
        assert cost == pytest.approx(0.25)

    def test_unknown_model_returns_none(self):
        usage = AgentUsage(model="ollama/llama3.3:70b", input_tokens=999_999_999)
        assert compute_cost("ollama/llama3.3:70b", usage) is None

    def test_zero_usage_is_zero_cost(self):
        usage = AgentUsage(model="anthropic/claude-opus-4-7")
        assert compute_cost("anthropic/claude-opus-4-7", usage) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# /usage slash command — end-to-end formatter behavior
# ---------------------------------------------------------------------------


class TestUsageSlashCommand:
    """The CLI helper composes record_usage state into a printable summary.

    ``_echo`` writes to a pre-patch_stdout reference captured at module
    import time, so plain ``capsys`` only catches it when this file
    runs in isolation. When the full suite runs and an earlier test
    has already called ``set_raw_out`` (or anything else mutated the
    cached reference), output bypasses capsys silently. We patch
    ``_echo`` directly into a list to stay deterministic regardless
    of run order.
    """

    @staticmethod
    def _patch_echo(mp):
        captured: list[str] = []

        def fake_echo(text: str = "", nl: bool = True) -> None:
            captured.append(text)

        mp.setattr("hosts.cli.__main__._echo", fake_echo)
        return captured

    def test_empty_usage_prints_no_records_line(self, monkeypatch):
        from hosts.cli.__main__ import _show_usage_summary

        captured = self._patch_echo(monkeypatch)
        _show_usage_summary()
        out = "\n".join(captured)
        assert "No usage recorded" in out

    def test_summary_includes_per_agent_breakdown_and_total(self, monkeypatch):
        from hosts.cli.__main__ import _show_usage_summary

        record_usage(
            "techne",
            _fake_response(prompt_tokens=2_000_000, completion_tokens=400_000),
            model="anthropic/claude-sonnet-4-6",
        )
        record_usage(
            "kallos",
            _fake_response(prompt_tokens=500_000, completion_tokens=100_000),
            model="anthropic/claude-haiku-4-5-20251001",
        )

        captured = self._patch_echo(monkeypatch)
        _show_usage_summary()
        out = "\n".join(captured)

        # Per-agent rows must appear with the model-specific cost.
        # techne: 2M*3 + 0.4M*15 = 6 + 6 = $12.0000
        # kallos: 0.5M*1 + 0.1M*5 = 0.5 + 0.5 = $1.0000
        assert "techne" in out
        assert "kallos" in out
        assert "12.0000" in out
        assert "1.0000" in out
        # Total line
        assert "TOTAL" in out
        assert "13.0000" in out  # 12.0 + 1.0

    def test_unknown_model_renders_dash_and_explains(self, monkeypatch):
        from hosts.cli.__main__ import _show_usage_summary

        record_usage(
            "experimental",
            _fake_response(prompt_tokens=500_000, completion_tokens=100_000),
            model="gemini/gemini-2.5-pro",
        )

        captured = self._patch_echo(monkeypatch)
        _show_usage_summary()
        out = "\n".join(captured)
        assert "experimental" in out
        # Dollar sign with em-dash placeholder, not a dollar amount.
        assert "$—" in out
        # Explanatory hint pointing at the pricing table.
        assert "kourai_common.pricing" in out
