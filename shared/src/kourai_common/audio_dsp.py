"""Pure-numpy audio DSP — normalization, fades, visualization, profiles.

Shared by any host with TTS playback for per-agent loudness targets and
DSP helpers without copying numpy code.

`research(2026-05)` follow-up filed in IMPL.md: ``AudioNormalizer``
implements a hand-rolled LUFS approximation; ``pyloudnorm`` is the
canonical ITU-R BS.1770-4 implementation. Migration is a behavior change
(different LUFS readings, possibly different normalization adjustments)
— separate PR when an audio-quality callback surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class AudioMetrics:
    """Metrics for audio quality and playback characteristics."""

    peak_amplitude: float  # 0.0-1.0
    rms_level: float  # Root Mean Square (loudness)
    duration_ms: float
    sample_rate: int = 44100


class AudioNormalizer:
    """Normalizes audio for consistent perceived loudness."""

    # Target loudness (LUFS) for dialogue
    TARGET_LOUDNESS = -17.0  # Integrated Loudness Unit Relative to FS
    PEAK_HEADROOM = -6.0  # Leave headroom to prevent clipping

    @staticmethod
    def normalize_amplitude(samples: np.ndarray, target_level: float = 0.85) -> np.ndarray:
        """Normalize audio amplitude to prevent clipping."""
        if len(samples) == 0:
            return samples

        peak = np.max(np.abs(samples))
        if peak == 0.0:
            return samples

        return samples * (target_level / peak)

    @staticmethod
    def calculate_rms(samples: np.ndarray) -> float:
        """Calculate RMS (Root Mean Square) level for loudness estimation."""
        if len(samples) == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples**2)))


class AudioFadeEffect:
    """Fade in/out effects for smooth audio transitions."""

    @staticmethod
    def apply_fade_in(
        samples: np.ndarray, duration_ms: float, sample_rate: int = 44100
    ) -> np.ndarray:
        """Apply fade-in effect."""
        fade_samples = int(duration_ms * sample_rate / 1000.0)
        fade_samples = min(fade_samples, len(samples))

        if fade_samples <= 1:
            return samples

        fade_curve = np.linspace(0.0, 1.0, fade_samples)
        samples = samples.copy()
        samples[:fade_samples] *= fade_curve

        return samples

    @staticmethod
    def apply_fade_out(
        samples: np.ndarray, duration_ms: float, sample_rate: int = 44100
    ) -> np.ndarray:
        """Apply fade-out effect."""
        fade_samples = int(duration_ms * sample_rate / 1000.0)
        fade_samples = min(fade_samples, len(samples))

        if fade_samples <= 1:
            return samples

        fade_curve = np.linspace(1.0, 0.0, fade_samples)
        samples = samples.copy()
        samples[-fade_samples:] *= fade_curve

        return samples


class AudioVisualizer:
    """Generates visual representations of audio for UI feedback."""

    @staticmethod
    def extract_waveform(samples: np.ndarray, num_points: int = 100) -> list[float]:
        """Downsample audio to ``num_points`` normalized amplitude values."""
        if len(samples) == 0:
            return [0.0] * num_points

        indices = np.linspace(0, len(samples) - 1, num_points, dtype=int)
        downsampled = np.abs(samples[indices])

        peak = np.max(downsampled)
        if peak > 0:
            downsampled = downsampled / peak

        return downsampled.tolist()

    @staticmethod
    def estimate_loudness(samples: np.ndarray) -> float:
        """Estimate perceived loudness using simplified LUFS calculation."""
        if len(samples) == 0:
            return float("-inf")

        rms = np.sqrt(np.mean(samples**2))

        if rms == 0.0:
            return float("-inf")

        loudness_db = 20.0 * np.log10(max(rms, 1e-6))
        return loudness_db


class PersonalityAudioProfile:
    """Audio characteristics for voice personality profiles."""

    def __init__(
        self,
        name: str,
        target_rms: float = 0.5,
        presence_boost_db: float = 0.0,
        warmth_adjustment: float = 1.0,
    ):
        self.name = name
        self.target_rms = target_rms
        self.presence_boost_db = presence_boost_db
        self.warmth_adjustment = warmth_adjustment

    def apply_profile(self, samples: np.ndarray) -> np.ndarray:
        """Apply personality profile to audio samples."""
        current_rms = AudioNormalizer.calculate_rms(samples)
        if current_rms > 0:
            samples = samples * (self.target_rms / current_rms)

        # Note: actual frequency-domain processing would require FFT;
        # placeholder for future enhancement (see IMPL.md follow-up).
        return samples


# Predefined personality profiles
AGENT_PROFILES = {
    "hephaestus": PersonalityAudioProfile(
        "hephaestus", target_rms=0.48, presence_boost_db=1.5, warmth_adjustment=1.1
    ),
    "metis": PersonalityAudioProfile(
        "metis", target_rms=0.50, presence_boost_db=2.0, warmth_adjustment=0.95
    ),
    "kallos": PersonalityAudioProfile(
        "kallos", target_rms=0.52, presence_boost_db=1.0, warmth_adjustment=1.05
    ),
    "mneme": PersonalityAudioProfile(
        "mneme", target_rms=0.48, presence_boost_db=0.5, warmth_adjustment=1.15
    ),
    "techne": PersonalityAudioProfile(
        "techne", target_rms=0.49, presence_boost_db=1.8, warmth_adjustment=1.0
    ),
    "dokimasia": PersonalityAudioProfile(
        "dokimasia", target_rms=0.50, presence_boost_db=1.2, warmth_adjustment=1.05
    ),
}


__all__ = [
    "AGENT_PROFILES",
    "AudioFadeEffect",
    "AudioMetrics",
    "AudioNormalizer",
    "AudioVisualizer",
    "PersonalityAudioProfile",
]
