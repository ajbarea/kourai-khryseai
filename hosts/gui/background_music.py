"""Background music manager for the GUI.

Plays ambient background music during dialogue.
Uses simple WAV data generation.
"""

from __future__ import annotations

import io
import logging
import math
import struct
import wave
from pathlib import Path

import pygame

logger = logging.getLogger(__name__)


class BackgroundMusic:
    """Manages background music playback in the GUI."""

    def __init__(self, music_dir: Path | None = None):
        """Initialize background music manager.

        Args:
            music_dir: Directory containing .ogg, .mp3, or .wav music files.
                      Uses built-in generated music if None.
        """
        self.music_dir = music_dir
        self.is_playing = False
        self.current_track = None
        self.master_volume = 0.4  # Quiet by default so dialogue is foreground
        self._mixer_initialized = False
        self._init_mixer()

    def _init_mixer(self) -> None:
        """Initialize pygame mixer if not already done."""
        if self._mixer_initialized:
            return
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self._mixer_initialized = True
            logger.info("Mixer initialized for background music")
        except RuntimeError:
            self._mixer_initialized = True
            logger.debug("Mixer already initialized")

    def set_volume(self, volume: float) -> None:
        """Set background music volume (0.0 to 1.0)."""
        self.master_volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(self.master_volume)
        logger.debug(f"Background music volume set to {self.master_volume}")

    def _generate_ambient_wave(self) -> bytes:
        """Generate WAV data for ambient pad using struct packing."""
        sample_rate = 44100
        duration = 8  # seconds
        frequency = 55  # Hz (A1 note)

        num_samples = int(sample_rate * duration)
        audio_frames = []

        for i in range(num_samples):
            t = i / sample_rate

            # Multiple sine waves
            sample = math.sin(2 * math.pi * frequency * t) * 0.3
            sample += math.sin(2 * math.pi * frequency * 2 * t) * 0.15
            sample += math.sin(2 * math.pi * frequency * 0.5 * t) * 0.2

            # Fade envelope
            fade_samples = int(sample_rate * 0.5)
            if i < fade_samples:
                sample *= i / fade_samples
            if i > (num_samples - fade_samples):
                sample *= (num_samples - i) / fade_samples

            # Convert to 16-bit int
            sample = int(sample * 32767 * 0.5)
            sample = max(-32768, min(32767, sample))

            # Add stereo (same sample for both channels)
            audio_frames.append(struct.pack("h", sample))
            audio_frames.append(struct.pack("h", sample))

        audio_data = b"".join(audio_frames)

        # Create WAV header
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav:
            wav.setnchannels(2)  # Stereo
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(sample_rate)
            wav.writeframes(audio_data)

        return wav_buffer.getvalue()

    def play_ambient_music(self) -> None:
        """Play generated ambient background music."""
        logger.info("Generating and playing ambient background music...")

        try:
            # Generate WAV data
            wav_data = self._generate_ambient_wave()

            # Load into pygame mixer
            wav_buffer = io.BytesIO(wav_data)
            sound = pygame.mixer.Sound(file=wav_buffer)
            sound.set_volume(self.master_volume)

            # Play with looping
            sound.play(-1)

            self.is_playing = True
            self.current_track = "ambient_generated"
            logger.info("Ambient music playing")

        except Exception as e:
            logger.error(f"Failed to generate ambient music: {e}", exc_info=True)

    def stop(self) -> None:
        """Stop background music."""
        if self.is_playing:
            pygame.mixer.stop()
            self.is_playing = False
            logger.info("Background music stopped")

    def pause(self) -> None:
        """Pause background music."""
        if self.is_playing:
            pygame.mixer.pause()
            logger.debug("Background music paused")

    def unpause(self) -> None:
        """Resume background music."""
        pygame.mixer.unpause()
        logger.debug("Background music resumed")

    def cleanup(self) -> None:
        """Clean up mixer resources."""
        self.stop()
        if self._mixer_initialized:
            try:
                pygame.mixer.quit()
                self._mixer_initialized = False
                logger.info("Mixer shut down")
            except RuntimeError:
                pass
