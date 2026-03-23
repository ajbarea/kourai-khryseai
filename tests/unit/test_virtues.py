"""Unit tests for kourai_common.virtues — Forge Virtue scoring system.

Tests are self-contained: each test creates its own in-memory SQLite DB by
monkeypatching _get_virtues_db so nothing touches the real ~/.kourai_khryseai.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock

import pytest

from kourai_common.virtues import (
    FORGE_VIRTUES,
    VIRTUE_HIGH_THRESHOLD,
    VIRTUE_LOW_THRESHOLD,
    Virtue,
    check_virtue_interjections,
    get_all_virtues,
    get_virtue_context,
    get_virtue_deltas,
    get_virtue_scores,
    update_virtue,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _fresh_db() -> sqlite3.Connection:
    """In-memory DB with the player_virtues schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE player_virtues (
            player_id TEXT NOT NULL,
            virtue_key TEXT NOT NULL,
            score REAL DEFAULT 0.5,
            session_delta REAL DEFAULT 0.0,
            last_updated REAL DEFAULT (unixepoch()),
            PRIMARY KEY (player_id, virtue_key)
        )
    """)
    conn.commit()
    return conn


@pytest.fixture()
def db(monkeypatch):
    """Monkeypatch _get_virtues_db to return a fresh in-memory DB each call.

    virtues.py calls conn.close() at the end of each public function. We wrap
    the real connection in a MagicMock so close() becomes a no-op while all
    other methods (execute, commit, etc.) delegate to the real sqlite3.Connection.
    This keeps the in-memory DB alive across multiple calls within a single test.

    Note: sqlite3.Connection.close is a read-only C-extension slot, so we cannot
    patch it directly on the instance — wrapping is the only viable approach.
    """
    conn = _fresh_db()
    mock_conn = MagicMock(wraps=conn)
    mock_conn.close = MagicMock()  # no-op — keeps in-memory DB alive
    monkeypatch.setattr("kourai_common.virtues._get_virtues_db", lambda: mock_conn)
    return mock_conn


PLAYER = "test-player-abc123"


# ── FORGE_VIRTUES catalog ─────────────────────────────────────────────────────


def test_forge_virtues_has_eight_entries():
    assert len(FORGE_VIRTUES) == 8


def test_all_expected_virtue_keys_present():
    expected = {"sophia", "techne_v", "arete", "mneia", "synergy", "kairos", "harmonia", "eros"}
    assert set(FORGE_VIRTUES.keys()) == expected


def test_each_virtue_has_patron_agent():
    for key, virtue in FORGE_VIRTUES.items():
        assert virtue.patron_agents, f"{key} has no patron_agents"


def test_companion_spirit_virtues_have_correct_patrons():
    assert FORGE_VIRTUES["kairos"].patron_agents == ["puck"]
    assert FORGE_VIRTUES["eros"].patron_agents == ["cupid"]
    assert FORGE_VIRTUES["harmonia"].patron_agents == ["kallos"]


def test_virtue_dataclass_fields():
    v = Virtue(
        name="Test",
        description="A test virtue.",
        low_label="Low",
        high_label="High",
        patron_agents=["techne"],
    )
    assert v.name == "Test"
    assert v.low_label == "Low"
    assert v.high_label == "High"


# ── get_virtue_scores ─────────────────────────────────────────────────────────


def test_get_virtue_scores_returns_neutral_for_new_player(db):
    scores = get_virtue_scores(PLAYER)
    assert set(scores.keys()) == set(FORGE_VIRTUES.keys())
    for key, score in scores.items():
        assert score == 0.5, f"{key} should default to 0.5, got {score}"


def test_get_virtue_scores_reflects_stored_value(db):
    db.execute(
        "INSERT INTO player_virtues (player_id, virtue_key, score) VALUES (?, ?, ?)",
        (PLAYER, "arete", 0.75),
    )
    db.commit()
    scores = get_virtue_scores(PLAYER)
    assert scores["arete"] == pytest.approx(0.75)


def test_get_virtue_scores_ignores_unknown_keys(db):
    db.execute(
        "INSERT INTO player_virtues (player_id, virtue_key, score) VALUES (?, ?, ?)",
        (PLAYER, "bogus_virtue", 0.9),
    )
    db.commit()
    scores = get_virtue_scores(PLAYER)
    assert "bogus_virtue" not in scores


def test_get_all_virtues_is_alias_for_get_virtue_scores(db):
    # Both should return identical results
    assert get_all_virtues(PLAYER) == get_virtue_scores(PLAYER)


# ── update_virtue ─────────────────────────────────────────────────────────────


def test_update_virtue_increases_score(db):
    new_score = update_virtue(PLAYER, "sophia", 0.10)
    assert new_score == pytest.approx(0.60)  # 0.5 + 0.10


def test_update_virtue_decreases_score(db):
    new_score = update_virtue(PLAYER, "sophia", -0.20)
    assert new_score == pytest.approx(0.30)  # 0.5 - 0.20


def test_update_virtue_clamps_at_one(db):
    new_score = update_virtue(PLAYER, "techne_v", 0.99)
    assert new_score == pytest.approx(1.0)


def test_update_virtue_clamps_at_zero(db):
    new_score = update_virtue(PLAYER, "techne_v", -0.99)
    assert new_score == pytest.approx(0.0)


def test_update_virtue_accumulates_session_delta(db):
    update_virtue(PLAYER, "synergy", 0.05)
    update_virtue(PLAYER, "synergy", 0.03)
    deltas = get_virtue_deltas(PLAYER)
    assert deltas.get("synergy", 0.0) == pytest.approx(0.08)


def test_update_virtue_unknown_key_returns_neutral(db):
    result = update_virtue(PLAYER, "not_a_virtue", 0.5)
    assert result == 0.5


def test_update_virtue_persists_across_reads(db):
    update_virtue(PLAYER, "mneia", 0.15)
    scores = get_virtue_scores(PLAYER)
    assert scores["mneia"] == pytest.approx(0.65)


# ── get_virtue_deltas ─────────────────────────────────────────────────────────


def test_get_virtue_deltas_empty_for_new_player(db):
    deltas = get_virtue_deltas(PLAYER)
    assert deltas == {}


def test_get_virtue_deltas_only_returns_nonzero(db):
    update_virtue(PLAYER, "arete", 0.05)
    deltas = get_virtue_deltas(PLAYER)
    assert "arete" in deltas
    # Keys with no updates should not appear
    assert "sophia" not in deltas


# ── check_virtue_interjections ────────────────────────────────────────────────


def test_check_interjections_none_at_neutral(db):
    result = check_virtue_interjections(PLAYER, "sophia")
    assert result is None


def test_check_interjections_high_when_above_threshold(db):
    # Push sophia above VIRTUE_HIGH_THRESHOLD
    update_virtue(PLAYER, "sophia", VIRTUE_HIGH_THRESHOLD - 0.5 + 0.05)
    result = check_virtue_interjections(PLAYER, "sophia")
    assert result is not None
    assert result["type"] == "high"
    assert result["patron_agent"] == "metis"


def test_check_interjections_low_when_below_threshold(db):
    # Push sophia below VIRTUE_LOW_THRESHOLD
    update_virtue(PLAYER, "sophia", -(0.5 - VIRTUE_LOW_THRESHOLD + 0.05))
    result = check_virtue_interjections(PLAYER, "sophia")
    assert result is not None
    assert result["type"] == "low"


def test_check_interjections_unknown_key_returns_none(db):
    result = check_virtue_interjections(PLAYER, "unknown_virtue")
    assert result is None


def test_check_interjections_returns_virtue_object(db):
    update_virtue(PLAYER, "kairos", VIRTUE_HIGH_THRESHOLD - 0.5 + 0.05)
    result = check_virtue_interjections(PLAYER, "kairos")
    assert result is not None
    assert isinstance(result["virtue"], Virtue)
    assert result["patron_agent"] == "puck"


def test_check_interjections_eros_patron_is_cupid(db):
    update_virtue(PLAYER, "eros", VIRTUE_HIGH_THRESHOLD - 0.5 + 0.05)
    result = check_virtue_interjections(PLAYER, "eros")
    assert result is not None
    assert result["patron_agent"] == "cupid"


# ── get_virtue_context ────────────────────────────────────────────────────────


def test_get_virtue_context_returns_string(db):
    ctx = get_virtue_context(PLAYER)
    assert isinstance(ctx, str)
    assert "virtue" in ctx.lower()


def test_get_virtue_context_includes_low_label_when_below_threshold(db):
    update_virtue(PLAYER, "mneia", -(0.5 - VIRTUE_LOW_THRESHOLD + 0.05))
    ctx = get_virtue_context(PLAYER)
    assert FORGE_VIRTUES["mneia"].low_label in ctx


def test_get_virtue_context_includes_high_label_when_above_threshold(db):
    update_virtue(PLAYER, "synergy", VIRTUE_HIGH_THRESHOLD - 0.5 + 0.05)
    ctx = get_virtue_context(PLAYER)
    assert FORGE_VIRTUES["synergy"].high_label in ctx


def test_get_virtue_context_includes_all_virtue_names(db):
    ctx = get_virtue_context(PLAYER)
    for virtue in FORGE_VIRTUES.values():
        assert virtue.name in ctx, f"{virtue.name} missing from virtue context"
