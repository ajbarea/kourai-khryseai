"""Behavioral pattern detection for time-aware greetings and work-style personalization."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from kourai_common.player import add_player_memory, get_player_memories

log = logging.getLogger(__name__)

# ── Time-of-day pattern detection ────────────────────────────────────────

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
