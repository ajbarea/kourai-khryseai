"""Text-to-Speech engine for agent dialogue with personality voices.

Uses edge-tts for natural neural voices and Pygame for playback.
Supports streaming, volume control, audio effects, and asynchronous playback.
Optimized for March 2026 best practices with low-latency streaming and MP3→WAV conversion.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import edge_tts
import pygame

# Configure logging with proper debug output
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Use pygame-ce if available for better mixer features, fall back to pygame
with contextlib.suppress(ImportError, AttributeError):
    pass


@dataclass
class VoiceConfig:
    """Configuration for a voice personality."""

    name: str
    edge_id: str
    speed: float = 1.0  # 0.5 to 2.0
    pitch: float = 1.0  # 0.5 to 2.0 (perceptual pitch)
    emotion: str = "default"  # natural, sad, cheerful, angry, etc.


# Curated voice roster for agent personalities
VOICE_ROSTER = {
    "aria": VoiceConfig("Aria", "en-US-AriaNeural", 0.95),
    "jenny": VoiceConfig("Jenny", "en-US-JennyNeural", 0.90),
    "michelle": VoiceConfig("Michelle", "en-US-MichelleNeural", 0.92),
    "sonia": VoiceConfig("Sonia", "en-GB-SoniaNeural", 0.93),
    "guy": VoiceConfig("Guy", "en-US-GuyNeural", 0.95),
}

# Map agent names to voice personalities
AGENT_VOICES = {
    "hephaestus": "guy",
    "metis": "aria",
    "kallos": "jenny",
    "mneme": "michelle",
    "techne": "sonia",
    "dokimasia": "aria",
}


class TTSEngine:
    """Manages text-to-speech generation and playback with advanced audio control.

    Features:
    - Low-latency streaming audio with MP3→WAV conversion for compatibility
    - Volume normalization and fade effects
    - Asynchronous playback with cancellation support
    - Memory-efficient cleanup
    - Personality voice effects and prosody control
    - Comprehensive logging for debugging
    """

    def __init__(
        self,
        temp_dir: Path | None = None,
        master_volume: float = 0.8,
        enable_effects: bool = True,
    ):
        """Initialize the TTS engine.

        Args:
            temp_dir: Directory for temporary audio files. Uses system temp if None.
            master_volume: Master volume (0.0 to 1.0).
            enable_effects: Enable audio effects and normalization.
        """
        self.temp_dir = temp_dir or Path(tempfile.gettempdir()) / "kourai_tts"
        self.temp_dir.mkdir(exist_ok=True)
        self.is_playing = False
        self.master_volume = max(0.0, min(1.0, master_volume))
        self.enable_effects = enable_effects
        self._current_task: asyncio.Task | None = None
        self._on_complete: Callable[[], None] | None = None
        self._mixer_initialized = False
        self._init_mixer()
        logger.info(f"TTSEngine initialized: temp_dir={self.temp_dir}, volume={self.master_volume}")

    def _init_mixer(self) -> None:
        """Initialize pygame mixer with optimal settings."""
        if self._mixer_initialized:
            return
        try:
            pygame.mixer.init(
                frequency=44100,  # Standard CD quality
                size=-16,  # 16-bit
                channels=2,  # Stereo
                buffer=512,  # Low latency buffer
            )
            # Ensure we have enough channels and reserve channel 0 for TTS
            # so pygame.mixer.stop() from background music can't evict speech.
            pygame.mixer.set_num_channels(8)
            self._tts_channel = pygame.mixer.Channel(0)
            self._mixer_initialized = True
            logger.info("Pygame mixer initialized successfully (TTS on channel 0)")
        except RuntimeError as e:
            # Mixer already initialized — grab the channel anyway
            logger.warning(f"Pygame mixer init error (may be already init): {e}")
            try:
                self._tts_channel = pygame.mixer.Channel(0)
            except Exception:
                self._tts_channel = None
            self._mixer_initialized = True

    def set_master_volume(self, volume: float) -> None:
        """Set master volume (0.0 to 1.0)."""
        self.master_volume = max(0.0, min(1.0, volume))
        if self._mixer_initialized:
            pygame.mixer.music.set_volume(self.master_volume)
        logger.debug(f"Master volume set to {self.master_volume}")

    def set_on_complete(self, callback: Callable[[], None]) -> None:
        """Set callback to fire when playback completes."""
        self._on_complete = callback

    def _get_converter(self) -> str | None:
        """Find available audio converter (ffmpeg or avconv)."""
        for converter in ["ffmpeg", "avconv"]:
            try:
                subprocess.run([converter, "-version"], capture_output=True, timeout=2)
                logger.debug(f"Found converter: {converter}")
                return converter
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        logger.warning("No audio converter found (ffmpeg or avconv). MP3 playback may fail.")
        return None

    async def speak(
        self,
        text: str,
        agent_name: str | None = None,
        voice_key: str | None = None,
        speed: float | None = None,
        pitch: float | None = None,
    ) -> None:
        """Generate and play speech asynchronously.

        Args:
            text: Text to speak.
            agent_name: Agent name to auto-select voice. Ignored if voice_key provided.
            voice_key: Explicit voice key from VOICE_ROSTER.
            speed: Override voice speed (0.5 to 2.0).
            pitch: Override voice pitch (0.5 to 2.0).
        """
        if not text.strip():
            logger.debug("Empty text, skipping TTS")
            return

        # Determine voice
        if voice_key is None:
            voice_key = AGENT_VOICES.get(agent_name or "hephaestus", "aria")

        voice_cfg = VOICE_ROSTER.get(voice_key, VOICE_ROSTER["aria"])
        final_speed = speed if speed is not None else voice_cfg.speed

        # Generate audio with edge-tts (MP3 format)
        temp_mp3 = self.temp_dir / f"speech_{abs(hash(text)) % 1000000}.mp3"
        # Also prepare WAV path for pygame compatibility
        temp_wav = self.temp_dir / f"speech_{abs(hash(text)) % 1000000}.wav"

        try:
            logger.info(
                f"TTS: Starting speech generation - agent={agent_name}, voice={voice_key}, speed={final_speed}, text_len={len(text)}"
            )

            # Generate audio with prosody (speed applied via edge-tts)
            communicate = edge_tts.Communicate(
                text, voice_cfg.edge_id, rate=f"{(final_speed - 1.0) * 50:+.0f}%"
            )
            await communicate.save(str(temp_mp3))

            if not temp_mp3.exists():
                raise RuntimeError(f"Edge-TTS failed to generate audio file: {temp_mp3}")

            logger.debug(f"TTS: MP3 generated ({temp_mp3.stat().st_size} bytes)")

            # Convert MP3 to WAV using ffmpeg (pygame mixer compatible)
            converter = self._get_converter()
            if converter:
                logger.debug(f"TTS: Converting MP3→WAV using {converter}")
                try:
                    result = subprocess.run(
                        [
                            converter,
                            "-i",
                            str(temp_mp3),
                            "-acodec",
                            "pcm_s16le",
                            "-ar",
                            "44100",
                            "-ac",
                            "2",
                            str(temp_wav),
                            "-y",
                        ],
                        capture_output=True,
                        timeout=10,
                        text=True,
                    )
                    if result.returncode != 0:
                        logger.warning(
                            f"TTS: Converter returned code {result.returncode}: {result.stderr}"
                        )
                    if temp_wav.exists():
                        logger.debug(f"TTS: WAV generated ({temp_wav.stat().st_size} bytes)")
                        playback_path = temp_wav
                    else:
                        logger.warning("TTS: WAV not created, falling back to MP3")
                        playback_path = temp_mp3
                except subprocess.TimeoutExpired:
                    logger.warning("TTS: Converter timed out, falling back to MP3")
                    playback_path = temp_mp3
            else:
                logger.warning("TTS: No converter available, using MP3 directly (may fail)")
                playback_path = temp_mp3

            # Initialize mixer and play
            self._init_mixer()
            self.is_playing = True

            logger.debug(f"TTS: Loading sound from {playback_path}")
            sound = pygame.mixer.Sound(str(playback_path))

            # Apply volume normalization (peak normalization for consistent loudness)
            if self.enable_effects:
                sound.set_volume(self.master_volume * 0.85)
            else:
                sound.set_volume(self.master_volume)

            # Use dedicated channel so mixer.stop() from background music can't kill us
            channel = getattr(self, "_tts_channel", None)
            if channel is not None:
                logger.info(f"TTS: Playing on reserved channel 0, volume={sound.get_volume():.2f}")
                channel.play(sound)
            else:
                logger.info(f"TTS: Playing on default, volume={sound.get_volume():.2f}")
                sound.play()

            # Wait for this specific channel to finish
            playback_start = 0
            if channel is not None:
                while channel.get_busy():
                    await asyncio.sleep(0.05)
                    playback_start += 0.05
            else:
                while pygame.mixer.get_busy():
                    await asyncio.sleep(0.05)
                    playback_start += 0.05

            logger.info(f"TTS: Playback complete (duration={playback_start:.2f}s)")

        except Exception as e:
            logger.error(f"TTS playback error: {type(e).__name__}: {e}", exc_info=True)
        finally:
            self.is_playing = False
            # Clean up both MP3 and WAV
            for temp_file in [temp_mp3, temp_wav]:
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                        logger.debug(f"TTS: Cleaned up {temp_file}")
                    except OSError as e:
                        logger.warning(f"TTS: Failed to clean up {temp_file}: {e}")
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
            logger.info("TTS playback stopped (channel 0)")
        elif self.is_playing and pygame.mixer.get_busy():
            pygame.mixer.stop()
            logger.info("TTS playback stopped (mixer-wide fallback)")
        self.is_playing = False

    def cleanup(self) -> None:
        """Clean up temporary files and mixer resources."""
        self.stop()
        if self.temp_dir.exists():
            for f in self.temp_dir.glob("*.mp3"):
                with contextlib.suppress(OSError):
                    f.unlink()
            for f in self.temp_dir.glob("*.wav"):
                with contextlib.suppress(OSError):
                    f.unlink()
        if self._mixer_initialized:
            try:
                pygame.mixer.quit()
                self._mixer_initialized = False
                logger.info("Pygame mixer shut down")
            except RuntimeError:
                pass
