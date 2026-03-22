"""TTS threading helper — DRY wrapper for async speech playback.

Replaces ~6 identical threading.Thread(target=speak_sync, ...) blocks
scattered across __main__.py's recv_q processing.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tts_gui_integration import TTSGUIManager


def speak_async(
    text: str,
    agent_name: str,
    tts_manager: TTSGUIManager,
    *,
    force: bool = False,
) -> None:
    """Spawn a daemon thread to speak *text* via TTS.

    Args:
        text: The text to speak.
        agent_name: Agent voice to use.
        tts_manager: The GUI TTS manager (has .enable_tts and .tts_engine).
        force: When True, speak even if TTS is toggled off.
               Used for INPUT_REQUIRED questions the player must hear.
    """
    if tts_manager.tts_engine is None:
        return
    if not force and not tts_manager.enable_tts:
        return
    threading.Thread(
        target=tts_manager.tts_engine.speak_sync,
        args=(text,),
        kwargs={"agent_name": agent_name},
        daemon=True,
    ).start()
