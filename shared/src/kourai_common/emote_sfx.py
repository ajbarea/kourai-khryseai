"""Shared emote-SFX engine — maps ``*emote cue*`` text to SFX file paths.

Extracts ``*action text*`` cues from dialogue lines and resolves each to
a real ``assets/audio/sfx/<category>.ogg`` path via keyword matching.
The host-specific playback bindings (pygame AudioManager for the GUI,
no-op for the CLI today, ``renpy.sound.play`` for the VN if it ever
wires one) stay in each host's own module — this layer is pure data.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from kourai_common.paths import audio_dir

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

# Root directory for SFX assets.
_SFX_DIR = audio_dir(kind="sfx")

# Pattern for emote cues: ``*action text*``.
_EMOTE_RE = re.compile(r"\*([^*]+)\*")

# Keyword → SFX category mapping. First match wins, so order matters for
# overlapping keywords (e.g., "anvil" must precede "hammer" to ensure
# "strikes the anvil with the hammer" lands on anvil_strike).
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
    """Pull all ``*emote cue*`` contents from a text string."""
    return _EMOTE_RE.findall(text)


def resolve_sfx(emote_text: str, agent_name: str | None = None) -> Path | None:
    """Map an emote string to an SFX file path.

    Checks a per-agent override directory first
    (``assets/audio/sfx/<agent>/<category>.ogg``); falls back to the shared
    pool (``assets/audio/sfx/<category>.ogg``). Returns ``None`` if the
    keyword doesn't match any category or no on-disk SFX exists.
    """
    lower = emote_text.lower().strip()

    category: str | None = None
    for keywords, cat in _KEYWORD_MAP:
        if any(kw in lower for kw in keywords):
            category = cat
            break

    if category is None:
        return None

    if agent_name:
        agent_path = _SFX_DIR / agent_name / f"{category}.ogg"
        if agent_path.exists():
            return agent_path

    shared_path = _SFX_DIR / f"{category}.ogg"
    if shared_path.exists():
        return shared_path

    logger.debug("SFX file not found for category '%s' (emote: '%s')", category, emote_text)
    return None


__all__ = ["extract_emotes", "resolve_sfx"]
