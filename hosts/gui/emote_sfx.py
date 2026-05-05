"""Emote SFX engine — maps *emote cues* in dialogue to real sound effects.

Extracts emote text from dialogue lines, resolves each to an SFX file
via keyword matching, and plays through AudioManager on a free channel.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from kourai_common.paths import audio_dir

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

# Root directory for SFX assets
_SFX_DIR = audio_dir(kind="sfx")

# Pattern for emote cues: *action text*
_EMOTE_RE = re.compile(r"\*([^*]+)\*")

# ---------------------------------------------------------------------------
# Keyword → SFX category mapping
# Each entry: (set of keywords, sfx_category)
# First match wins, so order matters for overlapping keywords.
# ---------------------------------------------------------------------------
_KEYWORD_MAP: list[tuple[set[str], str]] = [
    # Physical sounds
    ({"anvil", "strikes anvil", "slams"}, "anvil_strike"),
    ({"hammer", "sets hammer", "sets down hammer"}, "hammer_thud"),
    ({"knuckle", "cracks"}, "knuckle_crack"),
    ({"slides", "blueprint", "paper"}, "paper_slide"),
    ({"files nails", "filing"}, "nail_file"),
    ({"snaps fingers", "snap"}, "snap"),
    # Vocal reactions
    ({"grunt", "grunts"}, "grunt"),
    ({"sigh", "sighs"}, "sigh"),
    ({"scoff", "scoffs"}, "scoff"),
    ({"chuckle", "chuckles"}, "chuckle"),
    ({"giggle", "giggles"}, "giggle"),
    ({"laugh", "laughs"}, "laugh"),
    ({"snicker", "snickers"}, "snicker"),
    ({"hum", "hums"}, "hum"),
    ({"whisper", "whispers"}, "whisper"),
    ({"clears throat", "clear throat"}, "clear_throat"),
]


def extract_emotes(text: str) -> list[str]:
    """Pull all *emote cue* contents from a text string.

    Returns:
        List of emote contents (without the asterisks).
    """
    return _EMOTE_RE.findall(text)


def resolve_sfx(emote_text: str, agent_name: str | None = None) -> Path | None:
    """Map an emote string to an SFX file path.

    Checks for a per-agent override first, then falls back to the shared pool.

    Args:
        emote_text: The emote content (e.g. "strikes anvil").
        agent_name: Optional agent name for per-agent overrides.

    Returns:
        Path to the .ogg file, or None if no match / file missing.
    """
    lower = emote_text.lower().strip()

    category: str | None = None
    for keywords, cat in _KEYWORD_MAP:
        if any(kw in lower for kw in keywords):
            category = cat
            break

    if category is None:
        return None

    # Check per-agent override first
    if agent_name:
        agent_path = _SFX_DIR / agent_name / f"{category}.ogg"
        if agent_path.exists():
            return agent_path

    # Fall back to shared pool
    shared_path = _SFX_DIR / f"{category}.ogg"
    if shared_path.exists():
        return shared_path

    logger.debug("SFX file not found for category '%s' (emote: '%s')", category, emote_text)
    return None


def play_emote_sfx(
    text: str,
    agent_name: str | None,
    audio_manager: object,
) -> None:
    """Extract emotes from text and play matching SFX.

    Plays the first matched emote SFX to avoid overlapping sounds
    when multiple emotes appear in one line.

    Args:
        text: Dialogue text potentially containing *emote cues*.
        agent_name: Current speaking agent name.
        audio_manager: AudioManager instance with play_sfx() method.
    """
    emotes = extract_emotes(text)
    if not emotes:
        return

    for emote in emotes:
        sfx_path = resolve_sfx(emote, agent_name)
        if sfx_path:
            try:
                audio_manager.play_sfx(sfx_path)  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
                logger.debug("Emote SFX triggered: '%s' → %s", emote, sfx_path.stem)
            except Exception as e:
                logger.warning("Failed to play emote SFX for '%s': %s", emote, e)
            break  # one SFX per dialogue line to keep it clean
