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


def test_audio_module_import_triggers_sdl_configure(monkeypatch) -> None:
    """Regression guard: ``configure_sdl_audio_driver`` was defined long
    before this PR but wasn't called anywhere — so AJ's WSL2 launches
    fell through to SDL's default ALSA backend and produced
    ``cannot find card '0'`` chatter on every CLI/GUI startup. Importing
    :mod:`kourai_common.audio` must now invoke the helper before
    pygame's audio subsystem initializes; this test ensures a future
    refactor doesn't silently un-wire it again."""
    import importlib

    from kourai_common import audio, audio_env

    # The wiring is at module load. Reload triggers it again with the
    # current `configure_sdl_audio_driver` (so a monkeypatched version
    # would be observed). Use monkeypatch instead of direct module-attr
    # assignment so (a) ty stops warning about implicit shadowing of the
    # function symbol and (b) restoration happens automatically on
    # teardown — no try/finally bookkeeping.
    calls: list[str | None] = []
    real = audio_env.configure_sdl_audio_driver

    def _spy() -> str | None:
        result = real()
        calls.append(result)
        return result

    monkeypatch.setattr(audio_env, "configure_sdl_audio_driver", _spy)
    monkeypatch.setattr(audio, "configure_sdl_audio_driver", _spy)
    importlib.reload(audio)

    assert calls, (
        "kourai_common.audio failed to call configure_sdl_audio_driver() "
        "at module load — SDL backend selection is no longer wired in."
    )
