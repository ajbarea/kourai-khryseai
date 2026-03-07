"""Tests for GUI display-mode helpers."""

from __future__ import annotations

import pygame
import sys

from hosts.gui.display_modes import (
    DISPLAY_MODE_BORDERLESS,
    DISPLAY_MODE_FULLSCREEN,
    DISPLAY_MODE_WINDOWED,
    build_display_mode_spec,
    clamp_windowed_size,
    get_saved_windowed_size,
    normalize_display_mode,
    save_windowed_size,
)


class _SettingsStub:
    def __init__(self, initial: dict | None = None) -> None:
        self.values = dict(initial or {})

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def set(self, key: str, value) -> None:
        self.values[key] = value


def test_normalize_display_mode_defaults_to_windowed() -> None:
    assert normalize_display_mode("unexpected") == DISPLAY_MODE_WINDOWED
    assert normalize_display_mode(None) == DISPLAY_MODE_WINDOWED


def test_build_display_mode_spec_windowed_centers_window() -> None:
    spec = build_display_mode_spec(DISPLAY_MODE_WINDOWED, (1600, 900), (1920, 1080))

    assert spec.mode == DISPLAY_MODE_WINDOWED
    assert spec.size == (1600, 900)
    assert spec.flags == pygame.RESIZABLE
    assert spec.position == (160, 90)


def test_build_display_mode_spec_borderless_uses_desktop_size() -> None:
    spec = build_display_mode_spec(DISPLAY_MODE_BORDERLESS, (1600, 900), (1920, 1080))

    assert spec.mode == DISPLAY_MODE_BORDERLESS
    assert spec.size == (1920, 1080)
    assert spec.flags == pygame.NOFRAME
    assert spec.position == (0, 0)


def test_build_display_mode_spec_fullscreen_uses_desktop_size() -> None:
    spec = build_display_mode_spec(DISPLAY_MODE_FULLSCREEN, (1600, 900), (1920, 1080))

    assert spec.mode == DISPLAY_MODE_FULLSCREEN
    assert spec.size == (1920, 1080)
    if sys.platform == "win32":
        assert spec.flags == pygame.NOFRAME
        assert spec.position == (0, 0)
    else:
        assert spec.flags == pygame.FULLSCREEN
        assert spec.position is None


def test_get_saved_windowed_size_uses_adaptive_default_when_unset() -> None:
    settings = _SettingsStub()

    assert get_saved_windowed_size(settings, (1920, 1080)) == (1600, 900)


def test_get_saved_windowed_size_clamps_to_desktop() -> None:
    settings = _SettingsStub({"windowed_width": 3000, "windowed_height": 2000})

    assert get_saved_windowed_size(settings, (1920, 1080)) == (1920, 1080)


def test_clamp_windowed_size_enforces_minimum_when_possible() -> None:
    assert clamp_windowed_size((640, 360), (1920, 1080)) == (960, 540)


def test_save_windowed_size_persists_values() -> None:
    settings = _SettingsStub()

    save_windowed_size(settings, (1440, 810))

    assert settings.values["windowed_width"] == 1440
    assert settings.values["windowed_height"] == 810
