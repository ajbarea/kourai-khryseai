"""Alignment scoring for player text: Sovereignty / Devotion / Gossip response.

Provides keyword/phrase heuristic scoring of player messages to increment the
player's alignment gauges (sovereignty vs devotion) and per-agent affinity
during gossip exchanges.
"""

from __future__ import annotations

import logging
import re

from kourai_common.player import AGENT_ALIGNMENT_PREFERENCES, PlayerProfile

log = logging.getLogger(__name__)

# ── Alignment scoring — keyword/phrase patterns ─────────────────────────

# Sovereignty signals: authority, perfectionism, strictness
_SOVEREIGNTY_STRONG: list[re.Pattern[str]] = [
    re.compile(r"get\s+back\s+to\s+work", re.IGNORECASE),
    re.compile(r"this\s+isn'?t\s+good\s+enough", re.IGNORECASE),
    re.compile(r"do\s+it\s+(?:again|now|exactly)", re.IGNORECASE),
    re.compile(r"I\s+(?:didn'?t|don'?t)\s+ask", re.IGNORECASE),
    re.compile(r"(?:rewrite|redo)\s+(?:this|it|that|the)", re.IGNORECASE),
    re.compile(r"not\s+acceptable", re.IGNORECASE),
    re.compile(r"(?:100|full|complete)\s*%?\s*(?:test|coverage)", re.IGNORECASE),
]
_SOVEREIGNTY_MILD: list[re.Pattern[str]] = [
    re.compile(r"do\s+it\s+(?:this|my)\s+way", re.IGNORECASE),
    re.compile(r"I\s+(?:want|need)\s+(?:it|this)\s+(?:exactly|precisely)", re.IGNORECASE),
    re.compile(r"(?:reject|no|nope|wrong|incorrect)", re.IGNORECASE),
    re.compile(r"fix\s+(?:this|it|that)", re.IGNORECASE),
    re.compile(r"strict(?:er|ly)?", re.IGNORECASE),
]

# Devotion signals: warmth, trust, encouragement
_DEVOTION_STRONG: list[re.Pattern[str]] = [
    re.compile(r"great\s+(?:job|work)", re.IGNORECASE),
    re.compile(r"(?:I\s+)?(?:believe|trust)\s+(?:in\s+)?you", re.IGNORECASE),
    re.compile(r"it'?s\s+ok(?:ay)?\b", re.IGNORECASE),
    re.compile(r"try\s+again", re.IGNORECASE),
    re.compile(r"(?:love|adore)\s+(?:it|this|what|how)", re.IGNORECASE),
    re.compile(r"you'?re?\s+(?:the\s+)?best", re.IGNORECASE),
    re.compile(r"thank\s+you\s+(?:so\s+)?much", re.IGNORECASE),
]
_DEVOTION_MILD: list[re.Pattern[str]] = [
    re.compile(r"(?:thanks|thank\s+you|good|nice|well\s+done)\b", re.IGNORECASE),
    re.compile(r"you\s+decide", re.IGNORECASE),
    re.compile(r"(?:show\s+me|surprise\s+me)", re.IGNORECASE),
    re.compile(r"(?:your\s+call|up\s+to\s+you)", re.IGNORECASE),
    re.compile(r"(?:sounds\s+good|looks\s+good|perfect)", re.IGNORECASE),
    re.compile(r"(?:please|pretty\s+please)", re.IGNORECASE),
]

# Flirty signals give mild devotion
_FLIRTY: list[re.Pattern[str]] = [
    re.compile(r"~$", re.MULTILINE),
    re.compile(r"\b(?:cutie?|babe|gorgeous|beautiful|pretty|lovely)\b", re.IGNORECASE),
    re.compile(r"(?:flirt|blush|wink)", re.IGNORECASE),
    re.compile(r"<3|❤|💕|😘|😍", re.IGNORECASE),
]

# Gossip-specific tone (for score_gossip_response)
_GOSSIP_SCOLD: list[re.Pattern[str]] = [
    re.compile(r"(?:get|go)\s+back\s+to\s+work", re.IGNORECASE),
    re.compile(r"shouldn'?t\s+you\s+be\s+working", re.IGNORECASE),
    re.compile(r"stop\s+(?:gossiping|chatting|talking)", re.IGNORECASE),
]

# Points awarded per match tier
_STRONG_POINTS = 3
_MILD_POINTS = 1
_FLIRT_POINTS = 2  # Devotion from flirting


def score_alignment(
    text: str,
    profile: PlayerProfile,
    *,
    context: str = "task",
) -> tuple[int, int]:
    """Classify player text and award Sovereignty/Devotion points.

    Uses heuristic keyword matching on the player's input text.
    Mutates the profile in-place (adds points) and returns the deltas.

    Args:
        text: Player's message text to analyze.
        profile: Player profile (sovereignty/devotion updated in-place).
        context: "task" (default) or "gossip" — gossip responses score higher.

    Returns:
        (sovereignty_delta, devotion_delta) tuple of points awarded.
    """
    if not text.strip():
        return (0, 0)

    sov_delta = 0
    dev_delta = 0

    # Check sovereignty patterns
    for pat in _SOVEREIGNTY_STRONG:
        if pat.search(text):
            sov_delta += _STRONG_POINTS
            break  # Only count one strong per category
    for pat in _SOVEREIGNTY_MILD:
        if pat.search(text):
            sov_delta += _MILD_POINTS
            break

    # Check devotion patterns
    for pat in _DEVOTION_STRONG:
        if pat.search(text):
            dev_delta += _STRONG_POINTS
            break
    for pat in _DEVOTION_MILD:
        if pat.search(text):
            dev_delta += _MILD_POINTS
            break

    # Flirting → devotion bonus
    for pat in _FLIRTY:
        if pat.search(text):
            dev_delta += _FLIRT_POINTS
            break

    # Gossip context amplifier: responses in gossip carry 50% more weight
    if context == "gossip":
        sov_delta = int(sov_delta * 1.5)
        dev_delta = int(dev_delta * 1.5)

    # Apply to profile
    if sov_delta:
        profile.add_sovereignty(sov_delta)
    if dev_delta:
        profile.add_devotion(dev_delta)

    if sov_delta or dev_delta:
        log.debug(
            "Alignment scored: sov %+d → %d, dev %+d → %d (ctx=%s)",
            sov_delta,
            profile.sovereignty,
            dev_delta,
            profile.devotion,
            context,
        )

    return (sov_delta, dev_delta)


def score_gossip_response(
    text: str,
    profile: PlayerProfile,
    gossip_agents: list[str],
) -> tuple[int, int, dict[str, float]]:
    """Score a player's gossip response for alignment + per-agent affinity effects.

    In gossip, the player's tone affects both alignment gauges AND affinity
    with the agents involved in the gossip conversation.

    Args:
        text: Player's gossip response text.
        profile: Player profile (mutated in-place).
        gossip_agents: Names of agents in the gossip conversation.

    Returns:
        (sovereignty_delta, devotion_delta, affinity_deltas) where affinity_deltas
        maps agent_name → affinity change.
    """
    sov, dev = score_alignment(text, profile, context="gossip")

    # Determine per-agent affinity effects based on tone
    affinity_deltas: dict[str, float] = {}
    is_scolding = any(pat.search(text) for pat in _GOSSIP_SCOLD)
    is_flirting = any(pat.search(text) for pat in _FLIRTY)
    is_warm = dev > 0

    for agent in gossip_agents:
        delta = 0.01  # Base small positive for engaging at all
        prefs = AGENT_ALIGNMENT_PREFERENCES.get(agent, {})

        if is_scolding:
            # Authority-preferring agents respect scolding; devotion-preferring are hurt
            if prefs.get("sovereignty", 0) > 0.3:
                delta += 0.02  # Dokimasia, Hephaestus respect it
            elif prefs.get("devotion", 0) > 0.5:
                delta -= 0.02  # Kallos, Mneme are hurt

        if is_flirting:
            if prefs.get("devotion", 0) > 0.3:
                delta += 0.03  # Most maidens like flirting
            else:
                delta += 0.01  # Hephaestus is awkward but not offended

        if is_warm and not is_flirting:
            delta += 0.015  # General warmth is universally mild-positive

        affinity_deltas[agent] = round(delta, 4)

    return (sov, dev, affinity_deltas)
