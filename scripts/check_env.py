"""Check environment for required tools.

Verifies that uv, Python, and Docker are available before running setup.

Usage:
    python scripts/check_env.py
"""

from __future__ import annotations

import subprocess
import sys

try:
    from scripts.logging_utils import setup_logger
except ModuleNotFoundError:
    from logging_utils import setup_logger

logger = setup_logger(__name__, "check_env.log")


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
