"""Player data import/export for portability and backup."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from kourai_common.player_constants import _now_iso
from kourai_common.player_memory import (
    _get_player_db,
    get_player_memories,
    wipe_player_memories,
)
from kourai_common.player_profile import PlayerProfile

log = logging.getLogger(__name__)


# ── Profile Export / Import ─────────────────────────────────────────────


def export_player_data(player_id: str) -> dict[str, Any]:
    """Export complete player data for portability.

    Returns a dict with profile, memories, and affinities that can be
    serialized to JSON for backup or transfer.
    """
    from kourai_common.player_affinity import get_all_affinities

    profile = PlayerProfile.load(player_id)
    if not profile:
        return {}

    memories = get_player_memories(player_id, include_shared=True, limit=10000)
    affinities = get_all_affinities(player_id)

    return {
        "version": 1,
        "profile": profile.to_dict(),
        "memories": memories,
        "affinities": affinities,
    }


def import_player_data(data: dict[str, Any], *, merge: bool = False) -> PlayerProfile:
    """Import player data from an export bundle.

    Args:
        data: Export dict from export_player_data().
        merge: If True, merge memories into existing profile.
            If False, wipe and replace everything.

    Returns:
        The imported PlayerProfile.
    """
    if data.get("version") != 1:
        raise ValueError(f"Unsupported export version: {data.get('version')}")

    profile_data = data.get("profile", {})
    if not profile_data:
        raise ValueError("Export data missing profile")

    profile = PlayerProfile.from_dict(profile_data)

    if not merge:
        wipe_player_memories(profile.player_id)

    profile.save()

    conn = _get_player_db()

    # Import memories
    for mem in data.get("memories", []):
        existing = conn.execute(
            "SELECT 1 FROM player_memories WHERE player_id = ? AND content = ? AND agent_name IS ?",
            (profile.player_id, mem["content"], mem.get("agent_name")),
        ).fetchone()
        if existing:
            continue
        conn.execute(
            """
            INSERT INTO player_memories
                (memory_id, player_id, agent_name, category, content, importance,
                 access_count, created_at, last_accessed, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid4().hex,
                profile.player_id,
                mem.get("agent_name"),
                mem["category"],
                mem["content"],
                mem.get("importance", 0.5),
                mem.get("access_count", 0),
                mem.get("created_at", _now_iso()),
                mem.get("last_accessed", _now_iso()),
                mem.get("source", "imported"),
            ),
        )

    # Import affinities
    for agent_name, aff in data.get("affinities", {}).items():
        conn.execute(
            """
            INSERT INTO agent_affinity
                (player_id, agent_name, affinity_score, interaction_count,
                 last_interaction, romance_stage, memorable_quotes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_id, agent_name) DO UPDATE SET
                affinity_score = ?,
                interaction_count = ?,
                romance_stage = ?
            """,
            (
                profile.player_id,
                agent_name,
                aff.get("affinity_score", 0.0),
                aff.get("interaction_count", 0),
                aff.get("last_interaction"),
                aff.get("romance_stage", "none"),
                json.dumps(aff.get("memorable_quotes", [])),
                aff.get("affinity_score", 0.0),
                aff.get("interaction_count", 0),
                aff.get("romance_stage", "none"),
            ),
        )

    conn.commit()
    log.info(
        "Imported player data: %d memories, %d affinities (merge=%s)",
        len(data.get("memories", [])),
        len(data.get("affinities", {})),
        merge,
    )
    return profile
