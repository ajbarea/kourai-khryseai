"""Setup wrapper for uv sync and optional HF-Mount configuration.

Handles cross-platform setup including Python dependency installation
and optional HuggingFace Storage Buckets configuration.

Usage:
    python scripts/setup.py
    python scripts/setup.py --force-artifacts  # Force re-setup artifacts
    uv run --no-active python scripts/setup.py
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

SETUP_MARKER = Path(".hf-buckets-configured")


def run_command(cmd: list[str]) -> int:
    """Run a command and return its exit code."""
    try:
        result = subprocess.run(cmd, shell=False)  # noqa: S603 — no untrusted input; called only with allowlisted commands
        return result.returncode
    except Exception as e:
        logger.error(f"Error running command: {e}")
        return 1


def should_setup_artifacts(force: bool = False) -> bool:
    """Check if artifacts setup is needed.

    Setup is needed if:
    1. --force-artifacts flag is set, OR
    2. HF_TOKEN is set AND setup marker doesn't exist

    Args:
        force: Force re-setup even if marker exists

    Returns:
        True if setup is needed, False otherwise
    """
    if force:
        return True

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        return False

    if SETUP_MARKER.exists():
        logger.info("ℹ️  HF bucket already configured (marker file exists)")
        return False

    return True


def mark_artifacts_configured() -> None:
    """Create marker file to indicate HF bucket has been configured."""
    SETUP_MARKER.write_text("# Marker file: HF bucket configured\n")
    logger.info(f"✅ Created marker file: {SETUP_MARKER}")


def main() -> int:
    """Main setup workflow."""
    force_artifacts = "--force-artifacts" in sys.argv

    logger.info("")
    logger.info("🔧 Installing Python dependencies...")
    if run_command(["uv", "sync", "--all-packages", "--no-active"]) != 0:
        logger.error("Failed to sync dependencies")
        return 1

    if should_setup_artifacts(force=force_artifacts):
        logger.info("")
        logger.info("🚀 Setting up HuggingFace Storage Buckets...")
        if run_command(["uv", "run", "--no-active", "python", "scripts/setup_buckets.py"]) == 0:
            mark_artifacts_configured()
            logger.info("✅ HF bucket configured!")
        else:
            logger.warning("⚠ HF bucket setup failed or incomplete")
            return 1
    else:
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            logger.info("")
            logger.info("ℹ️  HF_TOKEN not set (optional). To enable HuggingFace artifact storage:")
            logger.info("   1. Get a write-scope token: https://huggingface.co/settings/tokens")
            logger.info("   2. Add to .env:  HF_TOKEN=hf_xxx...")
            logger.info("   3. Run: make setup")

    logger.info("")
    logger.info("✅ Setup complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
