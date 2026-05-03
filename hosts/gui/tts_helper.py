"""TTS threading helper — DRY wrapper for async speech playback.

Replaces ~6 identical threading.Thread(target=speak_sync, ...) blocks
scattered across __main__.py's recv_q processing.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from .tts_gui_integration import TTSGUIManager


def speak_async(
    text: str,
    agent_name: str,
    tts_manager: TTSGUIManager,
    *,
    force: bool = False,
    on_audio_start: Callable[[], None] | None = None,
    on_word: Callable[[object], None] | None = None,
) -> None:
    """Spawn a daemon thread to speak *text* via TTS.

    Args:
        text: The text to speak.
        agent_name: Agent voice to use.
        tts_manager: The GUI TTS manager (has .enable_tts and .tts_engine).
        force: When True, speak even if TTS is toggled off.
               Used for INPUT_REQUIRED questions the player must hear.
        on_audio_start: M20 sub-task 2 Tier 2 — fires when playback begins.
        on_word: M20 sub-task 2 Tier 1 — fires once per spoken word with
            a TimingInfo. Both callbacks dispatch from the daemon thread,
            so any GUI state they mutate must be safe under the GIL
            (typewriter cursor is a single int write — fine; richer state
            should use a queue back to the main loop).
    """
    if tts_manager.tts_engine is None:
        return
    if not force and not tts_manager.enable_tts:
        return
    threading.Thread(
        target=tts_manager.tts_engine.speak_sync,
        args=(text,),
        kwargs={
            "agent_name": agent_name,
            "on_audio_start": on_audio_start,
            "on_word": on_word,
        },
        daemon=True,
    ).start()
