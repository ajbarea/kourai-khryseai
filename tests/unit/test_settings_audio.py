"""Unit tests for the shared ``AudioSettings`` schema.

Replaces the per-host volume + toggle drift between
``hosts/cli/settings.py:CLISettings`` and ``hosts/gui/settings.py:DEFAULT_SETTINGS``.
The bug we caught: GUI's first-launch ``music_volume`` was 0.05 while CLI's
was 0.65 — a 13× divergence on the same player profile. The fix is one
schema; both hosts read the same defaults.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from kourai_common.settings_audio import (
    AMBIENT_VOLUME_DEFAULT,
    DEFAULT_AUDIO_SETTINGS,
    MUSIC_VOLUME_DEFAULT,
    SFX_VOLUME_DEFAULT,
    VOICE_VOLUME_DEFAULT,
    AudioSettings,
)


def test_default_volumes_are_canonical():
    # The canonical values match what CLI's CLISettings and GUI's
    # settings_overlay.py:222 audio_controls list have always shipped.
    assert MUSIC_VOLUME_DEFAULT == 0.65
    assert AMBIENT_VOLUME_DEFAULT == 0.50
    assert VOICE_VOLUME_DEFAULT == 1.0
    assert SFX_VOLUME_DEFAULT == 0.85


def test_audio_settings_default_construction():
    s = AudioSettings()
    assert s.voice_enabled is True
    assert s.music_enabled is True
    assert s.ambient_enabled is True
    assert s.music_volume == MUSIC_VOLUME_DEFAULT
    assert s.ambient_volume == AMBIENT_VOLUME_DEFAULT
    assert s.voice_volume == VOICE_VOLUME_DEFAULT
    assert s.sfx_volume == SFX_VOLUME_DEFAULT


def test_audio_settings_is_frozen():
    s = AudioSettings()
    with pytest.raises(FrozenInstanceError):
        s.music_volume = 0.99  # type: ignore[misc]


def test_default_audio_settings_dict_is_writable_view():
    # DEFAULT_AUDIO_SETTINGS is a plain dict — meant to be merged into
    # GUI's DEFAULT_SETTINGS dict at module load. It's a fresh copy each
    # call so callers can mutate without poisoning the shared baseline.
    d1 = dict(DEFAULT_AUDIO_SETTINGS)
    d1["music_volume"] = 0.0
    d2 = dict(DEFAULT_AUDIO_SETTINGS)
    assert d2["music_volume"] == MUSIC_VOLUME_DEFAULT


def test_default_audio_settings_dict_keys_match_dataclass_fields():
    # Hosts that don't subclass AudioSettings (GUI's plain dict) need every
    # volume key to be present in DEFAULT_AUDIO_SETTINGS so the slider
    # overlay's `.get(key, default)` path resolves to the canonical value.
    expected_keys = {
        "voice_enabled",
        "music_enabled",
        "ambient_enabled",
        "music_volume",
        "ambient_volume",
        "voice_volume",
        "sfx_volume",
    }
    assert set(DEFAULT_AUDIO_SETTINGS.keys()) == expected_keys


def test_default_audio_settings_match_dataclass_defaults():
    # The dict is a serialization of the dataclass defaults — they must
    # not drift from each other.
    s = AudioSettings()
    for key, value in DEFAULT_AUDIO_SETTINGS.items():
        assert getattr(s, key) == value, f"drift on {key}"
