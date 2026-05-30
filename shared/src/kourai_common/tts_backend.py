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


@dataclass(frozen=True)
class ChatterboxExpression:
    """Per-maiden Chatterbox generation params (M6 step 3).

    ``exaggeration`` is Chatterbox's emotion-intensity control (valid 0.25-2.0;
    0.5 is its natural default); ``cfg_weight`` is the classifier-free-guidance
    weight (0.0-1.0), which doubles as the pacing lever now that the engine has
    no Kokoro-style speed knob — lower is quicker, higher more deliberate.
    ``research(2026-05)``: Chatterbox / RealtimeTTS generation params + ranges.
    """

    exaggeration: float
    cfg_weight: float

    def __post_init__(self) -> None:
        if not 0.25 <= self.exaggeration <= 2.0:
            raise ValueError(f"exaggeration must be between 0.25 and 2.0, got {self.exaggeration}")
        if not 0.0 <= self.cfg_weight <= 1.0:
            raise ValueError(f"cfg_weight must be between 0.0 and 1.0, got {self.cfg_weight}")


# Per-maiden Chatterbox expression cast (M6 step 3); the dark ``chatterbox``
# engine seam consumes it. Derived from each maiden's documented register in
# ``tools/voice-lab/VOICE_CASTING_PLAN.md``: the ElevenLabs ``style`` (0.10 Aidos
# → 0.50 Cupid) maps to ``exaggeration`` in [0.35, 0.70] — expressive but inside
# the plan's "avoid cartoon extremes" band — and each maiden's Kokoro ``speed``
# (AGENT_VOICE_MAP) maps inversely to ``cfg_weight`` in [0.40, 0.60] so the
# deliberate/animated pacing survives the switch from Kokoro (speed knob) to
# Chatterbox (none). Starting points: tune by ear, then A/B before the seam lights.
AGENT_EXPRESSION_MAP: dict[str, ChatterboxExpression] = {
    "hephaestus": ChatterboxExpression(exaggeration=0.48, cfg_weight=0.52),
    "metis": ChatterboxExpression(exaggeration=0.53, cfg_weight=0.58),
    "kallos": ChatterboxExpression(exaggeration=0.66, cfg_weight=0.40),
    "mneme": ChatterboxExpression(exaggeration=0.44, cfg_weight=0.55),
    "techne": ChatterboxExpression(exaggeration=0.51, cfg_weight=0.54),
    "dokimasia": ChatterboxExpression(exaggeration=0.46, cfg_weight=0.60),
    "puck": ChatterboxExpression(exaggeration=0.68, cfg_weight=0.40),
    "cupid": ChatterboxExpression(exaggeration=0.70, cfg_weight=0.52),
    "aidos": ChatterboxExpression(exaggeration=0.35, cfg_weight=0.58),
    "aletheia": ChatterboxExpression(exaggeration=0.39, cfg_weight=0.54),
}

# Chatterbox's documented natural default — the fallback for an unknown agent.
_DEFAULT_EXPRESSION = ChatterboxExpression(exaggeration=0.5, cfg_weight=0.5)


def get_expression_for_agent(agent_name: str | None) -> ChatterboxExpression:
    """Resolve an agent name to its Chatterbox expression, default if unknown."""
    if agent_name is None:
        return _DEFAULT_EXPRESSION
    return AGENT_EXPRESSION_MAP.get(agent_name.lower(), _DEFAULT_EXPRESSION)
