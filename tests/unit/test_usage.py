"""Per-session token usage accumulator + pricing constants.

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

from kourai_common.pricing import (
    ANTHROPIC_PRICING,
    GEMINI_PRICING,
    ModelPricing,
    compute_cost,
    get_model_pricing,
)
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
    ephemeral_5m_input_tokens=None,
    ephemeral_1h_input_tokens=None,
):
    """Build a minimal LiteLLM-shaped response for ``record_usage`` to read.

    Pass ``ephemeral_5m_input_tokens`` / ``ephemeral_1h_input_tokens`` (or
    both) to populate the per-TTL breakdown sub-object Anthropic emits on
    mixed-TTL requests. When neither is provided, the response carries no
    ``cache_creation`` attribute — matching pre-#178 single-TTL responses.
    """
    details = SimpleNamespace(cached_tokens=cached_tokens)
    fields = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cache_creation_input_tokens": cache_creation_input_tokens,
        "prompt_tokens_details": details,
    }
    if ephemeral_5m_input_tokens is not None or ephemeral_1h_input_tokens is not None:
        fields["cache_creation"] = SimpleNamespace(
            ephemeral_5m_input_tokens=ephemeral_5m_input_tokens or 0,
            ephemeral_1h_input_tokens=ephemeral_1h_input_tokens or 0,
        )
    usage = SimpleNamespace(**fields)
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

        bucket = get_session_usage().agents[("techne", "anthropic/claude-sonnet-4-6")]
        assert bucket.input_tokens == 1500
        assert bucket.output_tokens == 400
        assert bucket.cache_read_tokens == 900
        # No per-TTL breakdown supplied → entire write attributed to the
        # safe-default 5m bucket (rather than over-billing at 1h rate).
        assert bucket.cache_write_5m_tokens == 200
        assert bucket.cache_write_1h_tokens == 0
        assert bucket.cache_write_tokens == 200  # property: sum
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

        bucket = get_session_usage().agents[("kallos", "anthropic/claude-haiku-4-5-20251001")]
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
        assert agents[("techne", "anthropic/claude-sonnet-4-6")].input_tokens == 1000
        assert agents[("kallos", "anthropic/claude-haiku-4-5-20251001")].input_tokens == 500

    def test_per_agent_per_model_keying(self):
        # M14 cheap-tier override means the same agent can ride two
        # models in one session: discuss_tradeoffs on Haiku, create_spec
        # on Opus. Both rows must stack — no first-wins masking.
        from kourai_common.usage import get_session_usage

        record_usage(
            "metis",
            _fake_response(prompt_tokens=200, completion_tokens=80),
            model="anthropic/claude-haiku-4-5-20251001",  # discussion
        )
        record_usage(
            "metis",
            _fake_response(prompt_tokens=2000, completion_tokens=4000),
            model="anthropic/claude-opus-4-7",  # spec
        )

        agents = get_session_usage().agents
        haiku_row = agents[("metis", "anthropic/claude-haiku-4-5-20251001")]
        opus_row = agents[("metis", "anthropic/claude-opus-4-7")]
        # Haiku totals stay distinct from Opus totals — no masking.
        assert haiku_row.input_tokens == 200
        assert opus_row.input_tokens == 2000
        # Both rows have the right model id for their cost calc.
        assert haiku_row.model == "anthropic/claude-haiku-4-5-20251001"
        assert opus_row.model == "anthropic/claude-opus-4-7"

    def test_no_usage_attr_is_silent_noop(self):
        from kourai_common.usage import get_session_usage

        record_usage("techne", SimpleNamespace(), model="anthropic/claude-sonnet-4-6")
        assert ("techne", "anthropic/claude-sonnet-4-6") not in get_session_usage().agents

    def test_all_zero_counts_does_not_create_bucket(self):
        from kourai_common.usage import get_session_usage

        record_usage("techne", _fake_response(), model="anthropic/claude-sonnet-4-6")
        assert ("techne", "anthropic/claude-sonnet-4-6") not in get_session_usage().agents

    def test_magicmock_counts_are_silently_dropped(self):
        from unittest.mock import MagicMock

        from kourai_common.usage import get_session_usage

        # MagicMock attribute access returns a Mock that's truthy and not int.
        # The counter must not coerce it to a sentinel — otherwise unit tests
        # that mock out the LLM response would inflate session totals.
        record_usage("techne", MagicMock(), model="anthropic/claude-sonnet-4-6")
        assert ("techne", "anthropic/claude-sonnet-4-6") not in get_session_usage().agents

    def test_per_ttl_cache_write_breakdown_extracted_when_present(self):
        """When the response carries usage.cache_creation with the 5m/1h
        sub-fields (Anthropic mixed-TTL requests post-#178), record_usage
        must split into the two buckets — not lump everything as 5m."""
        from kourai_common.usage import get_session_usage

        record_usage(
            "metis",
            _fake_response(
                prompt_tokens=2048,
                completion_tokens=503,
                cached_tokens=1800,
                cache_creation_input_tokens=556,  # legacy total = 5m + 1h
                ephemeral_5m_input_tokens=456,
                ephemeral_1h_input_tokens=100,
            ),
            model="anthropic/claude-opus-4-7",
        )
        bucket = get_session_usage().agents[("metis", "anthropic/claude-opus-4-7")]
        assert bucket.cache_write_5m_tokens == 456
        assert bucket.cache_write_1h_tokens == 100
        assert bucket.cache_write_tokens == 556  # property invariant

    def test_per_ttl_breakdown_accumulates_across_calls(self):
        """Both the 5m and 1h buckets must accumulate independently across
        repeated calls so /usage shows per-TTL totals over a session."""
        from kourai_common.usage import get_session_usage

        for _ in range(3):
            record_usage(
                "techne",
                _fake_response(
                    cache_creation_input_tokens=100,
                    ephemeral_5m_input_tokens=80,
                    ephemeral_1h_input_tokens=20,
                ),
                model="anthropic/claude-sonnet-4-6",
            )
        bucket = get_session_usage().agents[("techne", "anthropic/claude-sonnet-4-6")]
        assert bucket.cache_write_5m_tokens == 240  # 80 × 3
        assert bucket.cache_write_1h_tokens == 60  # 20 × 3
        assert bucket.cache_write_tokens == 300

    def test_legacy_total_only_attributes_to_5m_bucket(self):
        """When the response has cache_creation_input_tokens but no
        breakdown sub-object (older provider responses, streaming edge
        cases, non-Anthropic providers), attribute the entire total to
        the 5m bucket — under-quotes 1h writes by ~60% but never
        over-bills, which is the safer default."""
        from kourai_common.usage import get_session_usage

        record_usage(
            "kallos",
            _fake_response(cache_creation_input_tokens=500),  # no per-TTL sub-object
            model="anthropic/claude-haiku-4-5-20251001",
        )
        bucket = get_session_usage().agents[("kallos", "anthropic/claude-haiku-4-5-20251001")]
        assert bucket.cache_write_5m_tokens == 500
        assert bucket.cache_write_1h_tokens == 0


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

    def test_cache_write_1h_is_2x_input(self):
        # Anthropic May 2026 docs: 1-hour cache write costs 2× base input.
        # #178 upgraded the static system block to ttl="1h" so this rate
        # is what kourai's truly-static 1-3K-token prefix is billed at on
        # every cache rewrite (which now happens once per hour rather than
        # once per 5 minutes — net cost win).
        for model_id, rates in ANTHROPIC_PRICING.items():
            assert rates.cache_write_1h_per_m == pytest.approx(rates.input_per_m * 2.0), (
                f"{model_id}: 1-hour cache write is not 2x input"
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
    def test_known_anthropic_model_returns_rates(self):
        rates = get_model_pricing("anthropic/claude-sonnet-4-6")
        assert isinstance(rates, ModelPricing)
        assert rates.input_per_m == 3.0

    def test_known_gemini_model_returns_rates(self):
        # Both Anthropic and Gemini live in the unified lookup table.
        rates = get_model_pricing("gemini/gemini-2.5-pro")
        assert isinstance(rates, ModelPricing)
        assert rates.input_per_m == 1.25

    def test_unknown_model_returns_none(self):
        # Ollama models are local / free; we deliberately don't price them.
        assert get_model_pricing("ollama/llama3.3:70b") is None
        # An unrecognised provider id returns None — the CLI falls back
        # to the "$—" rendering plus the footer hint.
        assert get_model_pricing("openai/gpt-5") is None
        assert get_model_pricing("") is None


class TestGeminiPricing:
    """Gemini rates have to be spot-checked individually — output-to-input
    ratio is not tier-uniform like Anthropic (Flash 4x, Pro 8x)."""

    def test_2_0_flash_rates(self):
        rates = GEMINI_PRICING["gemini/gemini-2.0-flash"]
        assert (rates.input_per_m, rates.output_per_m) == (0.10, 0.40)

    def test_2_5_pro_rates(self):
        rates = GEMINI_PRICING["gemini/gemini-2.5-pro"]
        # Under-200K context tier — most agent calls fit.
        assert (rates.input_per_m, rates.output_per_m) == (1.25, 10.0)

    def test_cache_read_is_one_tenth_input(self):
        # The 0.1x cache-read multiplier holds across providers.
        for model_id, rates in GEMINI_PRICING.items():
            assert rates.cache_read_per_m == pytest.approx(rates.input_per_m * 0.1), (
                f"{model_id}: cache_read rate is not 0.1x input"
            )

    def test_cache_write_left_at_zero_intentionally(self):
        # Gemini's caching is per-hour storage, not per-write — neither
        # the 5m nor the 1h rate fits the shape, so both are 0. Documents
        # the under-count rather than guessing a per-write rate.
        for model_id, rates in GEMINI_PRICING.items():
            assert rates.cache_write_5min_per_m == 0.0, (
                f"{model_id}: cache_write_5min should be 0 (Gemini billing model)"
            )
            assert rates.cache_write_1h_per_m == 0.0, (
                f"{model_id}: cache_write_1h should be 0 (Gemini billing model)"
            )


class TestComputeCost:
    def test_input_only_cost_matches_rate(self):
        usage = AgentUsage(
            model="anthropic/claude-sonnet-4-6",
            input_tokens=1_000_000,
        )
        cost = compute_cost("anthropic/claude-sonnet-4-6", usage)
        assert cost == pytest.approx(3.0)

    def test_full_cost_combines_all_five_rates(self):
        # 1M input → $3 + 1M output → $15 + 1M cache_read → $0.30
        # + 1M cache_write_5m → $3.75 + 1M cache_write_1h → $6.0 = $28.05
        usage = AgentUsage(
            model="anthropic/claude-sonnet-4-6",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cache_read_tokens=1_000_000,
            cache_write_5m_tokens=1_000_000,
            cache_write_1h_tokens=1_000_000,
        )
        cost = compute_cost("anthropic/claude-sonnet-4-6", usage)
        assert cost == pytest.approx(3.0 + 15.0 + 0.30 + 3.75 + 6.0)

    def test_1h_cache_write_billed_at_2x_input(self):
        # 1M cache_write_1h at Sonnet's $3 input → $6 (2× input).
        # Pre-#178 the same M tokens would have been billed at the 5m
        # rate ($3.75) — under-quote of 60% on the 1h-static portion.
        usage = AgentUsage(
            model="anthropic/claude-sonnet-4-6",
            cache_write_1h_tokens=1_000_000,
        )
        cost = compute_cost("anthropic/claude-sonnet-4-6", usage)
        assert cost == pytest.approx(6.0)

    def test_5m_and_1h_priced_independently(self):
        # 500K cache_write_5m on Opus → 0.5 × $6.25 = $3.125
        # 500K cache_write_1h on Opus → 0.5 × $10 = $5.00
        # = $8.125 combined
        usage = AgentUsage(
            model="anthropic/claude-opus-4-7",
            cache_write_5m_tokens=500_000,
            cache_write_1h_tokens=500_000,
        )
        cost = compute_cost("anthropic/claude-opus-4-7", usage)
        assert cost == pytest.approx(3.125 + 5.0)

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

    def test_cost_alias_registered_in_completer(self):
        # OSS-CC vocabulary alignment — players coming from ClawCode /
        # Cline / OpenCode reflexively type /cost. Tier-2 lift from the
        # 2026-04-26 research sweep (ROADMAP M6 prioritization tier-5).
        from hosts.cli.completer import SLASH_COMMANDS

        names = [cmd.name for cmd in SLASH_COMMANDS]
        assert "cost" in names
        assert "usage" in names  # original still present

    def test_cost_dispatch_resolves_same_handler_as_usage(self):
        # The actual dispatch lives inside the REPL loop as
        # `if prompt_text in ("/usage", "/cost")`. Read the source as
        # a regression guard so a future refactor that splits the
        # branches gets caught — both must route to _show_usage_summary.
        import inspect

        from hosts.cli import __main__ as cli_main

        src = inspect.getsource(cli_main)
        assert '("/usage", "/cost")' in src or '("/cost", "/usage")' in src
        # And that the branch body calls _show_usage_summary.
        # Slice the snippet around the membership check for a tighter
        # assertion than "anywhere in the file".
        idx = src.find('"/cost"')
        nearby = src[idx : idx + 500]
        assert "_show_usage_summary" in nearby

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

    def test_multi_model_agent_renders_two_rows(self, monkeypatch):
        # M14 cheap-tier override + smart spec mean Metis can ride
        # two models in a session — both must show as separate rows
        # with their own cost calc, not stacked into one bucket.
        from hosts.cli.__main__ import _show_usage_summary

        record_usage(
            "metis",
            _fake_response(prompt_tokens=200_000, completion_tokens=80_000),
            model="anthropic/claude-haiku-4-5-20251001",
        )
        record_usage(
            "metis",
            _fake_response(prompt_tokens=2_000_000, completion_tokens=4_000_000),
            model="anthropic/claude-opus-4-7",
        )

        captured = self._patch_echo(monkeypatch)
        _show_usage_summary()
        out = "\n".join(captured)

        # Two distinct cost rows for the same agent.
        # Haiku: 0.2M*1 + 0.08M*5 = 0.2 + 0.4 = $0.60
        # Opus:  2M*5 + 4M*25 = 10 + 100 = $110.00
        assert "haiku" in out.lower()
        assert "opus" in out.lower()
        assert "0.6000" in out  # haiku row cost
        assert "110.0000" in out  # opus row cost
        assert "110.6000" in out  # TOTAL = 0.6 + 110.0

    def test_unknown_model_renders_dash_and_explains(self, monkeypatch):
        from hosts.cli.__main__ import _show_usage_summary

        # Ollama is the only unpriced provider we use today (local models,
        # actually free). Anything else (Anthropic, Gemini) lives in the
        # pricing table.
        record_usage(
            "experimental",
            _fake_response(prompt_tokens=500_000, completion_tokens=100_000),
            model="ollama/llama3.3:70b",
        )

        captured = self._patch_echo(monkeypatch)
        _show_usage_summary()
        out = "\n".join(captured)
        assert "experimental" in out
        # Dollar sign with em-dash placeholder, not a dollar amount.
        assert "$—" in out
        # Explanatory hint pointing at the pricing table.
        assert "kourai_common.pricing" in out

    def test_gemini_model_now_renders_dollar_cost(self, monkeypatch):
        from hosts.cli.__main__ import _show_usage_summary

        # 1M input on 2.0 Flash → $0.10. Used to be $— before this PR.
        record_usage(
            "metis",
            _fake_response(prompt_tokens=1_000_000, completion_tokens=0),
            model="gemini/gemini-2.0-flash",
        )

        captured = self._patch_echo(monkeypatch)
        _show_usage_summary()
        out = "\n".join(captured)
        assert "metis" in out
        # Real cost line, not the unknown-model placeholder.
        assert "0.1000" in out
        assert "$—" not in out


class TestShortModelLabel:
    """``_short_model_label`` keeps the /usage tier column readable."""

    def test_haiku_keeps_version_segment(self):
        from hosts.cli.__main__ import _short_model_label

        assert _short_model_label("anthropic/claude-haiku-4-5-20251001") == "haiku-4-5"

    def test_sonnet_keeps_version_segment(self):
        from hosts.cli.__main__ import _short_model_label

        assert _short_model_label("anthropic/claude-sonnet-4-6") == "sonnet-4-6"

    def test_opus_keeps_version_segment(self):
        from hosts.cli.__main__ import _short_model_label

        assert _short_model_label("anthropic/claude-opus-4-7") == "opus-4-7"

    def test_gemini_strips_provider_prefix(self):
        from hosts.cli.__main__ import _short_model_label

        # Gemini doesn't have the "claude-" prefix to strip; the
        # path-strip handles the provider/.
        assert _short_model_label("gemini/gemini-2.5-pro") == "gemini-2"

    def test_empty_returns_question_mark(self):
        from hosts.cli.__main__ import _short_model_label

        assert _short_model_label("") == "?"

    def test_unknown_format_truncated(self):
        # Anything we haven't special-cased gets safely truncated to
        # the column width so the table doesn't overflow.
        from hosts.cli.__main__ import _short_model_label

        # "test/some-very-long-model-name" → strips provider → some-… (8 chars)
        result = _short_model_label("test/some-very-long-model-name")
        assert len(result) <= 8


class TestResetUsage:
    """``reset_session_usage`` is what the new /reset_usage slash command calls."""

    def test_clears_all_buckets(self):
        from kourai_common.usage import get_session_usage

        record_usage(
            "techne",
            _fake_response(prompt_tokens=1000, completion_tokens=500),
            model="anthropic/claude-sonnet-4-6",
        )
        record_usage(
            "kallos",
            _fake_response(prompt_tokens=200, completion_tokens=50),
            model="anthropic/claude-haiku-4-5-20251001",
        )
        assert len(get_session_usage().agents) == 2

        reset_session_usage()

        assert get_session_usage().agents == {}

    def test_safe_to_call_on_empty_session(self):
        # Idempotent — calling /reset_usage with nothing in the bucket
        # shouldn't raise.
        reset_session_usage()
        reset_session_usage()
        from kourai_common.usage import get_session_usage

        assert get_session_usage().agents == {}


class TestResetUsageSlashCommand:
    """The /reset_usage slash command is registered in the completer."""

    def test_command_registered_in_completer(self):
        from hosts.cli.completer import SLASH_COMMANDS

        names = [c.name for c in SLASH_COMMANDS]
        assert "reset_usage" in names

    def test_command_appears_in_help_via_slash_commands(self):
        # _show_help() iterates SLASH_COMMANDS, so registering the
        # command auto-surfaces it in /help. Sanity-check that the
        # description is non-empty.
        from hosts.cli.completer import SLASH_COMMANDS

        cmd = next(c for c in SLASH_COMMANDS if c.name == "reset_usage")
        assert cmd.description.strip()
