"""Text-to-Speech engine for agent dialogue with personality voices.

Uses a pluggable TTSBackend (default: Kokoro-82M) for speech synthesis
and Pygame for playback. Supports volume control, audio effects, and
asynchronous playback.

The backend abstraction lives in kourai_common.tts_backend — see that
module for voice mapping and the TTSBackend protocol.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from kourai_common.tts_backend import (
    AGENT_VOICE_MAP,
    TTSVoiceConfig,
    get_voice_for_agent,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from kourai_common.tts_backend import TTSBackend

logger = logging.getLogger(__name__)


# Re-export for test compatibility — tests import these from tts_engine
VoiceConfig = TTSVoiceConfig
VOICE_ROSTER = {v.voice_id: v for v in AGENT_VOICE_MAP.values()}
AGENT_VOICES = {agent: cfg.voice_id for agent, cfg in AGENT_VOICE_MAP.items()}


def _create_default_backend() -> TTSBackend:
    """Create the default TTS backend (Kokoro, falling back to edge-tts)."""
    try:
        from kourai_common.tts_kokoro import KokoroBackend

        return KokoroBackend()
    except ImportError:
        logger.warning(
            "Kokoro not available (pip install kokoro soundfile). Falling back to edge-tts."
        )
        from kourai_common.tts_edge import EdgeTTSBackend

        return EdgeTTSBackend()


class TTSEngine:
    """Manages text-to-speech generation and playback with advanced audio control.

    Features:
    - Pluggable backend (Kokoro-82M local or edge-tts cloud)
    - Volume normalization and fade effects
    - Asynchronous playback with cancellation support
    - Memory-efficient cleanup
    - Personality voice effects and prosody control
    """

    def __init__(
        self,
        backend: TTSBackend | None = None,
        temp_dir: Path | None = None,
        master_volume: float = 0.8,
        enable_effects: bool = True,
    ):
        """Initialize the TTS engine.

        Args:
            backend: TTS synthesis backend. Auto-detected if None.
            temp_dir: Directory for temporary audio files. Uses system temp if None.
            master_volume: Master volume (0.0 to 1.0).
            enable_effects: Enable audio effects and normalization.
        """
        self.backend = backend or _create_default_backend()
        self.temp_dir = temp_dir or Path(tempfile.gettempdir()) / "kourai_tts"
        self.temp_dir.mkdir(exist_ok=True)
        self.is_playing = False
        self.master_volume = max(0.0, min(1.0, master_volume))
        self.enable_effects = enable_effects
        self._current_task: asyncio.Task | None = None
        self._on_complete: Callable[[], None] | None = None
        self._mixer_initialized = False
        self._init_mixer()
        logger.info(
            "TTSEngine initialized: backend=%s, temp_dir=%s, volume=%s",
            type(self.backend).__name__,
            self.temp_dir,
            self.master_volume,
        )

    def _init_mixer(self) -> None:
        """Initialize pygame mixer with optimal settings.

        Uses channel 2 (reserved for TTS) to avoid collision with AudioManager which uses
        channels 0 (voice) and 1 (ambient). If mixer is already initialized by AudioManager,
        reuse it without reinitializing.
        """
        if self._mixer_initialized:
            return
        try:
            # Try to init mixer — will fail if AudioManager already initialized it,
            # which is fine; we'll reuse the existing mixer.
            pygame.mixer.init(
                frequency=44100,
                size=-16,
                channels=2,
                buffer=512,
            )
            pygame.mixer.set_num_channels(8)
            logger.debug("Pygame mixer initialized (fresh)")
        except (RuntimeError, pygame.error) as e:
            if pygame.mixer.get_init() is None:
                self._tts_channel = None
                self._mixer_initialized = False
                logger.warning("TTS audio disabled; pygame mixer unavailable: %s", e)
                return
            # Mixer already initialized (likely by AudioManager) — reuse it
            logger.debug("Pygame mixer already initialized; reusing existing mixer")

        # Reserve channel 2 for TTS (channels 0-1 belong to AudioManager)
        try:
            self._tts_channel = pygame.mixer.Channel(2)
            self._mixer_initialized = True
            logger.info("Pygame mixer ready for TTS (using channel 2)")
        except pygame.error as channel_error:
            self._tts_channel = None
            self._mixer_initialized = False
            logger.warning(
                "TTS audio disabled; failed to reserve mixer channel 2: %s",
                channel_error,
            )
        except Exception as e:
            self._tts_channel = None
            self._mixer_initialized = False
            logger.error(
                "Unexpected error while reserving mixer channel 2: %s",
                e,
            )

    def set_master_volume(self, volume: float) -> None:
        """Set master volume (0.0 to 1.0)."""
        self.master_volume = max(0.0, min(1.0, volume))
        channel = getattr(self, "_tts_channel", None)
        if channel is not None:
            channel.set_volume(self.master_volume)
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
        """Generate and play speech asynchronously with low-latency streaming.

        Args:
            text: Text to speak.
            agent_name: Agent name to auto-select voice. Ignored if voice_key provided.
            voice_key: Explicit voice_id to use. Overrides agent_name lookup.
            speed: Override voice speed (0.5 to 2.0).
            pitch: Override voice pitch (0.5 to 2.0).
        """
        if not text.strip():
            logger.debug("Empty text, skipping TTS")
            return

        # Resolve voice config
        if voice_key is not None:
            voice_cfg = VOICE_ROSTER.get(voice_key, get_voice_for_agent(None))
        else:
            voice_cfg = get_voice_for_agent(agent_name)

        # Apply overrides
        if speed is not None or pitch is not None:
            voice_cfg = TTSVoiceConfig(
                name=voice_cfg.name,
                voice_id=voice_cfg.voice_id,
                lang_code=voice_cfg.lang_code,
                speed=speed if speed is not None else voice_cfg.speed,
                pitch=pitch if pitch is not None else voice_cfg.pitch,
                emotion=voice_cfg.emotion,
            )

        try:
            logger.info(
                "TTS: Starting streaming speech generation — "
                "agent=%s, voice=%s (%s), speed=%.2f, text_len=%d",
                agent_name,
                voice_cfg.voice_id,
                type(self.backend).__name__,
                voice_cfg.speed,
                len(text),
            )

            self._init_mixer()
            if pygame.mixer.get_init() is None:
                logger.info("Skipping TTS playback; audio is disabled.")
                return

            self.is_playing = True
            channel: pygame.mixer.Channel | None = getattr(self, "_tts_channel", None)
            playback_duration: float = 0.0
            chunk_count = 0

            # Stream chunks from the backend
            async for chunk_bytes in self.backend.stream_synthesize(text, voice_cfg):
                if not chunk_bytes:
                    continue

                chunk_count += 1
                sound = pygame.mixer.Sound(chunk_bytes)

                # Apply volume normalization
                if self.enable_effects:
                    sound.set_volume(self.master_volume * 0.85)
                else:
                    sound.set_volume(self.master_volume)

                if channel is not None:
                    # For the first chunk, play immediately
                    if chunk_count == 1:
                        logger.debug("TTS: Playing first chunk (latency optimized)")
                        channel.play(sound)
                    else:
                        # For subsequent chunks, queue them for gapless playback
                        # If the queue is full (pygame only supports 1 queued sound),
                        # wait until the current sound finishes or the queue is free.
                        while channel.get_queue() is not None:
                            await asyncio.sleep(0.01)
                            playback_duration += 0.01
                        channel.queue(sound)
                else:
                    # Fallback if no reserved channel: play sequentially (less ideal)
                    sound.play()
                    while pygame.mixer.get_busy():
                        await asyncio.sleep(0.01)
                        playback_duration += 0.01

            # Wait for final chunks to finish playing
            if channel is not None:
                while channel.get_busy():
                    await asyncio.sleep(0.05)
                    playback_duration += 0.05
            else:
                while pygame.mixer.get_busy():
                    await asyncio.sleep(0.05)
                    playback_duration += 0.05

            logger.info(
                "TTS: Streaming playback complete (chunks=%d, duration=%.2fs)",
                chunk_count,
                playback_duration,
            )

        except Exception as e:
            # TTS is non-critical; keep the console line terse. Full traceback
            # lands in logs/<host>.log via the file handler at DEBUG level.
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
        channel = getattr(self, "_tts_channel", None)
        if channel is not None and channel.get_busy():
            channel.stop()
            logger.info("TTS playback stopped (channel 2)")
        self.is_playing = False

    def cleanup(self) -> None:
        """Clean up temporary files.

        NOTE: Does NOT call pygame.mixer.quit() because the mixer is shared with
        AudioManager and other GUI components. Mixer lifecycle is managed globally.
        """
        self.stop()
        if self.temp_dir.exists():
            for f in self.temp_dir.glob("*.wav"):
                with contextlib.suppress(OSError):
                    f.unlink()
            for f in self.temp_dir.glob("*.mp3"):
                with contextlib.suppress(OSError):
                    f.unlink()
        logger.debug("TTSEngine cleanup complete")
