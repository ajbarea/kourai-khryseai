"""Integration of TTS and dialogue pacing into the GUI.

Handles voice playback, pacing, and agent personality in the main dialogue loop.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING

from dialogue_pacing import DialoguePacer, PacingConfig, PacingMode
from tts_engine import TTSEngine

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import queue as _queue


class TTSGUIManager:
    """Manages TTS playback and dialogue pacing in the GUI."""

    def __init__(
        self,
        recv_q: _queue.Queue[dict],
        enable_tts: bool = True,
        pacing_mode: PacingMode = PacingMode.NORMAL,
    ):
        """Initialize the TTS GUI manager.

        Args:
            recv_q: Queue for GUI events (from client).
            enable_tts: Whether to enable text-to-speech.
            pacing_mode: Initial dialogue pacing mode.
        """
        self.recv_q = recv_q
        self.enable_tts = enable_tts
        self.tts_engine = TTSEngine() if enable_tts else None
        self.pacer = DialoguePacer(PacingConfig(mode=pacing_mode))
        self._tts_thread: threading.Thread | None = None
        self._current_agent: str | None = None
        logger.info(
            f"TTSGUIManager initialized: enable_tts={enable_tts}, pacing_mode={pacing_mode.name}"
        )

    def set_tts_enabled(self, enabled: bool) -> None:
        """Enable or disable TTS."""
        self.enable_tts = enabled
        if enabled and self.tts_engine is None:
            self.tts_engine = TTSEngine()
            logger.info("TTS enabled")
        elif not enabled and self.tts_engine:
            self.tts_engine.stop()
            logger.info("TTS disabled")

    def set_pacing_mode(self, mode: PacingMode) -> None:
        """Change dialogue pacing mode."""
        self.pacer.set_mode(mode)
        logger.debug(f"Pacing mode changed to {mode.name}")

    def set_current_agent(self, agent_name: str) -> None:
        """Set the current speaking agent."""
        self._current_agent = agent_name
        logger.debug(f"Current agent set to {agent_name}")

    async def process_dialogue_event(self, event: dict) -> None:
        """Process a dialogue event with TTS and pacing.

        Args:
            event: Event dict from client (status, result, etc).
        """
        event_type = event.get("type")
        logger.debug(f"Processing dialogue event: type={event_type}")

        if event_type == "status":
            # Agent is thinking/processing
            text = event.get("text", "")
            if text:
                logger.debug(f"Status event with text: {text[:50]}...")
                await self.pacer.wait_before_response()
                if self.enable_tts and self.tts_engine:
                    await self._speak_async(text, self._current_agent)

        elif event_type == "result":
            # Final response
            text = event.get("text", "")
            if text:
                logger.debug(f"Result event with text: {text[:50]}...")
                await self.pacer.wait_between_responses()
                if self.enable_tts and self.tts_engine:
                    await self._speak_async(text, self._current_agent)

    async def _speak_async(
        self,
        text: str,
        agent_name: str | None = None,
        speed: float | None = None,
        pitch: float | None = None,
    ) -> None:
        """Speak text asynchronously in a thread pool.

        Args:
            text: Text to speak.
            agent_name: Agent name for voice selection.
            speed: Voice speed override.
            pitch: Voice pitch override.
        """
        if not self.tts_engine:
            logger.warning("TTS engine not initialized, skipping _speak_async")
            return

        logger.info(f"_speak_async: agent={agent_name}, text_len={len(text)}")
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                self.tts_engine.speak_sync,
                text,
                agent_name,
                None,  # voice_key (use auto-detection)
                speed,
                pitch,
            )
        except Exception as e:
            logger.error(f"_speak_async error: {e}", exc_info=True)

    def cleanup(self) -> None:
        """Clean up TTS resources."""
        logger.info("TTSGUIManager cleanup")
        if self.tts_engine:
            self.tts_engine.stop()
            self.tts_engine.cleanup()


class TTSSettingsPanel:
    """UI panel for TTS and pacing settings."""

    def __init__(self, manager: TTSGUIManager):
        """Initialize settings panel.

        Args:
            manager: TTSGUIManager instance to control.
        """
        self.manager = manager

    def get_settings_dict(self) -> dict:
        """Get current TTS settings as dict."""
        return {
            "tts_enabled": self.manager.enable_tts,
            "master_volume": self.manager.tts_engine.master_volume
            if self.manager.tts_engine
            else 0.8,
            "enable_effects": self.manager.tts_engine.enable_effects
            if self.manager.tts_engine
            else True,
            "pacing_mode": self.manager.pacer.config.mode.name,
            "thinking_pause": self.manager.pacer.config.enable_thinking_pause,
            "thinking_pause_duration": self.manager.pacer.config.thinking_pause_duration,
            "min_chars_per_second": self.manager.pacer.config.min_chars_per_second,
        }

    def apply_settings(self, settings: dict) -> None:
        """Apply TTS settings from dict.

        Args:
            settings: Settings dict with keys like 'tts_enabled', 'master_volume', etc.
        """
        if "tts_enabled" in settings:
            self.manager.set_tts_enabled(settings["tts_enabled"])

        if "master_volume" in settings and self.manager.tts_engine:
            self.manager.tts_engine.set_master_volume(settings["master_volume"])

        if "enable_effects" in settings and self.manager.tts_engine:
            self.manager.tts_engine.enable_effects = settings["enable_effects"]

        if "pacing_mode" in settings:
            mode_name = settings["pacing_mode"]
            try:
                mode = PacingMode[mode_name]
                self.manager.set_pacing_mode(mode)
            except KeyError:
                pass

        if "thinking_pause" in settings or "thinking_pause_duration" in settings:
            enabled = settings.get(
                "thinking_pause", self.manager.pacer.config.enable_thinking_pause
            )
            duration = settings.get(
                "thinking_pause_duration", self.manager.pacer.config.thinking_pause_duration
            )
            self.manager.pacer.set_thinking_pause(enabled, duration)

        if "min_chars_per_second" in settings:
            self.manager.pacer.config.min_chars_per_second = settings["min_chars_per_second"]
