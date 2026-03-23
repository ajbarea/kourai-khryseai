"""Companion spirit helpers — Puck & Cupid logic.

Pure functions for companion spirit gameplay mechanics, used by both
the Ren'Py VN and testable in isolation.

Spec: designs/COMPANION_SPIRITS.md
"""

from __future__ import annotations


def minigame_affinity_gain(base_gain: float, minigames_won: int) -> float:
    """Exponential decay on minigame affinity gains to prevent power-leveling.

    Organic conversation always gives full gains. Minigame gains decay
    by 0.8^n per minigame won, ensuring engagement with the forge is
    the primary path to deep relationships.

    Args:
        base_gain: The nominal affinity gain for the minigame.
        minigames_won: Total minigames won so far (across all agents).

    Returns:
        Discounted affinity gain, minimum 0.0.
    """
    if minigames_won < 0:
        return max(0.0, base_gain)
    return max(0.0, base_gain * (0.8**minigames_won))


def should_show_vulnerability(
    affinity_score: float,
    turn_counter: int,
    last_vulnerability_turn: int,
    romance_mode: bool,
    cooldown_turns: int = 8,
) -> bool:
    """Whether to show the Cupid vulnerability moment screen.

    Fires when the player is in a warm/intimate relationship AND has had
    enough turns since the last vulnerability moment to avoid spam.
    Only fires when romance mode is on — if the player opted out, Cupid
    stays quiet.

    Args:
        affinity_score: Current affinity with the active agent (0.0–1.0).
        turn_counter: Current global turn counter.
        last_vulnerability_turn: Turn when vulnerability last fired for this agent.
        romance_mode: Whether the player has enabled romance mode.
        cooldown_turns: Minimum turns between vulnerability moments (default 8).

    Returns:
        True if the vulnerability screen should fire.
    """
    if not romance_mode:
        return False
    if affinity_score < 0.70:
        return False
    return turn_counter - last_vulnerability_turn >= cooldown_turns


def should_show_puck_nudge(
    turn_counter: int,
    last_nudge_turn: int,
    unengaged_count: int,
    min_turns: int = 5,
    cooldown: int = 4,
) -> bool:
    """Whether to show a Puck nudge.

    Fires when ≥2 agents are still at default affinity after min_turns,
    with cooldown between nudges.

    Args:
        turn_counter: Current global turn counter.
        last_nudge_turn: Turn when the last nudge fired.
        unengaged_count: Number of agents at or below default affinity.
        min_turns: Turns before first nudge fires (default 5).
        cooldown: Minimum turns between nudges (default 4).

    Returns:
        True if the nudge screen should fire.
    """
    if unengaged_count < 2:
        return False
    if turn_counter < min_turns:
        return False
    return turn_counter - last_nudge_turn >= cooldown
