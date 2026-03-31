"""Forge Virtues — Psychological wellness dimensions for Kourai Khryseai.

Inspired by Disco Elysium's skill system. Six psychological dimensions that
track the player's development as a craftsperson and collaborator.
Each virtue has a score (0.0–1.0) and generates agent interjections when
thresholds are crossed (both low and high).
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

PLAYER_DIR = Path.home() / ".kourai_khryseai"
VIRTUES_DB = PLAYER_DIR / "virtues.db"


@dataclass
class Virtue:
    """A single psychological wellness dimension."""

    name: str
    description: str
    low_label: str  # What low score means (the vice)
    high_label: str  # What high score means (the virtue apex)
    # Agents that care most about this virtue (for interjection routing)
    patron_agents: list[str] = field(default_factory=list)


# Eight Forge Virtues — 6 maidens + 2 companion spirits.
# Aidos and Aletheia are utility agents; they observe but don't own a virtue.
FORGE_VIRTUES: dict[str, Virtue] = {
    "sophia": Virtue(
        name="Sophia",
        description="Clarity of thought and quality of questions asked.",
        low_label="Confused",
        high_label="Lucid",
        patron_agents=["metis"],
    ),
    "techne_v": Virtue(
        name="Techne",
        description="Craft precision — the will to write code right, not just write code.",
        low_label="Sloppy",
        high_label="Masterful",
        patron_agents=["techne", "kallos"],
    ),
    "arete": Virtue(
        name="Arete",
        description="Excellence-seeking — consistent commitment to improving the work.",
        low_label="Complacent",
        high_label="Relentless",
        patron_agents=["dokimasia"],
    ),
    "mneia": Virtue(
        name="Mneia",
        description="Memory and continuity — honoring what was built before.",
        low_label="Forgetful",
        high_label="Archival",
        patron_agents=["mneme"],
    ),
    "synergy": Virtue(
        name="Synergy",
        description="Collaboration with the maidens — quality of the partnership.",
        low_label="Isolated",
        high_label="Bonded",
        patron_agents=["hephaestus"],
    ),
    "kairos": Virtue(
        name="Kairos",
        description="Right timing — knowing when to push, when to rest, when to ship.",
        low_label="Scattered",
        high_label="Attuned",
        patron_agents=["puck"],
    ),
    "harmonia": Virtue(
        name="Harmonia",
        description="Harmony — care for beauty, elegance, and aesthetic quality in the work.",
        low_label="Rough",
        high_label="Elegant",
        patron_agents=["kallos"],
    ),
    "eros": Virtue(
        name="Eros",
        description="Connection — the bonds formed with the agents through care and attention.",
        low_label="Distant",
        high_label="Devoted",
        patron_agents=["cupid"],
    ),
}

# Thresholds that trigger agent interjections
VIRTUE_LOW_THRESHOLD = 0.25  # Below this → vice interjection
VIRTUE_HIGH_THRESHOLD = 0.80  # Above this → virtue apex interjection


def _get_virtues_db() -> sqlite3.Connection:
    PLAYER_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(VIRTUES_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_virtues (
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


def get_virtue_scores(player_id: str) -> dict[str, float]:
    """Retrieve all virtue scores for a player. Returns 0.5 (neutral) for unknowns."""
    conn = _get_virtues_db()
    rows = conn.execute(
        "SELECT virtue_key, score FROM player_virtues WHERE player_id = ?",
        (player_id,),
    ).fetchall()
    scores = dict.fromkeys(FORGE_VIRTUES, 0.5)
    for virtue_key, score in rows:
        if virtue_key in scores:
            scores[virtue_key] = score
    conn.close()
    return scores


def get_all_virtues(player_id: str) -> dict[str, float]:
    """Alias for get_virtue_scores."""
    return get_virtue_scores(player_id)


def get_virtue_deltas(player_id: str) -> dict[str, float]:
    """Retrieve all virtue session deltas for a player."""
    conn = _get_virtues_db()
    rows = conn.execute(
        "SELECT virtue_key, session_delta FROM player_virtues WHERE player_id = ?",
        (player_id,),
    ).fetchall()
    deltas = {
        virtue_key: delta
        for virtue_key, delta in rows
        if virtue_key in FORGE_VIRTUES and delta != 0.0
    }
    conn.close()
    return deltas


def update_virtue(player_id: str, virtue_key: str, delta: float) -> float:
    """Adjust a virtue score by delta. Returns new score.

    Score is clamped to [0.0, 1.0]. Session delta is accumulated for
    the Forge Journal display (shows change per session).
    """
    if virtue_key not in FORGE_VIRTUES:
        log.warning("Unknown virtue key: %s", virtue_key)
        return 0.5

    conn = _get_virtues_db()
    current = conn.execute(
        "SELECT score FROM player_virtues WHERE player_id = ? AND virtue_key = ?",
        (player_id, virtue_key),
    ).fetchone()
    old_score = current[0] if current else 0.5
    new_score = max(0.0, min(1.0, old_score + delta))

    conn.execute(
        """
        INSERT INTO player_virtues (player_id, virtue_key, score, session_delta)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(player_id, virtue_key) DO UPDATE SET
            score = excluded.score,
            session_delta = session_delta + ?,
            last_updated = unixepoch()
        """,
        (player_id, virtue_key, new_score, delta, delta),
    )
    conn.commit()
    conn.close()

    log.info(
        "Virtue %s for player %s: %.2f → %.2f (Δ%.2f)",
        virtue_key,
        player_id[:8],
        old_score,
        new_score,
        delta,
    )
    return new_score


def get_virtue_context(player_id: str) -> str:
    """Build a virtue context string for injection into agent system prompts.

    Returns a concise description of the player's current psychological state
    for use in agent prompt personalization.
    """
    scores = get_virtue_scores(player_id)
    if not scores:
        return ""

    lines = []
    for key, virtue in FORGE_VIRTUES.items():
        score = scores.get(key, 0.5)
        if score <= VIRTUE_LOW_THRESHOLD:
            label = f"⚠️ {virtue.low_label}"
        elif score >= VIRTUE_HIGH_THRESHOLD:
            label = f"✨ {virtue.high_label}"
        else:
            label = f"{score:.0%}"
        lines.append(f"- {virtue.name}: {label}")

    return "Player forge virtues:\n" + "\n".join(lines)


def check_virtue_interjections(
    player_id: str,
    virtue_key: str,
) -> dict[str, Any] | None:
    """Check if a virtue score warrants an agent interjection.

    Returns an interjection dict if a threshold is crossed, else None.
    The interjection dict has:
    - 'virtue': the Virtue object
    - 'score': current score
    - 'type': 'low' | 'high'
    - 'patron_agent': which agent should deliver the interjection
    """
    if virtue_key not in FORGE_VIRTUES:
        return None

    scores = get_virtue_scores(player_id)
    score = scores.get(virtue_key, 0.5)
    virtue = FORGE_VIRTUES[virtue_key]

    if score <= VIRTUE_LOW_THRESHOLD:
        return {
            "virtue": virtue,
            "score": score,
            "type": "low",
            "patron_agent": virtue.patron_agents[0] if virtue.patron_agents else "hephaestus",
        }
    if score >= VIRTUE_HIGH_THRESHOLD:
        return {
            "virtue": virtue,
            "score": score,
            "type": "high",
            "patron_agent": virtue.patron_agents[0] if virtue.patron_agents else "hephaestus",
        }
    return None
