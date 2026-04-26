"""M13 — Forge Order Confirmation: protocol parser + ROUTING_PROMPT.

The ``CONFIRM_ORDER`` routing token is Hephaestus's pre-pipeline gate.
Three tiers scale verbosity to order ambiguity:

- ``clear`` — one-line summary, "Light the forge?" (≤15 words)
- ``smart`` — summary + Metis's suggested upsells (edge cases, etc.)
- ``clarify`` — one specific missing-info question

The McDonald's-pattern (read-back-then-confirm) replaces the dead zone
between "Analyzing request..." and the pipeline announcement. Every
development task goes through this gate; ``/yolo`` opts out for
power users iterating fast.
"""

from __future__ import annotations

import pytest

from agents.hephaestus.confirmation import (
    ConfirmationResponse,
    parse_confirmation_response,
)


class TestParseConfirmationResponse:
    """Three tiers, three shapes — all parse via the same regex."""

    def test_clear_tier_parses(self):
        raw = 'CONFIRM_ORDER: clear "double(n) in src/math.py with a test. Light the forge?"'
        parsed = parse_confirmation_response(raw)
        assert isinstance(parsed, ConfirmationResponse)
        assert parsed.tier == "clear"
        assert "double(n)" in parsed.read_back
        assert parsed.read_back.endswith("Light the forge?")

    def test_smart_tier_parses_with_suggestions(self):
        raw = (
            'CONFIRM_ORDER: smart "double(n) in src/math.py — plus the edge '
            "cases Metis would want (zero, negatives, floats). Bare function "
            'or the works?"'
        )
        parsed = parse_confirmation_response(raw)
        assert parsed.tier == "smart"
        assert "edge cases" in parsed.read_back

    def test_clarify_tier_parses_with_question(self):
        raw = (
            'CONFIRM_ORDER: clarify "Which functions are you targeting? Algorithmic or micro-opt?"'
        )
        parsed = parse_confirmation_response(raw)
        assert parsed.tier == "clarify"
        assert "?" in parsed.read_back

    def test_unknown_tier_raises(self):
        with pytest.raises(ValueError, match="unknown tier"):
            parse_confirmation_response('CONFIRM_ORDER: bogus "..."')

    def test_malformed_response_raises(self):
        # No tier word at all.
        with pytest.raises(ValueError, match="malformed"):
            parse_confirmation_response("CONFIRM_ORDER: nothing-here")

    def test_missing_quotes_raises(self):
        # The plan requires the read-back to be quoted so we can carry
        # multi-word natural language through a single token boundary.
        with pytest.raises(ValueError, match="malformed"):
            parse_confirmation_response("CONFIRM_ORDER: clear no quotes here")

    def test_leading_trailing_whitespace_tolerated(self):
        raw = '  CONFIRM_ORDER: clear "double(n)? Confirm?"  \n'
        parsed = parse_confirmation_response(raw)
        assert parsed.tier == "clear"
        assert parsed.read_back == "double(n)? Confirm?"

    def test_response_is_immutable(self):
        # ConfirmationResponse is a frozen dataclass — guards against
        # downstream code mutating the read-back text mid-flight.
        parsed = parse_confirmation_response('CONFIRM_ORDER: clear "x"')
        with pytest.raises((AttributeError, Exception)):
            parsed.tier = "smart"  # type: ignore[misc]


class TestRoutingPromptDocumentsConfirmOrder:
    """ROUTING_PROMPT must teach the LLM the new response option."""

    def test_routing_prompt_mentions_confirm_order(self):
        from agents.hephaestus.agent import ROUTING_PROMPT

        assert "CONFIRM_ORDER:" in ROUTING_PROMPT

    def test_routing_prompt_lists_all_three_tiers(self):
        from agents.hephaestus.agent import ROUTING_PROMPT

        # The three tier keywords must appear so the LLM knows which to pick.
        assert "clear" in ROUTING_PROMPT
        assert "smart" in ROUTING_PROMPT
        assert "clarify" in ROUTING_PROMPT

    def test_routing_prompt_marks_gate_as_always_on(self):
        from agents.hephaestus.agent import ROUTING_PROMPT

        # Wording matters — the gate is the default. The agent-list
        # response is no longer the first response for development tasks.
        # Lower-cased substring check so capitalisation tweaks don't
        # break the test.
        prompt_lower = ROUTING_PROMPT.lower()
        assert "always" in prompt_lower or "every" in prompt_lower

    def test_routing_prompt_voice_constraints_present(self):
        from agents.hephaestus.agent import ROUTING_PROMPT

        # The personality contract: maidens roast Hephaestus and each other,
        # never the player. Voice guidance must be in the prompt.
        # Check for at least one of the constraint markers.
        assert any(
            marker in ROUTING_PROMPT
            for marker in ("never roasts the player", "tight", "TIGHT", "tier 1", "Tier 1")
        )
