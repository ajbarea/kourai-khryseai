"""Achievement system for Kourai Khryseai.

Tracks player accomplishments across task, gossip, alignment, and romance
categories. Achievements are defined declaratively and evaluated after each
interaction via check_achievements().

Storage: player_memories table with category='achievement'.
Achievement definitions are checked against live player state + history.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from kourai_common.player import (
    PlayerProfile,
    add_player_memory,
    get_active_romances,
    get_all_affinities,
    get_player_memories,
)

log = logging.getLogger(__name__)


# ── Achievement Definitions ─────────────────────────────────────────────


@dataclass(frozen=True)
class AchievementDef:
    """Definition of an achievement the player can earn."""

    id: str
    name: str
    description: str
    emoji: str
    category: str  # "task", "gossip", "alignment", "romance", "social", "meta"
    hidden: bool = False  # Hidden achievements aren't shown until unlocked


# All achievement definitions — evaluated by check_achievements().
ACHIEVEMENTS: dict[str, AchievementDef] = {}


def _register(*defs: AchievementDef) -> None:
    for d in defs:
        ACHIEVEMENTS[d.id] = d


# ── Task achievements ──────────────────────────────────────────────────
_register(
    AchievementDef(
        "first_forge",
        "First Forge",
        "Complete your first task pipeline.",
        "🔨",
        "task",
    ),
    AchievementDef(
        "hundred_hammers",
        "Hundred Hammers",
        "Complete 100 tasks.",
        "💯",
        "task",
    ),
    AchievementDef(
        "thousand_hammers",
        "Thousand Hammers",
        "Complete 1000 tasks.",
        "⚒️",
        "task",
        hidden=True,
    ),
    AchievementDef(
        "night_owl",
        "Night Owl",
        "Start 10 sessions after midnight.",
        "🦉",
        "task",
    ),
    AchievementDef(
        "early_bird",
        "Early Bird",
        "Start 10 sessions before 7 AM.",
        "🐦",
        "task",
    ),
    AchievementDef(
        "full_pipeline",
        "Full Pipeline",
        "Used all 5 specialist agents in one session.",
        "🔗",
        "task",
    ),
)

# ── Gossip achievements ────────────────────────────────────────────────
_register(
    AchievementDef(
        "first_gossip",
        "Eavesdropper",
        "Witness your first gossip session.",
        "👂",
        "gossip",
    ),
    AchievementDef(
        "gossip_monarch",
        "Gossip Monarch",
        "Engage with 50 gossip sessions.",
        "👑",
        "gossip",
    ),
    AchievementDef(
        "heartbreaker",
        "Heartbreaker",
        "Get rejected while flirting by 3 different agents.",
        "💔",
        "gossip",
        hidden=True,
    ),
    AchievementDef(
        "taskmaster",
        "Taskmaster",
        "Scold agents back to work 10 times.",
        "📋",
        "gossip",
    ),
    AchievementDef(
        "social_butterfly",
        "Social Butterfly",
        "Join 20 gossip sessions.",
        "🦋",
        "gossip",
    ),
)

# ── Alignment achievements ─────────────────────────────────────────────
_register(
    AchievementDef(
        "iron_fist",
        "Iron Fist",
        "Reach Sovereignty 80.",
        "🔴",
        "alignment",
    ),
    AchievementDef(
        "heart_of_gold",
        "Heart of Gold",
        "Reach Devotion 80.",
        "🔵",
        "alignment",
    ),
    AchievementDef(
        "the_commander",
        "The Commander",
        "Reach 80 in BOTH Sovereignty and Devotion.",
        "👑",
        "alignment",
    ),
    AchievementDef(
        "first_steps",
        "First Steps",
        "Earn your first alignment points.",
        "👣",
        "alignment",
    ),
)

# ── Romance achievements ──────────────────────────────────────────────
_register(
    AchievementDef(
        "first_spark",
        "First Spark",
        "Unlock your first romance path.",
        "💕",
        "romance",
    ),
    AchievementDef(
        "eternal_flame",
        "Eternal Flame",
        "Reach Bonfire stage with an agent.",
        "🔥",
        "romance",
    ),
    AchievementDef(
        "harem_protagonist",
        "Harem Protagonist",
        "Have 3+ active romances simultaneously.",
        "💘",
        "romance",
        hidden=True,
    ),
    AchievementDef(
        "ride_or_die",
        "Ride or Die",
        "Reach Bonfire with one agent without romancing any others.",
        "💍",
        "romance",
    ),
)

# ── Social achievements ───────────────────────────────────────────────
_register(
    AchievementDef(
        "everyones_friend",
        "Everyone's Friend",
        "Reach Companion tier with all agents.",
        "🤝",
        "social",
    ),
    AchievementDef(
        "bonded_pair",
        "Bonded Pair",
        "Reach Bonded tier with any agent.",
        "🔗",
        "social",
    ),
    AchievementDef(
        "inner_circle",
        "Inner Circle",
        "Reach Bonded tier with 3+ agents.",
        "⭐",
        "social",
    ),
)


# ── Achievement Checking ───────────────────────────────────────────────


def get_unlocked_achievements(player_id: str) -> set[str]:
    """Get the set of achievement IDs the player has already unlocked."""
    mems = get_player_memories(player_id, category="achievement", limit=500)
    unlocked = set()
    for mem in mems:
        content = mem.get("content", "")
        if content.startswith("achievement:"):
            unlocked.add(content.split(":", 1)[1])
    return unlocked


def _unlock_achievement(player_id: str, achievement_id: str) -> str:
    """Unlock an achievement and store it as a memory."""
    ach = ACHIEVEMENTS[achievement_id]
    memory_id = add_player_memory(
        player_id,
        f"achievement:{achievement_id}",
        category="achievement",
        importance=0.9,
        source="system_inferred",
    )
    log.info(
        "Achievement unlocked: %s %s — %s",
        ach.emoji,
        ach.name,
        ach.description,
    )
    return memory_id


def check_achievements(
    player_id: str,
    profile: PlayerProfile | None = None,
    context: dict[str, Any] | None = None,
) -> list[AchievementDef]:
    """Check and unlock any newly earned achievements.

    Call this after post-task hooks run. It evaluates all achievement
    conditions against the player's current state and history.

    Args:
        player_id: Player UUID.
        profile: Player profile (loaded if not provided).
        context: Optional dict with extra context:
            - "agents_used_this_session": set[str] of agent names
            - "gossip_sessions": int count of total gossip sessions
            - "gossip_joins": int count of times player joined gossip
            - "scold_count": int count of times player scolded agents
            - "session_hour": int (0-23) hour when session started

    Returns:
        List of newly unlocked AchievementDefs.
    """
    if not player_id:
        return []

    if profile is None:
        profile = PlayerProfile.load()
    if not profile:
        return []

    already = get_unlocked_achievements(player_id)
    newly_unlocked: list[AchievementDef] = []
    ctx = context or {}

    def _try_unlock(aid: str) -> bool:
        if aid in already:
            return False
        _unlock_achievement(player_id, aid)
        newly_unlocked.append(ACHIEVEMENTS[aid])
        already.add(aid)
        return True

    # Task achievements
    total_interactions = sum(
        a.get("interaction_count", 0) for a in get_all_affinities(player_id).values()
    )

    if total_interactions >= 1:
        _try_unlock("first_forge")
    if total_interactions >= 100:
        _try_unlock("hundred_hammers")
    if total_interactions >= 1000:
        _try_unlock("thousand_hammers")

    session_hour = ctx.get("session_hour")
    if session_hour is not None:
        # Check time-based patterns from memories
        night_mems = [
            m
            for m in get_player_memories(player_id, category="pattern", limit=500)
            if "time_of_day:night" in m.get("content", "")
        ]
        if len(night_mems) >= 10 or (0 <= session_hour < 5):
            night_mems_count = len(night_mems) + (1 if 0 <= session_hour < 5 else 0)
            if night_mems_count >= 10:
                _try_unlock("night_owl")

        early_mems = [
            m
            for m in get_player_memories(player_id, category="pattern", limit=500)
            if "time_of_day:early_morning" in m.get("content", "")
        ]
        if len(early_mems) >= 10:
            _try_unlock("early_bird")

    agents_used = ctx.get("agents_used_this_session", set())
    specialists = {"metis", "techne", "dokimasia", "kallos", "mneme"}
    if specialists.issubset(agents_used):
        _try_unlock("full_pipeline")

    # Gossip achievements
    gossip_sessions = ctx.get("gossip_sessions", 0)
    gossip_joins = ctx.get("gossip_joins", 0)
    scold_count = ctx.get("scold_count", 0)

    if gossip_sessions >= 1:
        _try_unlock("first_gossip")
    if gossip_sessions >= 50:
        _try_unlock("gossip_monarch")
    if gossip_joins >= 20:
        _try_unlock("social_butterfly")
    if scold_count >= 10:
        _try_unlock("taskmaster")

    # Alignment achievements
    if profile.sovereignty > 0 or profile.devotion > 0:
        _try_unlock("first_steps")
    if profile.sovereignty >= 80:
        _try_unlock("iron_fist")
    if profile.devotion >= 80:
        _try_unlock("heart_of_gold")
    if profile.sovereignty >= 80 and profile.devotion >= 80:
        _try_unlock("the_commander")

    # Romance achievements
    romances = get_active_romances(player_id)
    if romances:
        _try_unlock("first_spark")
    if any(r["romance_stage"] == "bonfire" for r in romances):
        _try_unlock("eternal_flame")
    if len(romances) >= 3:
        _try_unlock("harem_protagonist")
    if len(romances) == 1 and romances[0]["romance_stage"] == "bonfire":
        _try_unlock("ride_or_die")

    # Social achievements
    all_aff = get_all_affinities(player_id)
    from kourai_common.player import get_affinity_tier

    tier_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    for aff in all_aff.values():
        tier = get_affinity_tier(aff["affinity_score"])
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    if any(aff["affinity_score"] >= 0.7 for aff in all_aff.values()):
        _try_unlock("bonded_pair")
    if tier_counts.get(3, 0) >= 3:
        _try_unlock("inner_circle")
    if len(all_aff) >= 5 and all(
        get_affinity_tier(a["affinity_score"]) >= 2 for a in all_aff.values()
    ):
        _try_unlock("everyones_friend")

    if newly_unlocked:
        log.info(
            "Player %s unlocked %d achievement(s): %s",
            player_id[:8],
            len(newly_unlocked),
            ", ".join(a.name for a in newly_unlocked),
        )

    return newly_unlocked


def get_achievement_progress(
    player_id: str, profile: PlayerProfile | None = None
) -> dict[str, Any]:
    """Get a summary of achievement progress for display.

    Returns:
        Dict with total, unlocked count, achievements by category, etc.
    """
    if profile is None:
        profile = PlayerProfile.load()

    unlocked = get_unlocked_achievements(player_id)
    total = len(ACHIEVEMENTS)
    visible = [a for a in ACHIEVEMENTS.values() if not a.hidden or a.id in unlocked]

    by_category: dict[str, list[dict[str, Any]]] = {}
    for ach in visible:
        entry = {
            "id": ach.id,
            "name": ach.name,
            "emoji": ach.emoji,
            "description": ach.description,
            "unlocked": ach.id in unlocked,
        }
        by_category.setdefault(ach.category, []).append(entry)

    return {
        "total": total,
        "unlocked_count": len(unlocked),
        "visible_count": len(visible),
        "by_category": by_category,
    }


def format_achievement_notification(achievement: AchievementDef) -> str:
    """Format a notification string for a newly unlocked achievement."""
    return f"🏆 Achievement Unlocked: {achievement.emoji} {achievement.name} — {achievement.description}"
