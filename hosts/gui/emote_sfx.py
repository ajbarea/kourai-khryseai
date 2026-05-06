"""GUI emote-SFX playback wrapper.

The pure logic (``extract_emotes``, ``resolve_sfx``, the keyword → category
map, the regex) lives in :mod:`kourai_common.emote_sfx` so CLI and VN
hosts can opt in later. This module owns the GUI-specific playback path:
pull the first matched SFX path and hand it to the pygame AudioManager.

Existing GUI callers and tests continue to import ``extract_emotes`` and
``resolve_sfx`` from here unchanged — the names re-export from shared.
"""

from __future__ import annotations

import logging

from kourai_common.emote_sfx import extract_emotes, resolve_sfx

logger = logging.getLogger(__name__)


__all__ = ["extract_emotes", "play_emote_sfx", "resolve_sfx"]


def play_emote_sfx(
    text: str,
    agent_name: str | None,
    audio_manager: object,
) -> None:
    """Extract emotes from text and play the first matched SFX.

    Args:
        text: Dialogue potentially containing ``*emote cues*``.
        agent_name: Speaking agent for per-agent SFX overrides.
        audio_manager: ``AudioManager`` instance exposing ``play_sfx(path)``.
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
            break  # one SFX per dialogue line to keep the mix clean
