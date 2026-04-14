"""Unit tests for cross-platform SDL audio backend configuration."""

from __future__ import annotations

import os
from unittest.mock import patch

from kourai_common import audio_env


def test_configure_sdl_audio_driver_respects_explicit_override(monkeypatch) -> None:
    monkeypatch.setenv("SDL_AUDIODRIVER", "alsa")
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    monkeypatch.setenv("PULSE_SERVER", "unix:/mnt/wslg/PulseServer")

    assert audio_env.configure_sdl_audio_driver() == "alsa"
    assert os.environ["SDL_AUDIODRIVER"] == "alsa"


def test_configure_sdl_audio_driver_prefers_wsl_pulseaudio(monkeypatch) -> None:
    monkeypatch.delenv("SDL_AUDIODRIVER", raising=False)
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    monkeypatch.setenv("PULSE_SERVER", "unix:/mnt/wslg/PulseServer")

    with patch("kourai_common.audio_env.find_library", return_value="libpresent"):
        selected = audio_env.configure_sdl_audio_driver()

    assert selected == "pulseaudio"
    assert os.environ["SDL_AUDIODRIVER"] == "pulseaudio"


def test_configure_sdl_audio_driver_warns_when_wsl_pulse_missing(monkeypatch, caplog) -> None:
    monkeypatch.delenv("SDL_AUDIODRIVER", raising=False)
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    monkeypatch.setenv("PULSE_SERVER", "unix:/mnt/wslg/PulseServer")

    with patch("kourai_common.audio_env.find_library", return_value=None):
        selected = audio_env.configure_sdl_audio_driver()

    assert selected is None
    assert "libpulse runtime is missing" in caplog.text


def test_configure_sdl_audio_driver_uses_dummy_headless_linux(monkeypatch) -> None:
    monkeypatch.delenv("SDL_AUDIODRIVER", raising=False)
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.delenv("PULSE_SERVER", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(audio_env.sys, "platform", "linux", raising=False)

    selected = audio_env.configure_sdl_audio_driver()

    assert selected == "dummy"
    assert os.environ["SDL_AUDIODRIVER"] == "dummy"
