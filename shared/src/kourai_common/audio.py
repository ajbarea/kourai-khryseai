"""Centralized Audio Manager.

Handles music streaming, ambient loops, one-shot SFX, and voice playback
with independent volume controls and dedicated channels.

Uses Pygame mixer but is decoupled enough to be used by both GUI and CLI hosts.
"""

from __future__ import annotations

import io
import logging
import math
import random
import struct
import threading
import wave
from pathlib import Path
from typing import Any

from kourai_common.audio_env import configure_sdl_audio_driver

# Module-load side effect: pick a sensible SDL audio backend (e.g. WSLg
# pulseaudio, or `dummy` on headless Linux) BEFORE pygame is imported,
# so SDL's audio subsystem doesn't fall back to ALSA and flood stderr
# with `cannot find card '0'` lines on first init. Player overrides via
# ``SDL_AUDIODRIVER`` are always respected.
configure_sdl_audio_driver()


# Pygame is required for audio playback. If not available, audio is disabled.
try:
    import pygame
except ImportError:
    pygame = None

logger = logging.getLogger(__name__)


class AudioManager:
    """Manages all game audio: music, ambient, voice, and SFX."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized: bool = False
        self.audio_available = False
        self.voice_channel = None
        self.ambient_channel = None

        if pygame is None:
            logger.warning("Audio disabled; pygame not installed.")
            self._initialized = True
            return

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 512)
                pygame.mixer.init()

            # Ensure enough channels (0: voice, 1: ambient, 2: TTS, 3-7: sfx)
            pygame.mixer.set_num_channels(8)
            self.audio_available = True
            logger.info("AudioManager initialized Pygame mixer.")
        except (RuntimeError, Exception) as e:
            if pygame.mixer.get_init() is not None:
                self.audio_available = True
                pygame.mixer.set_num_channels(8)
                logger.warning("Pygame mixer init reported an error; reusing existing mixer: %s", e)
            else:
                logger.warning("Audio disabled; pygame mixer unavailable: %s", e)

        if self.audio_available:
            try:
                # Channel allocation: 0=voice, 1=ambient, 2=TTS, 3-7=SFX
                self.voice_channel = pygame.mixer.Channel(0)
                self.ambient_channel = pygame.mixer.Channel(1)
            except Exception as e:
                self.audio_available = False
                self.voice_channel = None
                self.ambient_channel = None
                logger.warning("Audio disabled; failed to reserve mixer channels: %s", e)

        self.music_volume = 0.25
        self.ambient_volume = 0.5
        self.voice_volume = 1.0
        self.sfx_volume = 0.8
        self.ambient_sound = None

        # SFX cache: path → loaded Sound object
        self._sfx_cache: dict[str, Any] = {}

        self._playlist: list[str] = []
        self._current_track_index = 0
        self._initialized = True

    def _mixer_ready(self) -> bool:
        if pygame is None:
            return False
        return self.audio_available and pygame.mixer.get_init() is not None

    # --- Volume Controls ---
    def set_music_volume(self, volume: float) -> None:
        self.music_volume = max(0.0, min(1.0, volume))
        if pygame is not None and self._mixer_ready() and pygame.mixer.music.get_busy():
            pygame.mixer.music.set_volume(self.music_volume)

    def set_ambient_volume(self, volume: float) -> None:
        self.ambient_volume = max(0.0, min(1.0, volume))
        if self.ambient_channel is not None:
            self.ambient_channel.set_volume(self.ambient_volume)

    def set_voice_volume(self, volume: float) -> None:
        self.voice_volume = max(0.0, min(1.0, volume))
        if self.voice_channel is not None:
            self.voice_channel.set_volume(self.voice_volume)

    def set_sfx_volume(self, volume: float) -> None:
        self.sfx_volume = max(0.0, min(1.0, volume))

    # --- Music (Streamed) ---
    def play_music(self, path: str | Path, loops: int = -1, fade_ms: int = 0) -> None:
        if not self._mixer_ready() or pygame is None:
            return
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(loops=loops, fade_ms=fade_ms)
            logger.info(f"Playing music: {path}")
        except Exception as e:
            logger.error(f"Failed to play music: {e}")

    def fade_to_music(self, path: str | Path, fade_ms: int = 1000) -> None:
        """Compatibility helper: fade current track out and start a new one."""
        if not self._mixer_ready() or pygame is None:
            return
        self.stop_music(fade_ms)
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(loops=-1, fade_ms=fade_ms)
        except Exception as e:
            logger.error(f"Failed to fade music: {e}")

    def stop_music(self, fade_ms: int = 0) -> None:
        if not self._mixer_ready() or pygame is None:
            return
        if fade_ms > 0:
            pygame.mixer.music.fadeout(fade_ms)
        else:
            pygame.mixer.music.stop()

    def pause_music(self) -> None:
        if self._mixer_ready() and pygame is not None:
            pygame.mixer.music.pause()

    def resume_music(self) -> None:
        if self._mixer_ready() and pygame is not None:
            pygame.mixer.music.unpause()

    # --- Ambient ---
    def play_ambient(self, path: str | Path | None = None) -> None:
        """Plays an ambient background sound, looping indefinitely."""
        if not self._mixer_ready() or self.ambient_channel is None or pygame is None:
            return
        try:
            if path:
                self.ambient_sound = pygame.mixer.Sound(file=str(path))
            else:
                # Fallback to generative synth drone
                wav_data = self._generate_ambient_wave()
                self.ambient_sound = pygame.mixer.Sound(file=io.BytesIO(wav_data))

            self.ambient_channel.set_volume(self.ambient_volume)
            self.ambient_channel.play(self.ambient_sound, loops=-1)
        except Exception as e:
            logger.error(f"Failed to play ambient sound: {e}")

    def _generate_ambient_wave(self) -> bytes:
        """Generate WAV data for ambient pad."""
        sample_rate = 44100
        duration = 8
        frequency = 55
        num_samples = int(sample_rate * duration)
        audio_frames = []
        for i in range(num_samples):
            t = i / sample_rate
            sample = math.sin(2 * math.pi * frequency * t) * 0.3
            sample = int(sample * 32767 * 0.5)
            audio_frames.append(struct.pack("h", max(-32768, min(32767, sample))))
            audio_frames.append(struct.pack("h", max(-32768, min(32767, sample))))

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(b"".join(audio_frames))
        return wav_buffer.getvalue()

    def _generate_sfx_blip_wave(self) -> bytes:
        """Generate a short UI blip for no-path SFX playback."""
        sample_rate = 44100
        duration = 0.1
        frequency = 880
        num_samples = int(sample_rate * duration)
        audio_frames = []
        fade_samples = int(sample_rate * 0.05)

        for i in range(num_samples):
            t = i / sample_rate
            sample = math.sin(2 * math.pi * frequency * t)
            if i > (num_samples - fade_samples):
                sample *= (num_samples - i) / fade_samples
            sample_i = int(sample * 32767 * 0.3)
            sample_i = max(-32768, min(32767, sample_i))
            audio_frames.append(struct.pack("h", sample_i))
            audio_frames.append(struct.pack("h", sample_i))

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(b"".join(audio_frames))
        return wav_buffer.getvalue()

    # --- SFX ---
    def play_sfx(self, path: str | Path | None = None) -> None:
        if not self._mixer_ready() or pygame is None:
            return
        try:
            if path:
                key = str(path)
                sound = self._sfx_cache.get(key)
                if sound is None:
                    sound = pygame.mixer.Sound(file=key)
                    self._sfx_cache[key] = sound
            else:
                sound = pygame.mixer.Sound(file=io.BytesIO(self._generate_sfx_blip_wave()))
            sound.set_volume(self.sfx_volume)
            channel = pygame.mixer.find_channel()
            if channel:
                channel.play(sound)
        except Exception as e:
            logger.error(f"Failed to play SFX: {e}")

    def cleanup(self) -> None:
        if not self._mixer_ready():
            return
        self.stop_music()
        if self.ambient_channel:
            self.ambient_channel.stop()
        self._sfx_cache.clear()

    def load_playlist(self, directory: str) -> None:
        if not self._mixer_ready():
            return
        try:
            self._playlist = [str(p) for p in Path(directory).iterdir() if p.suffix == ".ogg"]
            random.shuffle(self._playlist)
            self._current_track_index = 0
            logger.info(f"Loaded playlist with {len(self._playlist)} tracks.")
        except Exception as e:
            logger.error(f"Failed to load playlist: {e}")

    def play_next_track(self) -> None:
        if not self._playlist:
            return
        track = self._playlist[self._current_track_index]
        self._current_track_index = (self._current_track_index + 1) % len(self._playlist)
        self.play_music(track, fade_ms=1000)

    def is_music_playing(self) -> bool:
        return self._mixer_ready() and pygame is not None and pygame.mixer.music.get_busy()

    def play_playlist(self) -> None:
        if not self._mixer_ready() or not self._playlist:
            return

        def _play_loop():
            while True:
                if not self.is_music_playing():
                    self.play_next_track()
                if pygame is not None:
                    pygame.time.wait(1000)
                else:
                    import time

                    time.sleep(1)

        threading.Thread(target=_play_loop, daemon=True).start()
