"""Shared audio-settings schema across CLI + GUI hosts.

Cross-host duplication previously left ``music_volume`` defaults diverging
by 13× (CLI 0.65 vs GUI ``DEFAULT_SETTINGS`` 0.05) — same player switching
hosts heard a jarring loudness jump. Now both hosts read these constants;
slider overlays and CLI ``/settings`` panels stay independent.

Canonical defaults come from the values the CLI and GUI's slider-overlay
``audio_controls`` list have always shipped — only GUI's secondary
``DEFAULT_SETTINGS`` dict had drifted to silent-music territory.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

# --- canonical defaults ---

MUSIC_VOLUME_DEFAULT: float = 0.65
AMBIENT_VOLUME_DEFAULT: float = 0.50
VOICE_VOLUME_DEFAULT: float = 1.0
SFX_VOLUME_DEFAULT: float = 0.85


@dataclass(frozen=True)
class AudioSettings:
    """Cross-host audio toggles + volumes.

    Frozen so the schema is hashable / safely shareable; hosts copy values
    out into their own mutable settings stores.
    """

    voice_enabled: bool = True
    music_enabled: bool = True
    ambient_enabled: bool = True
    music_volume: float = MUSIC_VOLUME_DEFAULT
    ambient_volume: float = AMBIENT_VOLUME_DEFAULT
    voice_volume: float = VOICE_VOLUME_DEFAULT
    sfx_volume: float = SFX_VOLUME_DEFAULT


def _build_default_dict() -> dict[str, bool | float]:
    """Snapshot of AudioSettings() defaults — fresh dict each call."""
    s = AudioSettings()
    return {f.name: getattr(s, f.name) for f in fields(s)}


# Module-level snapshot used by GUI's plain-dict settings store.
# Construct lazily-eager: built once at import time, callers should
# treat as read-only (or wrap in dict() before mutating).
DEFAULT_AUDIO_SETTINGS: dict[str, bool | float] = _build_default_dict()


__all__ = [
    "AMBIENT_VOLUME_DEFAULT",
    "DEFAULT_AUDIO_SETTINGS",
    "MUSIC_VOLUME_DEFAULT",
    "SFX_VOLUME_DEFAULT",
    "VOICE_VOLUME_DEFAULT",
    "AudioSettings",
]
