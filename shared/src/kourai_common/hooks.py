"""Post-task hook orchestration entrypoint."""

from __future__ import annotations

from typing import Any

from kourai_common.hooks_alignment import (
    score_alignment,
)
from kourai_common.hooks_interaction import extract_memories_from_interaction, track_interaction
from kourai_common.hooks_patterns import (
    detect_work_patterns,
)

__all__ = ["run_post_task_hooks"]


def run_post_task_hooks(
    player_id: str,
    agent_name: str,
    user_input: str,
    agent_output: str,
    success: bool = True,
) -> dict[str, Any]:
    """Run all post-task hooks: affinity, alignment, memories, patterns, romance.

    This is the primary integration point — call after each agent task completes.

    Args:
        player_id: Player UUID.
        agent_name: Agent that handled this task.
        user_input: Player's original request.
        agent_output: Agent's response/output.
        success: Whether the task succeeded.

    Returns:
        Dict with hook results (romance_advanced, memories_created, etc.).
        Empty dict if no profile.
    """
    if not player_id:
        return {}

    from kourai_common.player import PlayerProfile

    profile = PlayerProfile.load(player_id)
    if not profile:
        return {}

    results: dict[str, Any] = {}
    metrics_enabled = bool(profile.preferences.get("metrics_tracking_enabled", True))
    if not metrics_enabled:
        results["metrics_tracking_enabled"] = False
        return results

    results["metrics_tracking_enabled"] = True

    # 1. Track affinity
    track_interaction(player_id, agent_name, profile=profile, success=success)

    # 2. Score alignment from player input
    sov, dev = score_alignment(user_input, profile)
    results["alignment_delta"] = {"sovereignty": sov, "devotion": dev}

    # 3. Extract memories
    memory_ids = extract_memories_from_interaction(player_id, agent_name, user_input, agent_output)
    results["memories_created"] = memory_ids

    # 4. Detect work patterns
    patterns = detect_work_patterns(player_id, user_input)
    results["patterns_detected"] = patterns

    # 5. Check romance progression
    from kourai_common.player import try_advance_romance

    new_stage = try_advance_romance(player_id, agent_name, profile)
    results["romance_advanced"] = new_stage

    # 6. Persist any alignment changes
    profile.save()

    # 7. Check achievements
    try:
        from kourai_common.achievements import check_achievements

        new_achievements = check_achievements(player_id, profile)
        results["achievements_unlocked"] = [a.id for a in new_achievements]
    except Exception:
        results["achievements_unlocked"] = []

    return results
