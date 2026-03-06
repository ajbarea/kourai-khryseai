"""Post-task hooks for affinity tracking, memory extraction, alignment scoring, and patterns.

Called after each agent completes a task to update player affinity scores,
extract notable memories, score alignment points, and detect behavioral patterns.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from kourai_common.player import (
    PlayerProfile,
    add_player_memory,
    get_player_memories,
    update_affinity,
)

log = logging.getLogger(__name__)

# Base affinity delta per successful interaction
BASE_AFFINITY_DELTA = 0.02
# Additional affinity for tasks that reference the player by name
NAME_BONUS = 0.005

# ── Preference / achievement extraction patterns ────────────────────────

_PREFERENCE_PATTERNS = [
    re.compile(r"(?:I\s+(?:prefer|like|want|love|always|hate|never))\s+(.{10,80})", re.IGNORECASE),
    re.compile(r"(?:use|switch to|go with)\s+(\S+)\s+(?:instead|rather|from now)", re.IGNORECASE),
]
_ACHIEVEMENT_PATTERNS = [
    re.compile(r"all\s+\d+\s+tests?\s+pass", re.IGNORECASE),
    re.compile(r"build\s+succeed|all\s+clean", re.IGNORECASE),
    re.compile(r"first\s+time\s+(?:all|every)", re.IGNORECASE),
]

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

    from kourai_common.player import AGENT_ALIGNMENT_PREFERENCES

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


# ── Behavioral Pattern Detection ────────────────────────────────────────

# Time-of-day buckets
_TIME_BUCKETS = {
    "early_morning": (5, 8),  # 5:00–7:59
    "morning": (8, 12),  # 8:00–11:59
    "afternoon": (12, 17),  # 12:00–16:59
    "evening": (17, 21),  # 17:00–20:59
    "night": (21, 24),  # 21:00–23:59
    "late_night": (0, 5),  # 0:00–4:59
}


def get_time_bucket(hour: int | None = None) -> str:
    """Classify an hour (0–23) into a named time bucket."""
    if hour is None:
        hour = datetime.now(UTC).hour
    for name, (start, end) in _TIME_BUCKETS.items():
        if start <= hour < end:
            return name
    return "unknown"


def detect_time_pattern(player_id: str) -> dict[str, int]:
    """Analyze existing pattern memories to build a time-of-day histogram.

    Returns:
        Dict mapping time bucket names to session counts.
    """
    memories = get_player_memories(player_id, category="pattern", include_shared=True, limit=200)
    histogram: dict[str, int] = {}
    for mem in memories:
        content = mem.get("content", "")
        if content.startswith("session_time:"):
            bucket = content.split(":", 1)[1].strip()
            histogram[bucket] = histogram.get(bucket, 0) + 1
    return histogram


def record_session_pattern(player_id: str, hour: int | None = None) -> str | None:
    """Record the current session's time-of-day pattern.

    Call this once per session start. Stores a 'pattern' memory with the
    time bucket. Returns the bucket name, or None if already recorded
    for this bucket today.

    Args:
        player_id: Player UUID.
        hour: Override hour for testing (default: current UTC hour).

    Returns:
        Time bucket name if recorded, None if duplicate suppressed.
    """
    bucket = get_time_bucket(hour)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    content = f"session_time:{bucket}"
    tag = f"{content}:{today}"

    # Check if we already recorded this bucket today
    existing = get_player_memories(player_id, category="pattern", include_shared=True, limit=100)
    for mem in existing:
        if mem.get("source") == tag:
            return None  # Already recorded today

    mid = add_player_memory(
        player_id,
        content,
        category="pattern",
        importance=0.3,
        source=tag,
    )
    log.debug("Recorded session pattern: %s (id=%s)", bucket, mid[:8])
    return bucket


def get_session_greeting_hint(player_id: str, hour: int | None = None) -> str | None:
    """Generate a time-aware greeting hint for agents based on detected patterns.

    Returns a short hint string like "You're up late again~" if the player's
    current time bucket matches a strong pattern. Returns None if no notable
    pattern detected.
    """
    bucket = get_time_bucket(hour)
    histogram = detect_time_pattern(player_id)

    if not histogram:
        return None

    count = histogram.get(bucket, 0)
    total = sum(histogram.values())
    if total < 3:
        return None  # Not enough data

    ratio = count / total

    # If this time bucket is strongly dominant (>40% of sessions), note it
    if ratio > 0.4 and count >= 3:
        hints = {
            "late_night": "Player frequently works late at night — they're a night owl.",
            "early_morning": "Player is an early bird — often starts before dawn.",
            "night": "Player often codes in the evening hours.",
            "morning": "Player is a morning person — peak productivity before noon.",
            "afternoon": "Player usually works afternoon sessions.",
            "evening": "Player tends to work in the evening.",
        }
        return hints.get(bucket)

    return None


# ── Work pattern detection ──────────────────────────────────────────────

_WORK_PATTERNS = {
    "tests_first": re.compile(
        r"(?:write|add|create)\s+(?:the\s+)?tests?\s+(?:first|before)", re.IGNORECASE
    ),
    "refactor_lover": re.compile(r"refactor|restructure|reorganize|clean\s+up", re.IGNORECASE),
    "docs_writer": re.compile(r"document(?:ation)?|docstring|readme", re.IGNORECASE),
    "perfectionist": re.compile(r"(?:100|full)\s*%?\s*(?:coverage|test|lint)", re.IGNORECASE),
    "fast_shipper": re.compile(r"(?:ship|deploy|push)\s+(?:it|this|now|fast|quick)", re.IGNORECASE),
}


def detect_work_patterns(player_id: str, user_input: str) -> list[str]:
    """Detect work habit patterns from user input and record them.

    Returns:
        List of pattern names detected (e.g., ["tests_first", "perfectionist"]).
    """
    if not player_id or not user_input:
        return []

    detected: list[str] = []
    existing = get_player_memories(player_id, category="pattern", include_shared=True, limit=200)
    existing_content = {m["content"] for m in existing}

    for name, pattern in _WORK_PATTERNS.items():
        if pattern.search(user_input):
            content = f"work_habit:{name}"
            if content not in existing_content:
                add_player_memory(
                    player_id,
                    content,
                    category="pattern",
                    importance=0.5,
                    source="system_inferred",
                )
            detected.append(name)

    return detected


def get_work_pattern_summary(player_id: str) -> str | None:
    """Build a brief summary of detected work patterns for prompt injection.

    Returns a human-readable summary or None if no patterns detected.
    """
    memories = get_player_memories(player_id, category="pattern", include_shared=True, limit=200)
    habits: list[str] = []
    for mem in memories:
        content = mem.get("content", "")
        if content.startswith("work_habit:"):
            habit_name = content.split(":", 1)[1]
            labels = {
                "tests_first": "writes tests before implementation",
                "refactor_lover": "enjoys refactoring and clean code",
                "docs_writer": "values documentation",
                "perfectionist": "aims for perfection (full coverage, zero warnings)",
                "fast_shipper": "prefers to ship fast and iterate",
            }
            label = labels.get(habit_name, habit_name)
            if label not in habits:
                habits.append(label)

    if not habits:
        return None
    return "Work style: " + "; ".join(habits) + "."


# ── Original hooks (affinity + memory extraction) ───────────────────────


def track_interaction(
    player_id: str,
    agent_name: str,
    profile: PlayerProfile | None = None,
    success: bool = True,
) -> None:
    """Update affinity after an agent interaction.

    Call this after each pipeline step completes. The alignment compatibility
    multiplier is applied automatically.

    Args:
        player_id: Player UUID.
        agent_name: The agent that just completed work.
        profile: Player profile (loads from disk if not provided).
        success: Whether the task completed successfully.
    """
    if not player_id:
        return

    if profile is None:
        profile = PlayerProfile.load()
    if not profile:
        return

    delta = BASE_AFFINITY_DELTA if success else BASE_AFFINITY_DELTA * 0.3
    multiplier = profile.alignment_compatibility(agent_name)

    new_score = update_affinity(player_id, agent_name, delta, alignment_multiplier=multiplier)
    log.debug(
        "Affinity update: %s %+.3f (×%.2f) → %.3f",
        agent_name,
        delta,
        multiplier,
        new_score,
    )


def extract_memories_from_interaction(
    player_id: str,
    agent_name: str,
    user_input: str,
    agent_output: str,
) -> list[str]:
    """Heuristic memory extraction from a user-agent interaction.

    Looks for stated preferences, achievements, and notable patterns
    in the conversation text. Returns list of memory IDs created.

    Args:
        player_id: Player UUID.
        agent_name: Agent that handled this interaction.
        user_input: What the user said/requested.
        agent_output: What the agent produced.

    Returns:
        List of memory_id strings for any memories created.
    """
    if not player_id or not user_input:
        return []

    created: list[str] = []

    # Check for stated preferences in user input
    for pattern in _PREFERENCE_PATTERNS:
        match = pattern.search(user_input)
        if match:
            pref_text = match.group(0).strip()
            if len(pref_text) > 15:
                mid = add_player_memory(
                    player_id,
                    pref_text,
                    category="preference",
                    agent_name=agent_name,
                    importance=0.7,
                    source="agent_observed",
                )
                created.append(mid)
                log.debug("Extracted preference memory: %s", pref_text[:60])

    # Check for achievements in agent output
    for pattern in _ACHIEVEMENT_PATTERNS:
        if pattern.search(agent_output):
            achievement_text = f"Achievement during {agent_name} task: {pattern.pattern}"
            mid = add_player_memory(
                player_id,
                achievement_text,
                category="achievement",
                agent_name=agent_name,
                importance=0.8,
                source="system_inferred",
            )
            created.append(mid)
            break  # Only one achievement per interaction

    return created


# ── Unified post-task hook ──────────────────────────────────────────────


def run_post_task_hooks(
    player_id: str,
    agent_name: str,
    user_input: str,
    agent_output: str,
    success: bool = True,
) -> None:
    """Run all post-task hooks: affinity, alignment, memories, patterns.

    This is the primary integration point — call after each agent task completes.

    Args:
        player_id: Player UUID.
        agent_name: Agent that handled this task.
        user_input: Player's original request.
        agent_output: Agent's response/output.
        success: Whether the task succeeded.
    """
    if not player_id:
        return

    profile = PlayerProfile.load()
    if not profile:
        return

    # 1. Track affinity
    track_interaction(player_id, agent_name, profile=profile, success=success)

    # 2. Score alignment from player input
    score_alignment(user_input, profile)

    # 3. Extract memories
    extract_memories_from_interaction(player_id, agent_name, user_input, agent_output)

    # 4. Detect work patterns
    detect_work_patterns(player_id, user_input)

    # 5. Persist any alignment changes
    profile.save()
