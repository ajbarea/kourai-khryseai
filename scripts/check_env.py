"""Check environment for required tools.

Verifies that uv, Python, and Docker are available before running setup.

Usage:
    python scripts/check_env.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from ctypes.util import find_library

try:
    from scripts.logging_utils import setup_logger
except ModuleNotFoundError:
    from logging_utils import setup_logger

logger = setup_logger(__name__, "check_env.log")


def _check_wsl_audio_runtime() -> None:
    """Report WSLg audio runtime status when running inside WSL."""
    if not os.environ.get("WSL_DISTRO_NAME"):
        return

    pulse_server = os.environ.get("PULSE_SERVER")
    if not pulse_server:
        print("  o WSLg audio: PULSE_SERVER not set")
        logger.info("o WSLg audio: PULSE_SERVER not set")
        return

    has_pulse = bool(find_library("pulse")) and bool(find_library("pulse-simple"))
    if has_pulse:
        print("  + WSLg audio: PulseAudio runtime detected")
        logger.info("+ WSLg audio: PulseAudio runtime detected")
        return

    print("  o WSLg audio: PulseAudio runtime missing (install libpulse0 pulseaudio-utils)")
    logger.warning("o WSLg audio: PulseAudio runtime missing (libpulse0 pulseaudio-utils)")


def main() -> int:
    """Verify required tools are available.

    Returns:
        0 if all required tools are available, 1 otherwise.
    """
    print("\n  Environment Check")
    print("=" * 60)
    logger.info("Checking environment...")

    checks = [
        ("uv", ["uv", "--version"]),
        ("Python", [sys.executable, "--version"]),
        ("Docker", ["docker", "--version"]),
    ]

    results: list[bool] = []
    for name, cmd in checks:
        try:
            result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()  # noqa: S603
            print(f"  + {name}: {result}")
            logger.info(f"+ {name}: {result}")
            results.append(True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            if name == "Docker":
                print(f"  o {name}: not found (optional)")
                logger.info(f"o {name} not found (optional)")
                results.append(True)
            else:
                print(f"  x {name}: not found")
                logger.error(f"x {name} not found")
                results.append(False)

    _check_wsl_audio_runtime()

    print("=" * 60)
    if all(results):
        print("+ All required tools available\n")
        logger.info("Environment check passed")
        return 0
    else:
        print("x Some required tools missing\n")
        logger.error("Environment check failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
