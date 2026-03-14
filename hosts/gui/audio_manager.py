"""Centralized Audio Manager for Pygame.

Handles music streaming, ambient loops, one-shot SFX, and voice playback
with independent volume controls and dedicated channels.
"""

from __future__ import annotations

import io
import logging
import math
import os
import random
import struct
import threading
import wave
from pathlib import Path

import pygame

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
        self.voice_channel: pygame.mixer.Channel | None = None
        self.ambient_channel: pygame.mixer.Channel | None = None

        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.mixer.init()
            # Ensure enough channels (0: voice, 1: ambient, 2-7: sfx)
            pygame.mixer.set_num_channels(8)
            self.audio_available = True
            logger.info("AudioManager initialized Pygame mixer.")
        except (RuntimeError, pygame.error) as e:
            if pygame.mixer.get_init() is not None:
                self.audio_available = True
                pygame.mixer.set_num_channels(8)
                logger.warning("Pygame mixer init reported an error; reusing existing mixer: %s", e)
            else:
                logger.warning("Audio disabled; pygame mixer unavailable: %s", e)

        if self.audio_available:
            try:
                # Channel allocation: 0=voice, 1=ambient, 2=TTS, 3-7=SFX
                # This is coordinated with TTSEngine which reserves channel 2
                self.voice_channel = pygame.mixer.Channel(0)
                self.ambient_channel = pygame.mixer.Channel(1)
            except pygame.error as e:
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
        self._sfx_cache: dict[str, pygame.mixer.Sound] = {}

        self._playlist = []
        self._current_track_index = 0
        self._initialized = True

    def _mixer_ready(self) -> bool:
        return self.audio_available and pygame.mixer.get_init() is not None

    # --- Volume Controls ---
    def set_music_volume(self, volume: float) -> None:
        self.music_volume = max(0.0, min(1.0, volume))
        if self._mixer_ready() and pygame.mixer.music.get_busy():
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
        if not self._mixer_ready():
            logger.info("Skipping music playback; audio is disabled.")
            return
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(loops=loops, fade_ms=fade_ms)
            logger.info(f"Playing music: {path} with fade_ms={fade_ms}")
        except Exception as e:
            logger.error(f"Failed to play music: {e}")

    def fade_to_music(self, path: str | Path, fade_ms: int = 1000) -> None:
        self.stop_music(fade_ms)
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(loops=-1, fade_ms=fade_ms)
        except Exception as e:
            logger.error(f"Failed to fade music: {e}")

    def stop_music(self, fade_ms: int = 0) -> None:
        if not self._mixer_ready():
            return
        if fade_ms > 0:
            pygame.mixer.music.fadeout(fade_ms)
        else:
            pygame.mixer.music.stop()

    def pause_music(self) -> None:
        if self._mixer_ready():
            pygame.mixer.music.pause()

    def resume_music(self) -> None:
        if self._mixer_ready():
            pygame.mixer.music.unpause()

    # --- Ambient ---
    def play_ambient(self, path: str | Path | None = None) -> None:
        """Plays an ambient background sound, looping indefinitely.
        If no path is provided, falls back to the generated synth pad.
        """
        if not self._mixer_ready() or self.ambient_channel is None:
            logger.info("Skipping ambient playback; audio is disabled.")
            return
        try:
            if path:
                self.ambient_sound = pygame.mixer.Sound(file=str(path))
            elif not self.ambient_sound:
                # Fallback to generative synth drone
                wav_data = self._generate_ambient_wave()
                wav_buffer = io.BytesIO(wav_data)
                self.ambient_sound = pygame.mixer.Sound(file=wav_buffer)

            self.ambient_channel.set_volume(self.ambient_volume)
            self.ambient_channel.play(self.ambient_sound, loops=-1)
            logger.info(f"Ambient playing via Sound channel: {path or 'generative synth'}")
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

    # --- SFX (one-shot on free channel) ---
    def play_sfx(self, path: str | Path | None = None) -> None:
        """Play a one-shot SFX file on the next free channel (3-7, skipping 2 reserved for TTS).

        Loads and caches the Sound object on first use. If no path is provided,
        falls back to a generated UI blip.
        """
        if not self._mixer_ready():
            logger.info("Skipping SFX playback; audio is disabled.")
            return
        try:
            if path:
                key = str(path)
                sound = self._sfx_cache.get(key)
                if sound is None:
                    sound = pygame.mixer.Sound(file=key)
                    self._sfx_cache[key] = sound
            else:
                # Generate a short, pleasant UI blip
                sample_rate = 44100
                duration = 0.1  # 100ms
                frequency = 880  # Hz (A5 note)

                num_samples = int(sample_rate * duration)
                audio_frames = []

                for i in range(num_samples):
                    t = i / sample_rate
                    sample = math.sin(2 * math.pi * frequency * t)

                    # Quick fade out to avoid clicking
                    fade_samples = int(sample_rate * 0.05)
                    if i > (num_samples - fade_samples):
                        sample *= (num_samples - i) / fade_samples

                    sample = int(sample * 32767 * 0.3)
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

                wav_buffer.seek(0)
                sound = pygame.mixer.Sound(file=wav_buffer)

            sound.set_volume(self.sfx_volume)
            # Find an available channel (not 0 or 1)
            channel = pygame.mixer.find_channel()
            if channel:
                channel.play(sound)
        except Exception as e:
            logger.error(f"Failed to play SFX: {e}")

    def cleanup(self) -> None:
        """Clean up mixer resources."""
        if not self._mixer_ready():
            self._sfx_cache.clear()
            return
        self.stop_music()
        if self.ambient_channel:
            self.ambient_channel.stop()
        if self.voice_channel:
            self.voice_channel.stop()
        self._sfx_cache.clear()
        # Do not call pygame.mixer.quit() if TTSEngine might still need to cleanup,
        # but it's safe if it's the last thing.

    def load_playlist(self, directory: str) -> None:
        """Load and shuffle all .ogg files from the given directory."""
        if not self._mixer_ready():
            logger.info("Skipping playlist loading; audio is disabled.")
            return
        try:
            self._playlist = [
                os.path.join(directory, f) for f in os.listdir(directory) if f.endswith(".ogg")
            ]
            random.shuffle(self._playlist)
            self._current_track_index = 0
            logger.info(f"Loaded playlist with {len(self._playlist)} tracks from {directory}.")
        except Exception as e:
            logger.error(f"Failed to load playlist: {e}")

    def play_next_track(self) -> None:
        """Play the next track in the playlist, looping back to the start if necessary."""
        if not self._playlist:
            logger.warning("Playlist is empty. Cannot play next track.")
            return
        track = self._playlist[self._current_track_index]
        self._current_track_index = (self._current_track_index + 1) % len(self._playlist)
        self.play_music(track, fade_ms=1000)

    def is_music_playing(self) -> bool:
        """Check if music is currently playing."""
        return pygame.mixer.music.get_busy()

    def play_playlist(self) -> None:
        """Start playing the shuffled playlist on loop."""
        if not self._mixer_ready():
            logger.info("Skipping playlist playback; audio is disabled.")
            return
        if not self._playlist:
            logger.warning("Playlist is empty. Load a playlist before playing.")
            return

        def _play_loop():
            while True:
                if not self.is_music_playing():
                    self.play_next_track()
                pygame.time.wait(100)  # Check every 100ms

        threading.Thread(target=_play_loop, daemon=True).start()
