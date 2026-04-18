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

from kourai_common.dev_log import LOG


def _check_wsl_audio_runtime() -> None:
    """Report WSLg audio runtime status when running inside WSL."""
    if not os.environ.get("WSL_DISTRO_NAME"):
        return

    pulse_server = os.environ.get("PULSE_SERVER")
    if not pulse_server:
        print("  o WSLg audio: PULSE_SERVER not set")
        LOG.event("INFO", "WSLg audio: PULSE_SERVER not set")
        return

    has_pulse = bool(find_library("pulse")) and bool(find_library("pulse-simple"))
    if has_pulse:
        print("  + WSLg audio: PulseAudio runtime detected")
        LOG.event("INFO", "WSLg audio: PulseAudio runtime detected")
        return

    print("  o WSLg audio: PulseAudio runtime missing (install libpulse0 pulseaudio-utils)")
    LOG.event("WARN", "WSLg audio: PulseAudio runtime missing (libpulse0 pulseaudio-utils)")


def _run_checks() -> int:
    print("\n  Environment Check")
    print("=" * 60)
    LOG.event("INFO", "Checking environment...")

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
            LOG.event("INFO", f"{name}: {result}")
            results.append(True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            if name == "Docker":
                print(f"  o {name}: not found (optional)")
                LOG.event("INFO", f"{name} not found (optional)")
                results.append(True)
            else:
                print(f"  x {name}: not found")
                LOG.event("ERROR", f"{name} not found")
                results.append(False)

    _check_wsl_audio_runtime()

    print("=" * 60)
    if all(results):
        print("+ All required tools available\n")
        LOG.event("INFO", "Environment check passed")
        return 0
    print("x Some required tools missing\n")
    LOG.event("ERROR", "Environment check failed")
    return 1


def main() -> int:
    LOG.open("check-env")
    LOG.session_header("check-env", sys.argv[1:])
    rc = 1
    try:
        rc = _run_checks()
    finally:
        LOG.session_footer(rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
