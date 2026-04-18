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

from kourai_common.dev_log import LOG


def run_upgrade_step(cmd: list[str], description: str) -> bool:
    """Execute an upgrade step, printing progress and logging to file."""
    print(f"  > {description}...")
    LOG.event("INFO", f"Running: {description}")
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        print(f"  + {description}")
        LOG.event("INFO", f"{description} completed")
        if result.stdout:
            LOG.raw(result.stdout.strip())
        return True
    except subprocess.CalledProcessError as e:
        print(f"  x {description} failed (exit code {e.returncode})")
        LOG.event("ERROR", f"Failed: {description} (exit code {e.returncode})")
        if e.stdout:
            LOG.raw(e.stdout.strip())
        if e.stderr:
            LOG.raw(e.stderr.strip())
        return False


def _run_upgrade() -> int:
    print("\n  Kourai Upgrade")
    print("=" * 60)
    LOG.event("INFO", "Starting dependency upgrade...")

    repo_root = Path(__file__).parent.parent
    lock_file = repo_root / "uv.lock"

    if not shutil.which("uv"):
        print("  x uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh")
        LOG.event("ERROR", "uv not found")
        return 1

    if lock_file.exists():
        timestamp = str(int(datetime.now().timestamp()))
        backup_file = repo_root / f"uv.lock.backup.{timestamp}"
        shutil.copy(lock_file, backup_file)
        print(f"  + Backed up to {backup_file.name}")
        LOG.event("INFO", f"Backed up to {backup_file.name}")

        backups = sorted(repo_root.glob("uv.lock.backup.*"))
        for old_backup in backups[:-3]:
            old_backup.unlink()

    steps = [
        (["uv", "lock", "--upgrade", "-q"], "Updating lockfile"),
        (["uv", "sync", "--frozen", "--all-packages", "-q"], "Syncing dependencies"),
    ]

    for cmd, description in steps:
        if not run_upgrade_step(cmd, description):
            print("\n" + "=" * 60)
            print("x Upgrade failed")
            print("=" * 60 + "\n")
            LOG.event("ERROR", "Upgrade failed")
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
    LOG.event("INFO", "Upgrade completed successfully")
    return 0


def main() -> int:
    LOG.open("upgrade")
    LOG.session_header("upgrade", sys.argv[1:])
    rc = 1
    try:
        rc = _run_upgrade()
    finally:
        LOG.session_footer(rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
