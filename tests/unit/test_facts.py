"""Tests for the player fact extraction and pipeline system.

Full pipeline coverage — extraction, storage, stripping,
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


# ── M17 Phase 1: project_id axis on facts ─────────────────────────


def test_player_fact_default_project_id_is_none():
    """A PlayerFact constructed without project_id is global by default."""
    fact = PlayerFact(body="any preference")
    assert fact.project_id is None


def test_player_fact_carries_project_id_when_provided():
    fact = PlayerFact(body="coverage_target: 80%", project_id="abc123def4567890")
    assert fact.project_id == "abc123def4567890"


def test_extract_fact_parses_project_id_attribute():
    """The <FACT> tag accepts a project_id="..." attribute."""
    text = (
        '<FACT category="preference" confidence="high" '
        'project_id="abc123def4567890">coverage_target: 80%</FACT>'
    )
    facts = extract_facts(text, "metis")

    assert len(facts) == 1
    assert facts[0].project_id == "abc123def4567890"
    assert facts[0].body == "coverage_target: 80%"
    assert facts[0].category == "preference"
    assert facts[0].confidence == "high"


def test_extract_fact_without_project_id_is_global():
    """A <FACT> tag without project_id yields a None scope (global)."""
    text = '<FACT category="preference">global preference</FACT>'
    facts = extract_facts(text)
    assert len(facts) == 1
    assert facts[0].project_id is None


def test_knowledge_graph_fact_inherits_project_id():
    """KnowledgeGraphFact.from_player_fact copies the project_id."""
    fact = PlayerFact(body="x", project_id="abc123def4567890")
    kg = KnowledgeGraphFact.from_player_fact(player_id="p1", fact=fact)
    assert kg.project_id == "abc123def4567890"


def test_player_fact_to_dict_includes_project_id():
    fact = PlayerFact(body="x", project_id="abc123def4567890")
    assert fact.to_dict()["project_id"] == "abc123def4567890"


def test_knowledge_graph_fact_to_dict_includes_project_id():
    fact = PlayerFact(body="x", project_id="abc123def4567890")
    kg = KnowledgeGraphFact.from_player_fact(player_id="p1", fact=fact)
    assert kg.to_dict()["project_id"] == "abc123def4567890"


def test_store_facts_threads_project_id_to_storage():
    """store_facts forwards each fact's project_id to add_player_memory."""
    facts = [
        PlayerFact(body="A", project_id="proj-A"),
        PlayerFact(body="B"),  # global
    ]
    captured: list[dict] = []

    def capture(**kwargs: object) -> None:
        captured.append(kwargs)

    with patch("kourai_common.player.add_player_memory", side_effect=capture):
        store_facts("p1", facts)

    assert len(captured) == 2
    assert captured[0]["project_id"] == "proj-A"
    assert captured[1]["project_id"] is None


# ── M17 Phase 1: read-side scope filter ────────────────────────────


def test_get_relevant_facts_passes_project_id_to_get_player_memories():
    """get_relevant_facts_for_enrichment forwards project_id to the storage layer."""
    from kourai_common.facts import get_relevant_facts_for_enrichment

    captured_kwargs: dict = {}

    def fake_get(**kwargs: object) -> list:
        captured_kwargs.update(kwargs)
        return []

    with patch("kourai_common.player.get_player_memories", side_effect=fake_get):
        get_relevant_facts_for_enrichment("p1", project_id="proj-A")

    assert captured_kwargs["project_id"] == "proj-A"


def test_get_relevant_facts_default_project_id_is_none():
    """Calls without project_id forward None (no project axis applied)."""
    from kourai_common.facts import get_relevant_facts_for_enrichment

    captured_kwargs: dict = {}

    def fake_get(**kwargs: object) -> list:
        captured_kwargs.update(kwargs)
        return []

    with patch("kourai_common.player.get_player_memories", side_effect=fake_get):
        get_relevant_facts_for_enrichment("p1")

    assert captured_kwargs["project_id"] is None


def test_get_relevant_facts_returns_project_id_in_each_dict():
    """The dict returned from enrichment carries the persisted project_id."""
    from kourai_common.facts import get_relevant_facts_for_enrichment

    fake_memory = {
        "memory_id": "m1",
        "agent_name": "metis",
        "category": "fact",
        "content": "[FACT:preference/high] coverage_target: 80%",
        "importance": 0.9,
        "access_count": 0,
        "created_at": "2026-04-29T10:00:00Z",
        "last_accessed": "2026-04-29T10:00:00Z",
        "source": "agent_observed",
        "project_id": "proj-A",
    }

    with patch("kourai_common.player.get_player_memories", return_value=[fake_memory]):
        out = get_relevant_facts_for_enrichment("p1", project_id="proj-A")

    assert out[0]["project_id"] == "proj-A"


def test_build_fact_context_passes_project_id():
    """build_fact_context threads project_id to enrichment."""
    from kourai_common.facts import build_fact_context

    captured_kwargs: dict = {}

    def fake_get(**kwargs: object) -> list:
        captured_kwargs.update(kwargs)
        return []

    with patch("kourai_common.player.get_player_memories", side_effect=fake_get):
        build_fact_context("p1", agent_name="metis", project_id="proj-A")

    assert captured_kwargs["project_id"] == "proj-A"


# ── M17 Phase 2 item 7: /preferences CRUD primitives ────────────────────


import sqlite3

import pytest

from kourai_common.player import _ensure_player_tables


@pytest.fixture
def _isolate_player_db(tmp_path, monkeypatch):
    """Sandbox the SQLite player DB so CRUD tests touch nothing on disk."""
    db_path = tmp_path / "test_memory.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)

    import kourai_common.player as player_mod

    player_mod._tables_initialized = False
    _ensure_player_tables(conn)
    monkeypatch.setattr(player_mod, "_get_player_db", lambda: conn)
    yield conn
    conn.close()


class TestListPreferenceFacts:
    """``list_preference_facts`` returns project-scoped preference rows."""

    def test_empty_when_no_facts_stored(self, _isolate_player_db):
        from kourai_common.facts import list_preference_facts

        assert list_preference_facts("player-uuid", project_id="proj-A") == []

    def test_returns_facts_in_active_project_and_global(self, _isolate_player_db):
        from kourai_common.facts import PlayerFact, list_preference_facts, store_facts

        store_facts(
            "player-uuid",
            [
                PlayerFact(
                    body="coverage_target: 80%",
                    category="preference",
                    confidence="high",
                    source_agent="metis",
                    project_id="proj-A",
                ),
                PlayerFact(
                    body="python_version: 3.12",
                    category="preference",
                    confidence="high",
                    source_agent="metis",
                    project_id=None,  # global
                ),
                PlayerFact(
                    body="coverage_target: 95%",
                    category="preference",
                    confidence="high",
                    source_agent="metis",
                    project_id="proj-B",  # other project — must not surface
                ),
            ],
        )
        out = list_preference_facts("player-uuid", project_id="proj-A")

        kinds = {row["kind"] for row in out}
        assert kinds == {"coverage_target", "python_version"}
        # proj-A's coverage_target wins, not proj-B's.
        coverage = next(r for r in out if r["kind"] == "coverage_target")
        assert coverage["value"] == "80%"
        assert coverage["scope"] == "project"
        python = next(r for r in out if r["kind"] == "python_version")
        assert python["scope"] == "global"

    def test_filters_to_closed_vocab(self, _isolate_player_db):
        # Free-form preference facts (skill, identity, observations from
        # process_agent_output) must not surface as "preferences" — only the
        # closed-vocab kinds Metis and the /preferences set path can emit.
        from kourai_common.facts import PlayerFact, list_preference_facts, store_facts

        store_facts(
            "player-uuid",
            [
                PlayerFact(
                    body="prefers verbose error messages",  # free-form, no kind:
                    category="preference",
                    confidence="medium",
                    source_agent="techne",
                    project_id="proj-A",
                ),
                PlayerFact(
                    body="coverage_target: 80%",
                    category="preference",
                    confidence="high",
                    source_agent="metis",
                    project_id="proj-A",
                ),
            ],
        )
        out = list_preference_facts("player-uuid", project_id="proj-A")
        assert {row["kind"] for row in out} == {"coverage_target"}


class TestForgetPreferenceFact:
    """``forget_preference_fact`` removes scope+kind rows; right-to-forget."""

    def test_removes_matching_kind_in_project_only(self, _isolate_player_db):
        from kourai_common.facts import (
            PlayerFact,
            forget_preference_fact,
            list_preference_facts,
            store_facts,
        )

        store_facts(
            "player-uuid",
            [
                PlayerFact(
                    body="coverage_target: 80%",
                    category="preference",
                    confidence="high",
                    source_agent="metis",
                    project_id="proj-A",
                ),
                PlayerFact(
                    body="coverage_target: 95%",
                    category="preference",
                    confidence="high",
                    source_agent="metis",
                    project_id="proj-B",
                ),
            ],
        )
        deleted = forget_preference_fact("player-uuid", project_id="proj-A", kind="coverage_target")
        assert deleted == 1

        # proj-A's coverage_target gone; proj-B's coverage_target survives.
        a = list_preference_facts("player-uuid", project_id="proj-A")
        assert a == []
        b = list_preference_facts("player-uuid", project_id="proj-B")
        assert {row["kind"]: row["value"] for row in b} == {"coverage_target": "95%"}

    def test_returns_zero_when_no_match(self, _isolate_player_db):
        from kourai_common.facts import forget_preference_fact

        assert (
            forget_preference_fact("player-uuid", project_id="proj-A", kind="coverage_target") == 0
        )

    def test_removes_global_when_project_id_is_none(self, _isolate_player_db):
        from kourai_common.facts import (
            PlayerFact,
            forget_preference_fact,
            list_preference_facts,
            store_facts,
        )

        store_facts(
            "player-uuid",
            [
                PlayerFact(
                    body="python_version: 3.12",
                    category="preference",
                    confidence="high",
                    source_agent="metis",
                    project_id=None,
                ),
                PlayerFact(
                    body="python_version: 3.13",
                    category="preference",
                    confidence="high",
                    source_agent="metis",
                    project_id="proj-A",
                ),
            ],
        )
        deleted = forget_preference_fact("player-uuid", project_id=None, kind="python_version")
        assert deleted == 1

        # The global row is gone; the proj-A scoped row survives.
        scoped = list_preference_facts("player-uuid", project_id="proj-A")
        kinds = {r["kind"]: r["scope"] for r in scoped}
        assert kinds == {"python_version": "project"}


class TestSetPreferenceFact:
    """``set_preference_fact`` upserts: replaces existing same-scope fact."""

    def test_writes_new_fact_when_none_exists(self, _isolate_player_db):
        from kourai_common.facts import (
            list_preference_facts,
            set_preference_fact,
        )

        ok = set_preference_fact(
            player_id="player-uuid",
            project_id="proj-A",
            kind="coverage_target",
            value="80%",
        )
        assert ok is True

        out = list_preference_facts("player-uuid", project_id="proj-A")
        assert len(out) == 1
        assert out[0]["kind"] == "coverage_target"
        assert out[0]["value"] == "80%"

    def test_replaces_existing_fact_for_same_scope_and_kind(self, _isolate_player_db):
        from kourai_common.facts import (
            list_preference_facts,
            set_preference_fact,
        )

        set_preference_fact(
            player_id="player-uuid",
            project_id="proj-A",
            kind="coverage_target",
            value="80%",
        )
        set_preference_fact(
            player_id="player-uuid",
            project_id="proj-A",
            kind="coverage_target",
            value="95%",
        )
        out = list_preference_facts("player-uuid", project_id="proj-A")
        # Exactly one row — the override, not a duplicate.
        assert len(out) == 1
        assert out[0]["value"] == "95%"

    def test_rejects_unknown_preference_kind(self, _isolate_player_db):
        from kourai_common.facts import set_preference_fact

        ok = set_preference_fact(
            player_id="player-uuid",
            project_id="proj-A",
            kind="not_a_real_kind",
            value="anything",
        )
        assert ok is False

    def test_rejects_blank_value(self, _isolate_player_db):
        from kourai_common.facts import set_preference_fact

        assert (
            set_preference_fact(
                player_id="player-uuid",
                project_id="proj-A",
                kind="coverage_target",
                value="   ",
            )
            is False
        )
