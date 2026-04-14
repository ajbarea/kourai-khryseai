"""Audio runtime environment helpers.

Configure SDL audio backend defaults for predictable cross-platform behavior.
"""

from __future__ import annotations

import logging
import os
import sys
from ctypes.util import find_library

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
