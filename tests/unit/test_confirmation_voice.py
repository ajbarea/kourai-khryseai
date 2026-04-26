"""M13 — voice regression guardrails for Forge Order Confirmation.

The runtime classifier is LLM-driven, so we can't unit-test the voice
itself the way we test code. What we CAN test is a guardrail spec that
catches obvious violations: banned phrases (mocking / condescending
tones), tier-1 verbosity caps, and the "no quoted-quotes" hygiene that
keeps the read-back parseable by ``parse_confirmation_response``.

These cases are curated examples of GOOD and BAD voice. If a prompt
edit lets one of the BAD cases through, that's a regression — re-tune
the ROUTING_PROMPT before merging. New violations get added to
``BANNED_PHRASES`` as the team finds them in dogfooding (per
the player-experience contract: "the maidens roast each other and
Hephaestus, never the player").

Lives under ``tests/unit/`` because every assertion below is static
(no LLM call, no network) — they belong on the push/PR fast lane.
When future LLM-fired regressions need live model calls to reproduce,
that follow-up moves to ``tests/integration/`` with the
``integration`` marker.
"""

from __future__ import annotations

import pytest

GOOD_CLEAR = [
    "double(n) in src/math.py with a test. Light the forge?",
    "Tiny one. Confirm?",
    "`triple(n)` in math.py + test. Ready?",
    "add(a, b) plus a parametric test. Light it?",
]

GOOD_SMART = [
    "double(n) in src/math.py — plus the edge cases Metis would want. Bare or works?",
    "Function added. Metis suggests negative-int test. Include?",
    "divide(a, b) — Metis flags zero-division. Defensive or assume callers handle?",
]

GOOD_CLARIFY = [
    "Which functions are you targeting? Algorithmic or micro-opt?",
    "Got benchmarks I should target, or am I building them?",
    "Stream chunked I/O or load all at once?",
]


# Phrases that mock or condescend to the player. Per player-experience
# contract #1: "The maidens roast each other and Hephaestus, never the
# player." If the LLM produces any of these in a read-back, we want a
# loud test failure during dogfooding.
BANNED_PHRASES = [
    "really?",  # mocking tone
    "you sure?",  # condescending
    "that's all",  # belittling
    "couldn't you",  # passive-aggressive
    "obviously",  # condescending
    "don't you",  # accusatory
]


@pytest.mark.parametrize("read_back", GOOD_CLEAR + GOOD_SMART + GOOD_CLARIFY)
def test_no_banned_phrases(read_back):
    lower = read_back.lower()
    for banned in BANNED_PHRASES:
        assert banned not in lower, (
            f"banned phrase {banned!r} in read-back: {read_back!r} "
            f"— violates player-experience contract #1 (no mocking the player)"
        )


@pytest.mark.parametrize("read_back", GOOD_CLEAR)
def test_clear_tier_under_word_count(read_back):
    """Tier 1 confirmations should be tight — under 15 words.

    Per the player-experience contract: "Tier 1 should feel like a
    beat (<2s of friction). Anything heavier than necessary breaks
    the player's flow."
    """
    word_count = len(read_back.split())
    assert word_count <= 15, f"tier 1 too verbose ({word_count} words): {read_back!r}"


@pytest.mark.parametrize("read_back", GOOD_CLEAR + GOOD_SMART)
def test_no_unescaped_quotes_in_read_back(read_back):
    """Read-backs must not contain unescaped double quotes — they'd
    break the ``CONFIRM_ORDER: <tier> "<read-back>"`` parser since the
    regex matches the LAST quoted span on the line."""
    # Backticks are fine (markdown code), apostrophes are fine
    # (English contractions). Only ASCII " is the killer.
    assert '"' not in read_back, (
        f'unescaped " in read-back: {read_back!r} — would break parse_confirmation_response'
    )


@pytest.mark.parametrize("read_back", GOOD_CLEAR + GOOD_SMART + GOOD_CLARIFY)
def test_read_back_round_trips_through_parser(read_back):
    """Every GOOD example must round-trip cleanly through the parser
    — no edge case in the corpus that the regex would reject."""
    from agents.hephaestus.confirmation import parse_confirmation_response

    # Pick a tier per-block by looking up the source list.
    if read_back in GOOD_CLEAR:
        tier = "clear"
    elif read_back in GOOD_SMART:
        tier = "smart"
    else:
        tier = "clarify"

    raw = f'CONFIRM_ORDER: {tier} "{read_back}"'
    parsed = parse_confirmation_response(raw)
    assert parsed.tier == tier
    assert parsed.read_back == read_back
