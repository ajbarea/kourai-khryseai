"""Affinity tracking and romance progression system.

Split from player.py for focused responsibility. Manages the agent_affinity
table — affinity scores, tier mapping, romance stage advancement, and
eligibility checking.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from kourai_common.player_constants import (
    AFFINITY_TIER_INSTRUCTIONS,
    AFFINITY_TIER_NAMES,
    ROMANCE_AFFINITY_THRESHOLD,
    ROMANCE_GOSSIP_THRESHOLD,
    ROMANCE_STAGES,
    _now_iso,
)
from kourai_common.player_memory import _get_player_db, get_player_memories

if TYPE_CHECKING:
    from kourai_common.player_profile import PlayerProfile

log = logging.getLogger(__name__)


# ── Affinity CRUD ───────────────────────────────────────────────────────


def get_affinity(player_id: str, agent_name: str) -> dict[str, Any]:
    """Get affinity data for a player-agent pair."""
    conn = _get_player_db()
    row = conn.execute(
        "SELECT affinity_score, interaction_count, last_interaction, romance_stage, "
        "memorable_quotes FROM agent_affinity WHERE player_id = ? AND agent_name = ?",
        (player_id, agent_name),
    ).fetchone()

    if row:
        return {
            "affinity_score": row[0],
            "interaction_count": row[1],
            "last_interaction": row[2],
            "romance_stage": row[3],
            "memorable_quotes": json.loads(row[4]) if row[4] else [],
        }

    return {
        "affinity_score": 0.0,
        "interaction_count": 0,
        "last_interaction": None,
        "romance_stage": "none",
        "memorable_quotes": [],
    }


def get_all_affinities(player_id: str) -> dict[str, dict[str, Any]]:
    """Get affinity data for all agents."""
    conn = _get_player_db()
    rows = conn.execute(
        "SELECT agent_name, affinity_score, interaction_count, last_interaction, "
        "romance_stage, memorable_quotes FROM agent_affinity WHERE player_id = ?",
        (player_id,),
    ).fetchall()

    return {
        row[0]: {
            "affinity_score": row[1],
            "interaction_count": row[2],
            "last_interaction": row[3],
            "romance_stage": row[4],
            "memorable_quotes": json.loads(row[5]) if row[5] else [],
        }
        for row in rows
    }


def update_affinity(
    player_id: str,
    agent_name: str,
    delta: float,
    alignment_multiplier: float = 1.0,
) -> float:
    """Update affinity score for a player-agent pair.

    Args:
        player_id: Player UUID.
        agent_name: Agent name.
        delta: Base affinity change (can be negative).
        alignment_multiplier: From PlayerProfile.alignment_compatibility().

    Returns:
        New affinity score.
    """
    conn = _get_player_db()
    current = get_affinity(player_id, agent_name)
    new_score = max(-1.0, min(1.0, current["affinity_score"] + delta * alignment_multiplier))
    now = _now_iso()

    conn.execute(
        """
        INSERT INTO agent_affinity (player_id, agent_name, affinity_score, interaction_count,
                                     last_interaction, romance_stage, memorable_quotes)
        VALUES (?, ?, ?, 1, ?, 'none', '[]')
        ON CONFLICT(player_id, agent_name) DO UPDATE SET
            affinity_score = ?,
            interaction_count = interaction_count + 1,
            last_interaction = ?
        """,
        (player_id, agent_name, new_score, now, new_score, now),
    )
    conn.commit()
    return new_score


def get_affinity_tier(affinity_score: float) -> int:
    """Map affinity score to dialogue tier.

    Returns:
        0 = Stranger, 1 = Acquaintance, 2 = Companion, 3 = Bonded.
    """
    if affinity_score >= 0.7:
        return 3  # Bonded
    if affinity_score >= 0.4:
        return 2  # Companion
    if affinity_score >= 0.15:
        return 1  # Acquaintance
    return 0  # Stranger


def get_affinity_tier_context(player_id: str, agent_name: str) -> str:
    """Build affinity tier context for prompt injection.

    Returns a concise instruction string telling the agent how to behave
    based on their relationship tier with this player.
    """
    aff = get_affinity(player_id, agent_name)
    tier = get_affinity_tier(aff["affinity_score"])
    tier_name = AFFINITY_TIER_NAMES[tier]
    instruction = AFFINITY_TIER_INSTRUCTIONS[tier]

    return (
        f"Affinity tier with this player: {tier_name} "
        f"({aff['interaction_count']} interactions).\n{instruction}"
    )


def advance_romance(player_id: str, agent_name: str) -> str | None:
    """Check and advance romance stage if conditions are met.

    Returns:
        New romance stage name if advanced, None if no change.
    """
    aff = get_affinity(player_id, agent_name)
    current_stage = aff["romance_stage"]
    current_idx = ROMANCE_STAGES.index(current_stage) if current_stage in ROMANCE_STAGES else 0

    if current_idx >= len(ROMANCE_STAGES) - 1:
        return None  # Already max

    if aff["affinity_score"] < ROMANCE_AFFINITY_THRESHOLD:
        return None  # Not bonded enough

    next_stage = ROMANCE_STAGES[current_idx + 1]
    conn = _get_player_db()
    conn.execute(
        "UPDATE agent_affinity SET romance_stage = ? WHERE player_id = ? AND agent_name = ?",
        (next_stage, player_id, agent_name),
    )
    conn.commit()
    log.info("Romance advanced: %s → %s with %s", current_stage, next_stage, agent_name)
    return next_stage


def check_romance_eligibility(
    player_id: str,
    agent_name: str,
    profile: PlayerProfile | None = None,
) -> dict[str, Any]:
    """Check whether a romance path can be unlocked with an agent.

    Full unlock conditions:
    1. Affinity tier 3 (Bonded) — affinity_score >= 0.7
    2. Alignment compatibility >= 1.0 (player in agent's preferred zone)
    3. At least ROMANCE_GOSSIP_THRESHOLD gossip-sourced memories
    4. Player hasn't opted out of romance content

    Returns:
        Dict with 'eligible' bool and detail about each condition.
    """
    # Lazy import to avoid circular dependency
    from kourai_common.player_profile import PlayerProfile

    if profile is None:
        profile = PlayerProfile.load()

    result: dict[str, Any] = {
        "eligible": False,
        "bonded": False,
        "alignment_compatible": False,
        "gossip_moments": 0,
        "romance_opted_out": True,
        "current_stage": "none",
    }

    if not profile:
        return result

    # Type narrow after None check
    if not isinstance(profile, PlayerProfile):
        raise TypeError("Expected 'profile' to be of type PlayerProfile")

    result["romance_opted_out"] = profile.romance_opted_out
    if profile.romance_opted_out:
        return result

    aff = get_affinity(player_id, agent_name)
    result["current_stage"] = aff["romance_stage"]

    # Condition 1: Bonded tier
    result["bonded"] = aff["affinity_score"] >= ROMANCE_AFFINITY_THRESHOLD

    # Condition 2: Alignment compatibility
    compat = profile.alignment_compatibility(agent_name)
    result["alignment_compatible"] = compat >= 1.0
    result["alignment_multiplier"] = compat

    # Condition 3: Gossip moments
    memories = get_player_memories(
        player_id, agent_name=agent_name, include_shared=False, limit=200
    )
    gossip_count = sum(1 for m in memories if m.get("source", "").startswith("gossip:"))
    result["gossip_moments"] = gossip_count

    result["eligible"] = (
        result["bonded"]
        and result["alignment_compatible"]
        and gossip_count >= ROMANCE_GOSSIP_THRESHOLD
    )

    return result


def try_advance_romance(
    player_id: str,
    agent_name: str,
    profile: PlayerProfile | None = None,
) -> str | None:
    """Attempt to advance romance, checking all eligibility conditions first.

    This is the recommended entry point for romance progression.
    Checks eligibility, then advances if conditions are met.

    Returns:
        New romance stage name if advanced, None otherwise.
    """
    eligibility = check_romance_eligibility(player_id, agent_name, profile)
    if not eligibility["eligible"]:
        return None

    return advance_romance(player_id, agent_name)


def get_active_romances(player_id: str) -> list[dict[str, Any]]:
    """Get all active romance relationships for a player.

    Returns:
        List of dicts with agent_name, romance_stage, and affinity_score.
    """
    all_aff = get_all_affinities(player_id)
    return [
        {
            "agent_name": agent_name,
            "romance_stage": aff["romance_stage"],
            "affinity_score": aff["affinity_score"],
        }
        for agent_name, aff in all_aff.items()
        if aff.get("romance_stage", "none") != "none"
    ]
