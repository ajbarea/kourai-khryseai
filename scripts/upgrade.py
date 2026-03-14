#!/usr/bin/env python
"""Update Python dependencies using uv lock.

Upgrades all dependencies to their latest compatible versions.
Creates a backup of uv.lock before making changes.

Usage:
    python scripts/upgrade.py

Dependencies: uv
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


def log_info(msg: str) -> None:
    """Log info message."""
    logger.info(f"ℹ {msg}")


def log_success(msg: str) -> None:
    """Log success message."""
    logger.info(f"✓ {msg}")


def log_warning(msg: str) -> None:
    """Log warning message."""
    logger.warning(f"⚠ {msg}")


def log_error(msg: str) -> None:
    """Log error message."""
    logger.error(f"✗ {msg}")


def run_command(cmd: list[str], check: bool = True) -> bool:
    """Run a shell command and return success status."""
    executable = shutil.which(cmd[0])
    if not executable:
        log_error(f"Command not found: {cmd[0]}")
        return False

    try:
        result = subprocess.run([executable, *cmd[1:]], cwd=Path(__file__).parent.parent)  # noqa: S603 — command is allowlisted ('uv', etc.); no untrusted input.
        if check and result.returncode != 0:
            return False
        return result.returncode == 0
    except Exception as e:
        log_error(f"Error running {cmd[0]}: {e}")
        return False


def main() -> int:
    """Main upgrade workflow."""
    repo_root = Path(__file__).parent.parent
    lock_file = repo_root / "uv.lock"

    # Check for uv
    if not shutil.which("uv"):
        log_error("uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh")
        return 1

    # Backup uv.lock
    if lock_file.exists():
        timestamp = str(int(datetime.now().timestamp()))
        backup_file = repo_root / f"uv.lock.backup.{timestamp}"
        shutil.copy(lock_file, backup_file)
        log_success(f"Backed up to {backup_file.name}")

        # Keep only the last 3 backups
        backups = sorted(repo_root.glob("uv.lock.backup.*"))
        for old_backup in backups[:-3]:
            old_backup.unlink()

    log_info("Upgrading dependencies...")
    if not run_command(["uv", "lock", "--upgrade", "-q"]):
        log_error("Failed to upgrade lock file")
        return 1
    log_success("Lock file updated")

    log_info("Syncing local environment...")
    if not run_command(["uv", "sync", "--frozen", "--all-packages", "-q"]):
        log_error("Failed to sync environment")
        return 1
    log_success("Environment synced")

    logger.info("")
    log_warning("Next: Review (git diff), Test, and Commit.")

    # Platform-specific restore hints
    if sys.platform == "win32":
        log_info("Restore (Windows): copy uv.lock.backup.* uv.lock (use latest backup)")
    else:
        log_info("Restore (Mac/Linux): cp $(ls -t uv.lock.backup.* | head -n1) uv.lock && uv sync")
    log_info("OR simply run: uv lock --upgrade && uv sync")

    return 0


if __name__ == "__main__":
    sys.exit(main())
