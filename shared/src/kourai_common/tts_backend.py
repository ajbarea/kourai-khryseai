"""TTS voice config + agent → voice mapping.

Holds the backend-agnostic data classes shared across the TTS path. The
``TTSBackend`` ABC + Kokoro/Edge backend pair retired with M19 Phase 3
once vn_bridge moved onto ``RealtimeTTSEngine.synthesize_to_wav``; only
the voice-config primitives remain.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TTSVoiceConfig:
    """Backend-agnostic voice configuration.

    Attributes:
        name: Human-readable voice name (e.g. "Sarah").
        voice_id: Backend-specific identifier (e.g. "af_sarah" for Kokoro).
        lang_code: Language code for the backend (Kokoro: "a" American /
                   "b" British).
        speed: Playback speed multiplier (1.0 = normal, valid range 0.5-2.0).
        pitch: Pitch multiplier (1.0 = normal, valid range 0.5-2.0).
        emotion: Emotion hint (backend-dependent, may be ignored).
    """

    name: str
    voice_id: str
    lang_code: str = "a"
    speed: float = 1.0
    pitch: float = 1.0
    emotion: str = "default"

    def __post_init__(self) -> None:
        if not 0.5 <= self.speed <= 2.0:
            raise ValueError(f"speed must be between 0.5 and 2.0, got {self.speed}")
        if not 0.5 <= self.pitch <= 2.0:
            raise ValueError(f"pitch must be between 0.5 and 2.0, got {self.pitch}")
        if self.lang_code not in ("a", "b"):
            raise ValueError(
                f"lang_code must be 'a' (American) or 'b' (British), got '{self.lang_code}'"
            )


# Each agent gets a unique Kokoro voice with per-agent prosody tuning.
AGENT_VOICE_MAP: dict[str, TTSVoiceConfig] = {
    "hephaestus": TTSVoiceConfig("Michael", "am_michael", speed=0.95),
    "metis": TTSVoiceConfig("Sarah", "af_sarah", speed=0.90, pitch=1.1),
    "kallos": TTSVoiceConfig("Bella", "af_bella", speed=1.05, pitch=1.15),
    "mneme": TTSVoiceConfig("Nicole", "af_nicole", speed=0.92, pitch=0.95),
    "techne": TTSVoiceConfig("Emma", "bf_emma", lang_code="b", speed=0.93, pitch=1.05),
    "dokimasia": TTSVoiceConfig("Jessica", "af_jessica", speed=0.88),
    "puck": TTSVoiceConfig("Adam", "am_adam", speed=1.05),
    "cupid": TTSVoiceConfig("Sky", "af_sky", speed=0.95, pitch=1.1),
    "aidos": TTSVoiceConfig("Kore", "af_kore", speed=0.90, pitch=0.95),
    "aletheia": TTSVoiceConfig("Nova", "af_nova", speed=0.93),
}

_DEFAULT_VOICE = TTSVoiceConfig("Heart", "af_heart")


def get_voice_for_agent(agent_name: str | None) -> TTSVoiceConfig:
    """Resolve an agent name to its voice config, falling back to default."""
    if agent_name is None:
        return _DEFAULT_VOICE
    return AGENT_VOICE_MAP.get(agent_name.lower(), _DEFAULT_VOICE)
