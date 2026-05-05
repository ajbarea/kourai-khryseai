"""Unit tests for the shared emoji-prefix → agent map and ``detect_agent``.

Both CLI and GUI route emoji-prefixed status strings through this map.
Previously each host had its own dict (CLI ``_EMOJI_TO_MAIDEN``, GUI
``EMOJI_TO_AGENT``) — drift risk every time Hephaestus picks up a new
agent or changes a glyph. The shared map lives next to ``AGENT_METADATA``.
"""

from __future__ import annotations

from kourai_common.agents import EMOJI_PREFIX, detect_agent


def test_emoji_prefix_covers_all_six_main_agents():
    expected = {"hephaestus", "metis", "techne", "dokimasia", "kallos", "mneme"}
    assert set(EMOJI_PREFIX.values()) >= expected


def test_emoji_prefix_handles_techne_variation_selectors():
    # ⚙ (U+2699) appears both bare and with the FE0F variation selector.
    # Both should resolve to techne — Hephaestus's emit varies by client.
    bare = "⚙"
    with_vs16 = "⚙️"
    assert EMOJI_PREFIX[bare] == "techne"
    assert EMOJI_PREFIX[with_vs16] == "techne"


def test_detect_agent_strips_emoji_and_returns_name():
    name, cleaned = detect_agent("\U0001f525 forging the pipeline")
    assert name == "hephaestus"
    assert cleaned == "forging the pipeline"


def test_detect_agent_handles_leading_whitespace():
    name, cleaned = detect_agent("   \U0001f4d0 analyzing tests/")
    assert name == "metis"
    assert cleaned == "analyzing tests/"


def test_detect_agent_returns_none_when_no_emoji_prefix():
    name, original = detect_agent("plain status without prefix")
    assert name is None
    assert original == "plain status without prefix"


def test_detect_agent_for_each_agent():
    # One representative test per agent — guards against accidental drop.
    cases = [
        ("\U0001f525 hephaestus line", "hephaestus"),
        ("\U0001f4d0 metis line", "metis"),
        ("⚙️ techne line", "techne"),
        ("\U0001f9ea dokimasia line", "dokimasia"),
        ("✨ kallos line", "kallos"),
        ("\U0001f4dc mneme line", "mneme"),
    ]
    for text, expected_agent in cases:
        name, _ = detect_agent(text)
        assert name == expected_agent, f"failed for {text!r}"
