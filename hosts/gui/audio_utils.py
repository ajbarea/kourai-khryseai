"""GUI re-export shim for audio DSP helpers.

The pure-numpy logic (AudioMetrics, AudioNormalizer, AudioFadeEffect,
AudioVisualizer, PersonalityAudioProfile, AGENT_PROFILES) lives in
:mod:`kourai_common.audio_dsp` so any host with TTS playback can opt
into the same per-personality normalization. Existing GUI imports of
``hosts.gui.audio_utils`` continue to work unchanged.
"""

from __future__ import annotations

from kourai_common.audio_dsp import (
    AGENT_PROFILES,
    AudioFadeEffect,
    AudioMetrics,
    AudioNormalizer,
    AudioVisualizer,
    PersonalityAudioProfile,
)

__all__ = [
    "AGENT_PROFILES",
    "AudioFadeEffect",
    "AudioMetrics",
    "AudioNormalizer",
    "AudioVisualizer",
    "PersonalityAudioProfile",
]
