"""Setup wrapper for uv sync and optional HF-Mount configuration.

Handles cross-platform setup including Python dependency installation
and optional HuggingFace Storage Buckets configuration.

Usage:
    python scripts/setup.py
    python scripts/setup.py --force-artifacts  # Force re-setup artifacts
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

try:
    from scripts.logging_utils import setup_logger
except ModuleNotFoundError:
    from logging_utils import setup_logger

logger = setup_logger(__name__, "setup.log")

SETUP_MARKER = Path(".hf-buckets-configured")


def run_step(cmd: list[str], description: str, *, required: bool = True) -> bool:
    """Execute a setup step, printing progress and logging to file.

    Args:
        cmd: Command and arguments as a list of strings.
        description: Human-readable description for display and logging.
        required: If True, missing commands fail the step. If False, they are skipped.

    Returns:
        True if the step succeeded, False on failure.
    """
    print(f"  > {description}...")
    logger.info(f"Running: {description}")
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        print(f"  + {description}")
        logger.info(f"+ {description} completed")
        if result.stdout:
            logger.debug(result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        print(f"  x {description} failed (exit code {e.returncode})")
        logger.error(f"Failed: {description} (exit code {e.returncode})")
        if e.stdout:
            logger.debug(f"stdout: {e.stdout.strip()}")
        if e.stderr:
            logger.debug(f"stderr: {e.stderr.strip()}")
        return False
    except FileNotFoundError:
        if required:
            print(f"  x {description} failed (command not found)")
            logger.error(f"Failed: {description} - command not found in PATH")
            return False
        print(f"  ! {description} skipped (command not found)")
        logger.warning(f"Skipped: {description} - command not found in PATH")
        return True


def run_command(cmd: list[str]) -> int:
    """Backward-compatible command runner used by older tests/tooling."""
    try:
        result = subprocess.run(cmd, check=False)  # noqa: S603
    except FileNotFoundError:
        return 127
    return result.returncode


def should_setup_artifacts(force: bool = False) -> bool:
    """Check if artifacts setup is needed."""
    if force:
        return True

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        return False

    if SETUP_MARKER.exists():
        logger.info("HF bucket already configured (marker file exists)")
        return False

    return True


def mark_artifacts_configured() -> None:
    """Create marker file to indicate HF bucket has been configured."""
    SETUP_MARKER.write_text("# Marker file: HF bucket configured\n")
    logger.info(f"Created marker file: {SETUP_MARKER}")


def main() -> int:
    """Main setup workflow.

    Returns:
        0 on success, 1 on failure.
    """
    force_artifacts = "--force-artifacts" in sys.argv

    print("\n  Kourai Setup")
    print("=" * 60)
    logger.info("Starting Kourai setup...")

    # Step 1: Install dependencies
    if not run_step(
        ["uv", "sync", "--all-packages", "--no-active"],
        "Installing dependencies",
        required=True,
    ):
        print("\n" + "=" * 60)
        print("x Setup failed")
        print("=" * 60 + "\n")
        logger.error("Setup failed")
        return 1

    # Step 2: Optional HF bucket setup
    if should_setup_artifacts(force=force_artifacts):
        if run_step(
            ["uv", "run", "--no-active", "python", "scripts/setup_buckets.py"],
            "Setting up HuggingFace Storage Buckets",
            required=True,
        ):
            mark_artifacts_configured()
        else:
            print("\n" + "=" * 60)
            print("x Setup failed")
            print("=" * 60 + "\n")
            logger.error("Setup failed")
            return 1
    else:
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            print()
            print("  i HF_TOKEN not set (optional). To enable HuggingFace artifact storage:")
            print("    1. Get a write-scope token: https://huggingface.co/settings/tokens")
            print("    2. Add to .env:  HF_TOKEN=hf_xxx...")
            print("    3. Run: make setup")

    print("\n" + "=" * 60)
    print("+ Setup completed successfully")
    print("=" * 60 + "\n")
    logger.info("Setup completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
