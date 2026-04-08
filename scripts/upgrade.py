"""Update Python dependencies using uv lock.

Upgrades all dependencies to their latest compatible versions.
Creates a backup of uv.lock before making changes.

Usage:
    python scripts/upgrade.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    from scripts.logging_utils import setup_logger
except ModuleNotFoundError:
    from logging_utils import setup_logger

logger = setup_logger(__name__, "upgrade.log")


def run_step(cmd: list[str], description: str) -> bool:
    """Execute an upgrade step, printing progress and logging to file.

    Args:
        cmd: Command and arguments as a list of strings.
        description: Human-readable description for display and logging.

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


def main() -> int:
    """Update lockfile and sync all dependencies.

    Returns:
        0 on success, 1 on failure.
    """
    print("\n  Kourai Upgrade")
    print("=" * 60)
    logger.info("Starting dependency upgrade...")

    repo_root = Path(__file__).parent.parent
    lock_file = repo_root / "uv.lock"

    # Check for uv
    if not shutil.which("uv"):
        print("  x uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh")
        logger.error("uv not found")
        return 1

    # Backup uv.lock
    if lock_file.exists():
        timestamp = str(int(datetime.now().timestamp()))
        backup_file = repo_root / f"uv.lock.backup.{timestamp}"
        shutil.copy(lock_file, backup_file)
        print(f"  + Backed up to {backup_file.name}")
        logger.info(f"Backed up to {backup_file.name}")

        # Keep only the last 3 backups
        backups = sorted(repo_root.glob("uv.lock.backup.*"))
        for old_backup in backups[:-3]:
            old_backup.unlink()

    steps = [
        (["uv", "lock", "--upgrade", "-q"], "Updating lockfile"),
        (["uv", "sync", "--frozen", "--all-packages", "-q"], "Syncing dependencies"),
    ]

    for cmd, description in steps:
        if not run_step(cmd, description):
            print("\n" + "=" * 60)
            print("x Upgrade failed")
            print("=" * 60 + "\n")
            logger.error("Upgrade failed")
            return 1

    print("\n" + "=" * 60)
    print("+ Upgrade completed successfully")
    print("=" * 60)
    print()
    print("  Next: Review (git diff), Test, and Commit.")
    if sys.platform == "win32":
        print("  Restore: copy uv.lock.backup.* uv.lock (use latest backup)")
    else:
        print("  Restore: cp $(ls -t uv.lock.backup.* | head -n1) uv.lock && uv sync")
    print()
    logger.info("Upgrade completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
