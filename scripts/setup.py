"""Setup wrapper for uv sync and optional HF-Mount configuration.

Handles cross-platform setup including Python dependency installation
and optional HuggingFace Storage Buckets configuration.

Usage:
    python scripts/setup.py
    python scripts/setup.py --force-artifacts  # Force re-setup artifacts
"""

from __future__ import annotations

import os
import shutil
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


def _setup_ollama() -> None:
    """Check Ollama connectivity and report status.

    Models are pulled on demand by Ollama at first LLM call — no bulk download needed.
    """
    print()
    print("  Ollama Setup (KOURAI_PROVIDER=local)")
    print("-" * 40)

    # Health check
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print("  x Ollama is installed but not responding (is 'ollama serve' running?)")
            logger.warning("Ollama list failed: %s", result.stderr.strip())
            return
    except FileNotFoundError:
        print("  x Ollama not found")
        return

    print("  + Ollama is running")

    # Report which models are already available
    lines = result.stdout.strip().splitlines()[1:]
    installed = [line.split()[0] for line in lines if line.strip()]
    if installed:
        for model in installed:
            print(f"  + {model}")
    else:
        print("  i No models pulled yet — Ollama will download them on first use")
        print("    Tip: pre-pull a small model with: ollama pull llama3.3:8b (~5GB)")


def main() -> int:
    """Main setup workflow.

    Returns:
        0 on success, 1 on failure.
    """
    force_artifacts = "--force-artifacts" in sys.argv

    print("\n  Kourai Setup")
    print("=" * 60)
    logger.info("Starting Kourai setup...")

    # Install dependencies
    if not run_step(
        ["uv", "sync", "--all-packages"],
        "Installing dependencies",
        required=True,
    ):
        print("\n" + "=" * 60)
        print("x Setup failed")
        print("=" * 60 + "\n")
        logger.error("Setup failed")
        return 1

    # Optional HF bucket setup (only if HF_TOKEN is set and not already configured)
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

    # Optional Ollama setup (only when KOURAI_PROVIDER=local)
    provider = os.environ.get("KOURAI_PROVIDER", "").lower()
    if provider == "local" and shutil.which("ollama"):
        _setup_ollama()
    elif provider == "local":
        print()
        print("  ! KOURAI_PROVIDER=local but ollama not found in PATH")
        print("    Install from: https://ollama.com/")

    print("\n" + "=" * 60)
    print("+ Setup completed successfully")
    print("=" * 60 + "\n")
    logger.info("Setup completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
