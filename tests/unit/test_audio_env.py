"""Unit tests for cross-platform SDL audio backend configuration."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

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


# ===================================================================
# silence_alsa_lib_errors — ctypes noop handler for libasound
# ===================================================================


def test_silence_alsa_lib_errors_installs_handler(monkeypatch) -> None:
    """First call loads libasound, sets a no-op error handler, flips the
    module flag, and stashes the ctypes function so it's not GC'd."""
    monkeypatch.setattr(audio_env, "_alsa_silenced", False)
    monkeypatch.setattr(audio_env, "_ALSA_ERROR_HANDLER", None)
    monkeypatch.delenv("KOURAI_AUDIO_DEBUG", raising=False)

    fake_asound = MagicMock(name="libasound")
    with (
        patch("kourai_common.audio_env.find_library", return_value="libasound.so.2"),
        patch("kourai_common.audio_env.ctypes.cdll.LoadLibrary", return_value=fake_asound),
    ):
        audio_env.silence_alsa_lib_errors()

    fake_asound.snd_lib_error_set_handler.assert_called_once()
    assert audio_env._alsa_silenced is True
    assert audio_env._ALSA_ERROR_HANDLER is not None


def test_silence_alsa_lib_errors_idempotent(monkeypatch) -> None:
    """Second call after a successful install is a no-op — never re-loads
    libasound, so callers can sprinkle it at multiple init sites without
    leaking handler refs."""
    monkeypatch.setattr(audio_env, "_alsa_silenced", True)
    monkeypatch.setattr(audio_env, "_ALSA_ERROR_HANDLER", object())
    monkeypatch.delenv("KOURAI_AUDIO_DEBUG", raising=False)

    with patch("kourai_common.audio_env.ctypes.cdll.LoadLibrary") as load:
        audio_env.silence_alsa_lib_errors()

    load.assert_not_called()


def test_silence_alsa_lib_errors_skipped_when_debug_env_set(monkeypatch) -> None:
    """KOURAI_AUDIO_DEBUG=1 keeps the cascade visible so a developer
    diagnosing real audio failures isn't blinded by the fix."""
    monkeypatch.setattr(audio_env, "_alsa_silenced", False)
    monkeypatch.setattr(audio_env, "_ALSA_ERROR_HANDLER", None)
    monkeypatch.setenv("KOURAI_AUDIO_DEBUG", "1")

    with patch("kourai_common.audio_env.ctypes.cdll.LoadLibrary") as load:
        audio_env.silence_alsa_lib_errors()

    load.assert_not_called()
    assert audio_env._alsa_silenced is False


def test_silence_alsa_lib_errors_skipped_when_libasound_missing(monkeypatch) -> None:
    """Non-Linux hosts (macOS, Windows) lack libasound — bail out cleanly
    rather than raising on LoadLibrary."""
    monkeypatch.setattr(audio_env, "_alsa_silenced", False)
    monkeypatch.setattr(audio_env, "_ALSA_ERROR_HANDLER", None)
    monkeypatch.delenv("KOURAI_AUDIO_DEBUG", raising=False)

    with (
        patch("kourai_common.audio_env.find_library", return_value=None),
        patch("kourai_common.audio_env.ctypes.cdll.LoadLibrary") as load,
    ):
        audio_env.silence_alsa_lib_errors()

    load.assert_not_called()
    assert audio_env._alsa_silenced is False


def test_silence_alsa_lib_errors_handles_load_failure(monkeypatch) -> None:
    """find_library can return a name that nonetheless fails to load
    (mismatched soname, broken install). Don't crash — log and skip."""
    monkeypatch.setattr(audio_env, "_alsa_silenced", False)
    monkeypatch.setattr(audio_env, "_ALSA_ERROR_HANDLER", None)
    monkeypatch.delenv("KOURAI_AUDIO_DEBUG", raising=False)

    with (
        patch("kourai_common.audio_env.find_library", return_value="libasound.so.2"),
        patch(
            "kourai_common.audio_env.ctypes.cdll.LoadLibrary",
            side_effect=OSError("not found"),
        ),
    ):
        audio_env.silence_alsa_lib_errors()

    assert audio_env._alsa_silenced is False


# ===================================================================
# silence_audio_init_noise — fd-level stderr redirect for JACK
# ===================================================================


def test_silence_audio_init_noise_redirects_fd2(monkeypatch, tmp_path) -> None:
    """Inside the context manager, fd 2 points at /dev/null so libjack's
    fprintf-based error messages are dropped; on exit fd 2 is restored.
    Fork into a subprocess so we can dup the original stderr safely."""
    monkeypatch.delenv("KOURAI_AUDIO_DEBUG", raising=False)

    sentinel = tmp_path / "stderr-capture.txt"
    capture_fd = os.open(str(sentinel), os.O_WRONLY | os.O_CREAT, 0o644)
    saved_stderr = os.dup(2)
    try:
        os.dup2(capture_fd, 2)
        with audio_env.silence_audio_init_noise():
            os.write(2, b"INSIDE\n")
        os.write(2, b"OUTSIDE\n")
    finally:
        sys.stderr.flush()
        os.dup2(saved_stderr, 2)
        os.close(capture_fd)
        os.close(saved_stderr)

    captured = sentinel.read_bytes()
    assert b"OUTSIDE" in captured, "fd 2 must be restored after the context exits"
    assert b"INSIDE" not in captured, "writes to fd 2 inside the context must be dropped"


def test_silence_audio_init_noise_passthrough_when_debug_env_set(monkeypatch, tmp_path) -> None:
    """KOURAI_AUDIO_DEBUG=1 disables the redirect so devs see everything."""
    monkeypatch.setenv("KOURAI_AUDIO_DEBUG", "1")

    sentinel = tmp_path / "stderr-capture.txt"
    capture_fd = os.open(str(sentinel), os.O_WRONLY | os.O_CREAT, 0o644)
    saved_stderr = os.dup(2)
    try:
        os.dup2(capture_fd, 2)
        with audio_env.silence_audio_init_noise():
            os.write(2, b"INSIDE\n")
    finally:
        sys.stderr.flush()
        os.dup2(saved_stderr, 2)
        os.close(capture_fd)
        os.close(saved_stderr)

    captured = sentinel.read_bytes()
    assert b"INSIDE" in captured, "debug mode must pass writes through"


def test_silence_audio_init_noise_restores_on_exception(monkeypatch, tmp_path) -> None:
    """Exception inside the body must not leak the dup'd fd or leave
    fd 2 redirected — finally clause runs."""
    monkeypatch.delenv("KOURAI_AUDIO_DEBUG", raising=False)

    sentinel = tmp_path / "stderr-capture.txt"
    capture_fd = os.open(str(sentinel), os.O_WRONLY | os.O_CREAT, 0o644)
    saved_stderr = os.dup(2)
    try:
        os.dup2(capture_fd, 2)
        try:
            with audio_env.silence_audio_init_noise():
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        os.write(2, b"AFTER\n")
    finally:
        sys.stderr.flush()
        os.dup2(saved_stderr, 2)
        os.close(capture_fd)
        os.close(saved_stderr)

    captured = sentinel.read_bytes()
    assert b"AFTER" in captured, "fd 2 must be restored even when body raises"
