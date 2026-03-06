"""Centralized Audio Manager for Pygame.

Handles music streaming, ambient loops, one-shot SFX, and voice playback
with independent volume controls and dedicated channels.
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


class AudioManager:
    """Manages all game audio: music, ambient, voice, and SFX."""

    _instance = None
    _initialized = False

    def __new__(cls):
        # Optional singleton pattern or just allow normal instantiation.
        # We'll stick to normal instantiation for safety but keep instance tracking
        # if other modules need global access without passing it around.
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent re-initialization
        if self._initialized:
            return

        # 1. Pre-init for low latency
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.mixer.init()
            # Ensure enough channels (0: voice, 1: ambient, 2-7: sfx)
            pygame.mixer.set_num_channels(8)
            logger.info("AudioManager initialized Pygame mixer.")
        except RuntimeError as e:
            logger.warning(f"Pygame mixer init error (may be already init): {e}")

        # Reserve channels
        self.voice_channel = pygame.mixer.Channel(0)
        self.ambient_channel = pygame.mixer.Channel(1)

        # Volumes
        self.music_volume = 0.25
        self.ambient_volume = 0.5
        self.voice_volume = 1.0
        self.sfx_volume = 0.8

        self.ambient_sound = None

        self._initialized = True

    # --- Volume Controls ---
    def set_music_volume(self, volume: float) -> None:
        self.music_volume = max(0.0, min(1.0, volume))
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.set_volume(self.music_volume)

    def set_ambient_volume(self, volume: float) -> None:
        self.ambient_volume = max(0.0, min(1.0, volume))
        self.ambient_channel.set_volume(self.ambient_volume)

    def set_voice_volume(self, volume: float) -> None:
        self.voice_volume = max(0.0, min(1.0, volume))
        self.voice_channel.set_volume(self.voice_volume)

    def set_sfx_volume(self, volume: float) -> None:
        self.sfx_volume = max(0.0, min(1.0, volume))

    # --- Music (Streamed) ---
    def play_music(self, path: str | Path, loops: int = -1) -> None:
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(loops=loops)
            logger.info(f"Playing music: {path}")
        except Exception as e:
            logger.error(f"Failed to play music: {e}")

    def fade_to_music(self, path: str | Path, fade_ms: int = 1000) -> None:
        self.stop_music(fade_ms)
        # In a full game, we'd use a USEREVENT to start the next track when fadeout ends.
        # For now, just load and play with fade_in if the API supports it.
        # pygame.mixer.music.fadeout blocks or is async? It's async.
        # A simple implementation just loads and plays with fade.
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(self.music_volume)
            # Pygame 2+ allows fade_ms in play()
            pygame.mixer.music.play(loops=-1, fade_ms=fade_ms)
        except Exception as e:
            logger.error(f"Failed to fade music: {e}")

    def stop_music(self, fade_ms: int = 0) -> None:
        if fade_ms > 0:
            pygame.mixer.music.fadeout(fade_ms)
        else:
            pygame.mixer.music.stop()

    def pause_music(self) -> None:
        pygame.mixer.music.pause()

    def resume_music(self) -> None:
        pygame.mixer.music.unpause()

    # --- Ambient ---
    def play_ambient(self) -> None:
        """Plays the generated ambient background music as a Sound object."""
        try:
            if not self.ambient_sound:
                wav_data = self._generate_ambient_wave()
                wav_buffer = io.BytesIO(wav_data)
                self.ambient_sound = pygame.mixer.Sound(file=wav_buffer)

            self.ambient_channel.set_volume(self.ambient_volume)
            self.ambient_channel.play(self.ambient_sound, loops=-1)
            logger.info("Ambient music playing via Sound channel")
        except Exception as e:
            logger.error(f"Failed to play ambient sound: {e}", exc_info=True)

    def _generate_ambient_wave(self) -> bytes:
        """Generate WAV data for ambient pad using struct packing."""
        sample_rate = 44100
        duration = 8  # seconds
        frequency = 55  # Hz (A1 note)

        num_samples = int(sample_rate * duration)
        audio_frames = []

        for i in range(num_samples):
            t = i / sample_rate

            sample = math.sin(2 * math.pi * frequency * t) * 0.3
            sample += math.sin(2 * math.pi * frequency * 2 * t) * 0.15
            sample += math.sin(2 * math.pi * frequency * 0.5 * t) * 0.2

            fade_samples = int(sample_rate * 0.5)
            if i < fade_samples:
                sample *= i / fade_samples
            if i > (num_samples - fade_samples):
                sample *= (num_samples - i) / fade_samples

            sample = int(sample * 32767 * 0.5)
            sample = max(-32768, min(32767, sample))

            audio_frames.append(struct.pack("h", sample))
            audio_frames.append(struct.pack("h", sample))

        audio_data = b"".join(audio_frames)

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(audio_data)

        return wav_buffer.getvalue()

    def cleanup(self) -> None:
        """Clean up mixer resources."""
        self.stop_music()
        if self.ambient_channel:
            self.ambient_channel.stop()
        if self.voice_channel:
            self.voice_channel.stop()
        # Do not call pygame.mixer.quit() if TTSEngine might still need to cleanup,
        # but it's safe if it's the last thing.
