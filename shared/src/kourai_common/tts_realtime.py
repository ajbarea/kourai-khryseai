"""RealtimeTTS-backed TTS engine — bundles Kokoro synth + PyAudio playback.

Replaces the pygame.mixer-based ``hosts.gui.tts_engine.TTSEngine`` on the
CLI surface. pygame.mixer's documented inability to reliably resample
24 kHz mono → 44.1 kHz stereo produced the "VHS rewind" chipmunk
symptom; RealtimeTTS routes Kokoro's native 24 kHz mono through
PyAudio with no resample step in the path.

ABI-compatible drop-in for the CLI's TTSEngine usage (``speak``,
``speak_sync``, ``stop``, ``cleanup``, ``set_master_volume``,
``master_volume``, ``enable_effects``, ``is_playing``). GUI migration
is a separate Phase 2 follow-up; until both hosts flip, the legacy
``tts_engine.py`` / ``tts_kokoro.py`` / ``tts_edge.py`` remain.

Future ElevenLabs swap (M6) becomes a one-line engine change inside
``__init__``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

# Module-level bindings (aliased with leading underscore) so tests can
# monkeypatch them without instantiating PyAudio. RealtimeTTS is a hard
# dep in hosts/gui/pyproject.toml; importing it pulls in pyaudio, which
# requires portaudio19-dev on Linux (CI installs it via ed4d560).
from RealtimeTTS import KokoroEngine as _KokoroEngine, TextToAudioStream as _TextToAudioStream

from kourai_common.tts_backend import (
    AGENT_VOICE_MAP,
    TTSVoiceConfig,
    get_voice_for_agent,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# Re-exports for parity with hosts.gui.tts_engine
VoiceConfig = TTSVoiceConfig
VOICE_ROSTER = {v.voice_id: v for v in AGENT_VOICE_MAP.values()}
AGENT_VOICES = {agent: cfg.voice_id for agent, cfg in AGENT_VOICE_MAP.items()}


class RealtimeTTSEngine:
    """TTS engine wrapping RealtimeTTS's KokoroEngine + TextToAudioStream.

    PyAudio-backed playback at native 24 kHz mono — no pygame mixer in
    the path, so the resample "VHS rewind" failure mode is gone by
    construction. Mirrors ``TTSEngine``'s ABI for drop-in replacement.
    """

    def __init__(
        self,
        master_volume: float = 0.8,
        enable_effects: bool = True,
        muted: bool = False,
        on_word: Callable[[object], None] | None = None,
    ):
        self._engine = _KokoroEngine(voice="af_heart", default_speed=1.0, debug=False)
        self._stream = _TextToAudioStream(
            engine=self._engine,
            on_word=on_word,
            muted=muted,
            level=logging.WARNING,
        )

        self.master_volume = max(0.0, min(1.0, master_volume))
        self.enable_effects = enable_effects
        self.is_playing = False
        self._on_complete: Callable[[], None] | None = None

        self._stream.set_volume(self._effective_volume())

        logger.info(
            "RealtimeTTSEngine initialized: voice=af_heart, volume=%s, effects=%s",
            self.master_volume,
            self.enable_effects,
        )

    def _effective_volume(self) -> float:
        return self.master_volume * (0.85 if self.enable_effects else 1.0)

    def set_master_volume(self, volume: float) -> None:
        """Set master volume (0.0 to 1.0)."""
        self.master_volume = max(0.0, min(1.0, volume))
        self._stream.set_volume(self._effective_volume())
        logger.debug("Master volume set to %s", self.master_volume)

    def set_on_complete(self, callback: Callable[[], None]) -> None:
        """Set callback to fire when playback completes."""
        self._on_complete = callback

    async def speak(
        self,
        text: str,
        agent_name: str | None = None,
        voice_key: str | None = None,
        speed: float | None = None,
        pitch: float | None = None,
    ) -> None:
        """Generate and play speech asynchronously.

        ``pitch`` is accepted for ABI parity with ``TTSEngine.speak`` but
        ignored — KokoroEngine has no pitch control (the legacy
        ``KokoroBackend`` also dropped it for the same reason).
        """
        if not text.strip():
            logger.debug("Empty text, skipping TTS")
            return

        # Resolve voice
        if voice_key is not None:
            voice_cfg = VOICE_ROSTER.get(voice_key, get_voice_for_agent(None))
        else:
            voice_cfg = get_voice_for_agent(agent_name)

        effective_speed = speed if speed is not None else voice_cfg.speed

        try:
            logger.info(
                "TTS: starting RealtimeTTS speech — agent=%s, voice=%s, speed=%.2f, text=%r",
                agent_name,
                voice_cfg.voice_id,
                effective_speed,
                text,
            )

            self._engine.set_voice(voice_cfg.voice_id)
            self._engine.set_speed(effective_speed)

            self.is_playing = True
            self._stream.feed(text)

            # Bridge RealtimeTTS's blocking play() into the async loop.
            # play() runs synthesis + playback to completion on a worker
            # thread, returning when the audio stream stops.
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._stream.play)

            logger.info("TTS: playback complete")
        except Exception as e:
            # TTS is non-critical; keep the console line terse.
            logger.warning("TTS playback skipped (%s: %s)", type(e).__name__, e)
            logger.debug("TTS playback error detail", exc_info=True)
        finally:
            self.is_playing = False
            if self._on_complete:
                self._on_complete()

    def speak_sync(
        self,
        text: str,
        agent_name: str | None = None,
        voice_key: str | None = None,
        speed: float | None = None,
        pitch: float | None = None,
    ) -> None:
        """Synchronous wrapper for speak (blocks until complete)."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self.speak(
                    text,
                    agent_name=agent_name,
                    voice_key=voice_key,
                    speed=speed,
                    pitch=pitch,
                )
            )
        finally:
            loop.close()

    def stop(self) -> None:
        """Stop current playback gracefully."""
        try:
            self._stream.stop()
        except Exception as e:
            logger.debug("RealtimeTTS stop ignored (%s: %s)", type(e).__name__, e)
        self.is_playing = False

    def cleanup(self) -> None:
        """Stop playback and shut the KokoroEngine down."""
        self.stop()
        try:
            self._engine.shutdown()
        except Exception as e:
            logger.debug("KokoroEngine shutdown ignored (%s: %s)", type(e).__name__, e)
        logger.debug("RealtimeTTSEngine cleanup complete")
