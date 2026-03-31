"""TTS backend abstraction — pluggable speech synthesis interface.

Defines the TTSBackend protocol so the GUI and VN bridge can swap between
Kokoro, edge-tts, or any future engine without touching consumer code.

Why an ABC instead of Protocol: we want runtime isinstance() checks so
the settings layer can validate backend types at startup.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from anyio import Path as AnyioPath

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TTSVoiceConfig:
    """Backend-agnostic voice configuration.

    Attributes:
        name: Human-readable voice name (e.g. "Sarah").
        voice_id: Backend-specific identifier (e.g. "af_sarah" for Kokoro,
                  "en-US-AriaNeural" for edge-tts).
        lang_code: Language code for the backend (e.g. "a" for American English
                   in Kokoro, ignored by edge-tts).
        speed: Playback speed multiplier (1.0 = normal, valid range 0.5–2.0).
        pitch: Pitch multiplier (1.0 = normal, valid range 0.5–2.0).
        emotion: Emotion hint (backend-dependent, may be ignored).
    """

    name: str
    voice_id: str
    lang_code: str = "a"
    speed: float = 1.0
    pitch: float = 1.0
    emotion: str = "default"

    def __post_init__(self) -> None:
        """Validate voice config on instantiation."""
        # Validate speed range (typical TTS range: 0.5x–2.0x)
        if not 0.5 <= self.speed <= 2.0:
            raise ValueError(f"speed must be between 0.5 and 2.0, got {self.speed}")

        # Validate pitch range
        if not 0.5 <= self.pitch <= 2.0:
            raise ValueError(f"pitch must be between 0.5 and 2.0, got {self.pitch}")

        # Validate lang_code (Kokoro-specific: "a" = American, "b" = British)
        if self.lang_code not in ("a", "b"):
            raise ValueError(
                f"lang_code must be 'a' (American) or 'b' (British), got '{self.lang_code}'"
            )


# ── Agent → Voice mapping (shared across all backends) ───────────────────────

# Each agent gets a unique Kokoro voice with per-agent prosody tuning.
# When using edge-tts fallback, tts_edge.py maps these to Edge Neural voices.
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


# ── Backend ABC ──────────────────────────────────────────────────────────────


class TTSBackend(ABC):
    """Abstract base for pluggable TTS backends.

    Subclasses must implement synthesize() and available_voices().
    synthesize_to_file() has a default implementation that writes bytes to disk.
    """

    @abstractmethod
    async def synthesize(self, text: str, voice: TTSVoiceConfig) -> bytes:
        """Generate audio bytes from text.

        Returns PCM WAV bytes (preferred) or MP3 bytes depending on backend.
        """
        ...

    @abstractmethod
    def stream_synthesize(self, text: str, voice: TTSVoiceConfig) -> AsyncGenerator[bytes, None]:
        """Yield audio chunks as they are generated for low-latency playback.

        Each chunk should be a valid, playable audio segment (e.g., a WAV chunk
        or MP3 frame).
        """
        ...

    async def synthesize_to_file(self, text: str, voice: TTSVoiceConfig, output: Path) -> Path:
        """Generate audio and save to file. Returns the output path."""
        audio_bytes = await self.synthesize(text, voice)
        anyio_output = AnyioPath(output)
        await anyio_output.parent.mkdir(parents=True, exist_ok=True)
        await anyio_output.write_bytes(audio_bytes)
        logger.debug("TTS audio saved: %s (%d bytes)", output, len(audio_bytes))
        return output

    @abstractmethod
    def available_voices(self) -> list[TTSVoiceConfig]:
        """List voices available from this backend."""
        ...

    @property
    def sample_rate(self) -> int:
        """Audio sample rate in Hz. Subclasses may override."""
        return 24000
