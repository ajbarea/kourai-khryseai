"""Audio utilities and effects for enhanced TTS playback.

Provides volume normalization, fade effects, and audio visualization support
for polished dialogue playback with personality-matched audio characteristics.
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
        """Normalize audio amplitude to prevent clipping.

        Args:
            samples: Audio samples (typically float32 -1.0 to 1.0).
            target_level: Target peak level (0.0-1.0).

        Returns:
            Normalized audio samples.
        """
        if len(samples) == 0:
            return samples

        peak = np.max(np.abs(samples))
        if peak == 0.0:
            return samples

        return samples * (target_level / peak)

    @staticmethod
    def calculate_rms(samples: np.ndarray) -> float:
        """Calculate RMS (Root Mean Square) level for loudness estimation.

        Args:
            samples: Audio samples.

        Returns:
            RMS level (0.0-1.0).
        """
        if len(samples) == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples**2)))


class AudioFadeEffect:
    """Fade in/out effects for smooth audio transitions."""

    @staticmethod
    def apply_fade_in(
        samples: np.ndarray, duration_ms: float, sample_rate: int = 44100
    ) -> np.ndarray:
        """Apply fade-in effect.

        Args:
            samples: Audio samples.
            duration_ms: Fade duration in milliseconds.
            sample_rate: Sample rate in Hz.

        Returns:
            Audio with fade-in applied.
        """
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
        """Apply fade-out effect.

        Args:
            samples: Audio samples.
            duration_ms: Fade duration in milliseconds.
            sample_rate: Sample rate in Hz.

        Returns:
            Audio with fade-out applied.
        """
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
        """Extract simplified waveform for visualization.

        Args:
            samples: Audio samples.
            num_points: Number of waveform points to extract.

        Returns:
            List of normalized amplitude values (0.0-1.0).
        """
        if len(samples) == 0:
            return [0.0] * num_points

        # Downsample audio to num_points
        indices = np.linspace(0, len(samples) - 1, num_points, dtype=int)
        downsampled = np.abs(samples[indices])

        # Normalize to 0-1
        peak = np.max(downsampled)
        if peak > 0:
            downsampled = downsampled / peak

        return downsampled.tolist()

    @staticmethod
    def estimate_loudness(samples: np.ndarray) -> float:
        """Estimate perceived loudness using simplified LUFS calculation.

        Args:
            samples: Audio samples.

        Returns:
            Estimated loudness in LUFS (relative scale).
        """
        if len(samples) == 0:
            return float("-inf")

        # Simplified loudness calculation using RMS
        rms = np.sqrt(np.mean(samples**2))

        if rms == 0.0:
            return float("-inf")

        # Convert to dB scale
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
        """Initialize personality audio profile.

        Args:
            name: Profile name (agent name).
            target_rms: Target RMS level (0.0-1.0).
            presence_boost_db: Presence (high-frequency) boost in dB.
            warmth_adjustment: Warmth (low-frequency) adjustment factor.
        """
        self.name = name
        self.target_rms = target_rms
        self.presence_boost_db = presence_boost_db
        self.warmth_adjustment = warmth_adjustment

    def apply_profile(self, samples: np.ndarray) -> np.ndarray:
        """Apply personality profile to audio.

        Args:
            samples: Audio samples.

        Returns:
            Audio with personality profile applied.
        """
        # Apply RMS normalization
        current_rms = AudioNormalizer.calculate_rms(samples)
        if current_rms > 0:
            samples = samples * (self.target_rms / current_rms)

        # Note: Actual frequency domain processing would require FFT
        # This is a placeholder for future enhancement
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
