"""Tests for the player fact extraction and pipeline system.

Phase 4.5: Full pipeline coverage — extraction, storage, stripping,
process_agent_output, PlayerFact normalization, and KnowledgeGraphFact conversion.
"""

from __future__ import annotations

from unittest.mock import patch

from kourai_common.facts import (
    KnowledgeGraphFact,
    PlayerFact,
    extract_facts,
    process_agent_output,
    store_facts,
    strip_facts,
)


def test_extract_facts():
    text = 'Here is some text. <FACT category="preference" confidence="high">Player loves Python.</FACT> End.'
    facts = extract_facts(text, "techne")

    assert len(facts) == 1
    fact = facts[0]
    assert fact.category == "preference"
    assert fact.confidence == "high"
    assert fact.body == "Player loves Python."
    assert fact.source_agent == "techne"


def test_extract_multiple_facts():
    text = '<FACT confidence="low">First fact</FACT> some noise <FACT category="skill" confidence="medium">Second fact</FACT>'
    facts = extract_facts(text)

    assert len(facts) == 2
    assert facts[0].body == "First fact"
    assert facts[0].confidence == "low"

    assert facts[1].body == "Second fact"
    assert facts[1].category == "skill"
    assert facts[1].confidence == "medium"


def test_strip_facts():
    text = 'Here is some text. <FACT category="preference" confidence="high">Player loves Python.</FACT> End.'
    stripped = strip_facts(text)
    assert stripped == "Here is some text.  End."


def test_strip_facts_no_tags():
    """Text with no FACT tags is returned unchanged."""
    text = "Plain text with no facts."
    assert strip_facts(text) == text


def test_strip_facts_multiple_tags():
    """All FACT tags are removed when multiple are present."""
    text = '<FACT confidence="high">Fact 1</FACT> middle <FACT confidence="low">Fact 2</FACT> end'
    stripped = strip_facts(text)
    assert "<FACT" not in stripped
    assert "middle" in stripped
    assert "end" in stripped


# ── PlayerFact normalization ──────────────────────────────────────────────────


class TestPlayerFact:
    def test_weight_for_high_confidence(self):
        fact = PlayerFact(body="Player knows Rust", confidence="high")
        assert fact.weight == 1.0

    def test_weight_for_medium_confidence(self):
        fact = PlayerFact(body="Player likes async", confidence="medium")
        assert fact.weight == 0.6

    def test_weight_for_low_confidence(self):
        fact = PlayerFact(body="Player might use Windows", confidence="low")
        assert fact.weight == 0.3

    def test_invalid_confidence_defaults_to_medium(self):
        fact = PlayerFact(body="some fact", confidence="very_sure")
        assert fact.confidence == "medium"
        assert fact.weight == 0.6

    def test_invalid_category_defaults_to_preference(self):
        fact = PlayerFact(body="some fact", category="random_invalid_cat")
        assert fact.category == "preference"

    def test_valid_categories_accepted(self):
        for cat in ("preference", "identity", "skill", "context", "goal", "personality"):
            fact = PlayerFact(body="x", category=cat)
            assert fact.category == cat

    def test_to_dict_contains_all_fields(self):
        fact = PlayerFact(
            body="Player prefers tabs",
            category="preference",
            confidence="high",
            source_agent="kallos",
        )
        d = fact.to_dict()
        assert d["body"] == "Player prefers tabs"
        assert d["category"] == "preference"
        assert d["confidence"] == "high"
        assert d["source_agent"] == "kallos"
        assert d["weight"] == 1.0


# ── KnowledgeGraphFact ────────────────────────────────────────────────────────


class TestKnowledgeGraphFact:
    def test_from_player_fact_maps_fields(self):
        pf = PlayerFact(
            body="Likes Python", category="skill", confidence="high", source_agent="techne"
        )
        kgf = KnowledgeGraphFact.from_player_fact(player_id="player-123", fact=pf)

        assert kgf.body == "Likes Python"
        assert kgf.category == "skill"
        assert kgf.confidence == 1.0  # high → weight 1.0
        assert kgf.source_agent == "techne"
        assert kgf.player_id == "player-123"
        assert kgf.validity == "active"
        assert kgf.reinforcement_count == 1

    def test_from_player_fact_generates_fact_id(self):
        pf = PlayerFact(body="Fact", confidence="medium")
        kgf = KnowledgeGraphFact.from_player_fact(player_id="p1", fact=pf)
        assert len(kgf.fact_id) > 0

    def test_from_player_fact_uses_supplied_fact_id(self):
        pf = PlayerFact(body="Fact", confidence="low")
        kgf = KnowledgeGraphFact.from_player_fact(player_id="p1", fact=pf, fact_id="custom-id-123")
        assert kgf.fact_id == "custom-id-123"

    def test_to_dict_is_json_serializable(self):
        import json

        pf = PlayerFact(body="Uses dark mode", category="preference", confidence="high")
        kgf = KnowledgeGraphFact.from_player_fact(player_id="player-abc", fact=pf)
        d = kgf.to_dict()
        json.dumps(d)  # must not raise


# ── store_facts ───────────────────────────────────────────────────────────────


class TestStoreFacts:
    def test_calls_add_player_memory_for_each_fact(self):
        facts = [
            PlayerFact(
                body="Prefers Python",
                category="preference",
                confidence="high",
                source_agent="techne",
            ),
            PlayerFact(
                body="Uses dark mode",
                category="preference",
                confidence="medium",
                source_agent="kallos",
            ),
        ]
        with patch("kourai_common.player.add_player_memory") as mock_add:
            store_facts("player-uuid", facts)

        assert mock_add.call_count == 2

    def test_formats_content_with_fact_prefix(self):
        facts = [
            PlayerFact(
                body="Knows Rust", category="skill", confidence="high", source_agent="techne"
            )
        ]
        captured: list[dict] = []

        def capture(**kwargs: object) -> None:
            captured.append(dict(kwargs))

        with patch("kourai_common.player.add_player_memory", side_effect=capture):
            store_facts("player-uuid", facts)

        assert len(captured) == 1
        assert "[FACT:skill/high]" in captured[0]["content"]
        assert "Knows Rust" in captured[0]["content"]

    def test_passes_weight_as_importance(self):
        facts = [PlayerFact(body="High confidence fact", confidence="high")]
        captured: list[dict] = []

        def capture(**kwargs: object) -> None:
            captured.append(dict(kwargs))

        with patch("kourai_common.player.add_player_memory", side_effect=capture):
            store_facts("player-uuid", facts)

        assert captured[0]["importance"] == 1.0

    def test_does_nothing_for_empty_facts(self):
        with patch("kourai_common.player.add_player_memory") as mock_add:
            store_facts("player-uuid", [])
        mock_add.assert_not_called()

    def test_does_nothing_for_empty_player_id(self):
        facts = [PlayerFact(body="Some fact", confidence="high")]
        with patch("kourai_common.player.add_player_memory") as mock_add:
            store_facts("", facts)
        mock_add.assert_not_called()


# ── process_agent_output ──────────────────────────────────────────────────────


class TestProcessAgentOutput:
    def test_returns_clean_text_with_facts_stripped(self):
        text = 'Good work! <FACT category="skill" confidence="high">Player knows async.</FACT> Keep it up.'
        with patch("kourai_common.player.add_player_memory"):
            clean = process_agent_output(text, player_id="p1", source_agent="techne")

        assert "<FACT" not in clean
        assert "Good work!" in clean
        assert "Keep it up." in clean

    def test_extracts_and_stores_facts(self):
        text = '<FACT category="preference" confidence="high">Player prefers tabs.</FACT>'
        stored: list[dict] = []

        def capture(**kwargs: object) -> None:
            stored.append(dict(kwargs))

        with patch("kourai_common.player.add_player_memory", side_effect=capture):
            process_agent_output(text, player_id="p1", source_agent="mneme")

        assert len(stored) == 1
        assert "Player prefers tabs" in stored[0]["content"]

    def test_no_store_when_no_facts(self):
        text = "Clean response with no fact tags."
        with patch("kourai_common.player.add_player_memory") as mock_add:
            result = process_agent_output(text, player_id="p1")
        mock_add.assert_not_called()
        assert result == text

    def test_assigns_source_agent_to_extracted_facts(self):
        text = '<FACT confidence="medium">Player iterates fast.</FACT>'
        stored: list[dict] = []

        def capture(**kwargs: object) -> None:
            stored.append(dict(kwargs))

        with patch("kourai_common.player.add_player_memory", side_effect=capture):
            process_agent_output(text, player_id="p1", source_agent="puck")

        assert stored[0]["agent_name"] == "puck"

    def test_handles_multiple_facts_in_one_response(self):
        text = (
            '<FACT category="skill" confidence="high">Knows Python.</FACT> '
            '<FACT category="goal" confidence="medium">Wants to ship by Q2.</FACT>'
        )
        stored: list[str] = []

        def capture(**kwargs: object) -> None:
            stored.append(str(kwargs["content"]))

        with patch("kourai_common.player.add_player_memory", side_effect=capture):
            clean = process_agent_output(text, player_id="p1", source_agent="cupid")

        assert len(stored) == 2
        assert clean.strip() == ""  # all text was inside FACT tags
