"""Classify incoming A2A messages into content tiers.

Pure functions, no GUI state. Moved from ``hosts/gui/message_classifier.py``
so CLI streaming and the VN bridge can route the same KIND_DIALOGUE-vs-
status decision through one set of regexes — both already do this work
inline today with overlapping patterns.

Tiers (matching the GUI dialogue panel's routing):
  * System status (Tier 3 pipeline chatter) → status bubbles / debug log
  * Scratchpad content (Tier 2 CoT/TODO) → agent scratchpad overlay
  * Everything else (Tier 1 dialogue) → dialogue history
"""

from __future__ import annotations

import re

import emoji

_SYSTEM_STATUS_RE = re.compile(
    r"^(?:Analyzing|Processing|Running|Building|Compiling|Testing|Checking|"
    r"Routing|Delegating|Preparing|Loading|Connecting|Waiting|Scanning|"
    r"Fetching|Generating|Deploying|Resolving|Verifying|Coding|Drafting|Writing)\b",
    re.IGNORECASE,
)


def is_system_status(text: str) -> bool:
    """Return True if text looks like transient pipeline chatter."""
    stripped = text.strip()
    stripped = emoji.replace_emoji(stripped, replace="").strip()

    if len(stripped) > 80:
        return False
    if "?" in stripped:
        return False
    if "INPUT_REQUIRED:" in stripped:
        return False

    # CoT/TODO plans have newlines + list / bullet markers — the dialogue
    # panel routes those to the scratchpad overlay instead of status bubbles.
    if "\n" in stripped and (
        "- " in stripped or "* " in stripped or "1. " in stripped or "TODO" in stripped.upper()
    ):
        return False

    return bool(_SYSTEM_STATUS_RE.match(stripped))


def is_scratchpad_content(text: str) -> bool:
    """Return True if text looks like a CoT plan or TODO list for the scratchpad."""
    stripped = text.strip()
    if is_system_status(text):
        return False
    return bool(
        "\n" in stripped
        and (
            "- " in stripped
            or "* " in stripped
            or "1. " in stripped
            or "TODO" in stripped.upper()
            or "[ ]" in stripped
            or "[x]" in stripped
        )
    )


__all__ = ["is_scratchpad_content", "is_system_status"]
