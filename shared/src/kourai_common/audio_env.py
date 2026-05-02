"""Audio runtime environment helpers.

Configure SDL audio backend defaults for predictable cross-platform behavior,
and quiet PortAudio's ALSA/JACK device-enumeration cascade on systems that
route audio through PulseAudio (WSL2/WSLg) or have no audio device (CI).
"""

from __future__ import annotations

import contextlib
import ctypes
import logging
import os
import sys
from ctypes.util import find_library
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)


def _is_wsl() -> bool:
    return bool(os.environ.get("WSL_DISTRO_NAME"))


def _has_pulseaudio_runtime() -> bool:
    return bool(find_library("pulse")) and bool(find_library("pulse-simple"))


def _is_headless_linux() -> bool:
    if not sys.platform.startswith("linux"):
        return False
    return not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")


def configure_sdl_audio_driver() -> str | None:
    """Set SDL_AUDIODRIVER defaults when the user did not specify one.

    Returns the selected driver if one was set or already configured.
    """
    configured = os.environ.get("SDL_AUDIODRIVER")
    if configured:
        return configured

    # WSLg exposes PulseAudio via PULSE_SERVER. Prefer this backend explicitly
    # so SDL does not fall back to ALSA in environments without a hardware card.
    if _is_wsl() and os.environ.get("PULSE_SERVER"):
        if _has_pulseaudio_runtime():
            os.environ["SDL_AUDIODRIVER"] = "pulseaudio"
            logger.info("Configured SDL audio backend: pulseaudio (WSLg)")
            return "pulseaudio"

        logger.warning(
            "WSLg PulseAudio is configured but libpulse runtime is missing. "
            "Install with: sudo apt install -y libpulse0 pulseaudio-utils"
        )
        return None

    # In headless Linux environments (CI/cloud without GUI session), explicitly
    # use dummy audio to avoid noisy ALSA errors and startup failures.
    if _is_headless_linux():
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        logger.info("Configured SDL audio backend: dummy (headless Linux)")
        return "dummy"

    return None


_alsa_silenced: bool = False
_ALSA_ERROR_HANDLER: object | None = None


def _audio_debug_enabled() -> bool:
    return bool(os.environ.get("KOURAI_AUDIO_DEBUG"))


def silence_alsa_lib_errors() -> None:
    """Install a no-op libasound error handler so PortAudio's ALSA
    enumeration cascade doesn't write to stderr at TTS init.

    Idempotent. Skipped when ``KOURAI_AUDIO_DEBUG=1``.
    """
    global _alsa_silenced, _ALSA_ERROR_HANDLER
    if _alsa_silenced or _audio_debug_enabled():
        return
    if not find_library("asound"):
        return
    try:
        asound = ctypes.cdll.LoadLibrary("libasound.so.2")
    except OSError as exc:
        logger.debug("Skipping ALSA error suppression: %s", exc)
        return

    handler_t = ctypes.CFUNCTYPE(
        None,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
    )

    def _noop(
        filename: bytes | None,
        line: int,
        function: bytes | None,
        err: int,
        fmt: bytes | None,
    ) -> None:
        return

    _ALSA_ERROR_HANDLER = handler_t(_noop)
    asound.snd_lib_error_set_handler(_ALSA_ERROR_HANDLER)
    _alsa_silenced = True
    logger.debug("Installed no-op libasound error handler")


@contextlib.contextmanager
def silence_audio_init_noise() -> Iterator[None]:
    """Drop fd-level stderr to hide libjack's connect-error chatter.

    Wrap only the PyAudio constructor — the redirect catches everything
    on fd 2, so a wider window would swallow torch / HF Hub warnings.
    Skipped when ``KOURAI_AUDIO_DEBUG=1``.
    """
    if _audio_debug_enabled():
        yield
        return

    saved_fd = os.dup(2)
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    try:
        sys.stderr.flush()
        os.dup2(devnull_fd, 2)
        yield
    finally:
        sys.stderr.flush()
        os.dup2(saved_fd, 2)
        os.close(devnull_fd)
        os.close(saved_fd)
