"""Build artifact and cache cleanup utility.

Removes build artifacts, test caches, and temporary files to maintain a clean
development environment. Supports selective cleanup via --cache-only and --tests-only.

The ``logs/`` directory is never wiped wholesale — only ``dev-*-*.log``
archives older than ``LOG_ARCHIVE_MAX_AGE_DAYS`` are pruned. ``dev-latest.log``
(the active handle for the current run) is always preserved.

Usage:
    python scripts/clean_build.py
    python scripts/clean_build.py --cache-only
    python scripts/clean_build.py --tests-only
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

from kourai_common.dev_log import LOG

LOG_ARCHIVE_GLOB = "dev-*-*.log"
LOG_ARCHIVE_MAX_AGE_DAYS = 30


def clean_build(cache_only: bool = False, tests_only: bool = False) -> None:
    """Remove build artifacts and cache directories."""
    if cache_only:
        print("\n  Kourai Cleanup (cache only)")
    elif tests_only:
        print("\n  Kourai Cleanup (test artifacts only)")
    else:
        print("\n  Kourai Cleanup")
    print("=" * 60)
    LOG.event("INFO", "Starting cleanup...")

    root = Path()
    skip_dirs = {".venv", ".venv-win", ".venv-wsl", "venv", "node_modules"}

    if tests_only:
        _clean_patterns(
            root, [".pytest_cache", "__pycache__", ".hypothesis", "MagicMock"], skip_dirs
        )
        _clean_files(root, [".coverage"])
        _clean_dirs(root, ["htmlcov"])
        _prune_log_archives(root, ["logs"])
        _print_done()
        return

    if cache_only:
        _clean_dirs(root, [".ty_cache", ".mypy_cache", ".ruff_cache"])
        _print_done()
        return

    _clean_dirs(
        root,
        [
            ".pytest_cache",
            ".ty_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".hypothesis",
            ".playwright-mcp",
            "site",
            "dist",
            "build",
            "htmlcov",
        ],
    )
    _clean_patterns(root, ["__pycache__", "*.egg-info", "MagicMock"], skip_dirs)
    _clean_files(root, [".coverage", "docker-debug.log"])
    _clean_globs(root, [".coverage.*", "uv.lock.backup.*"])
    _prune_log_archives(root, ["logs"])

    _print_done()


def _clean_dirs(root: Path, dirs: list[str]) -> None:
    """Remove specific directories if they exist."""
    removed = []
    for dirname in dirs:
        d = root / dirname
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
            removed.append(dirname)
    if removed:
        print("\n  Removing directories...")
        for d in removed:
            print(f"  + Removed {d}")


def _clean_patterns(root: Path, patterns: list[str], skip_dirs: set[str]) -> None:
    """Remove directories matching patterns recursively."""
    pattern_results: dict[str, int] = {}
    for pattern in patterns:
        count = 0
        for p in root.rglob(pattern):
            if any(part in skip_dirs for part in p.parts):
                continue
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                count += 1
            except PermissionError:
                print(f"  ! Skipped (locked): {p}")
        if count > 0:
            pattern_results[pattern] = count
    if pattern_results:
        print("\n  Cleaning artifact patterns...")
        for pattern, count in pattern_results.items():
            print(f"  + Cleaned {count} {pattern} artifacts")


def _clean_files(root: Path, files: list[str]) -> None:
    """Remove specific files if they exist."""
    removed = []
    for filename in files:
        f = root / filename
        if f.exists():
            f.unlink()
            removed.append(filename)
    if removed:
        print("\n  Removing files...")
        for f in removed:
            print(f"  + Removed {f}")


def _prune_log_archives(root: Path, log_dirs: list[str]) -> None:
    """Delete dev-runner archives older than the retention window.

    Skips any *-latest.log file (the active handle for the current run), so
    naming conventions like dev-latest.log or dev-runner-latest.log are both safe.
    """
    cutoff = time.time() - LOG_ARCHIVE_MAX_AGE_DAYS * 86400
    pruned = 0
    for dirname in log_dirs:
        d = root / dirname
        if not d.is_dir():
            continue
        for log_file in d.glob(LOG_ARCHIVE_GLOB):
            if log_file.name.endswith("-latest.log"):
                continue
            try:
                if log_file.stat().st_mtime < cutoff:
                    log_file.unlink()
                    pruned += 1
            except (PermissionError, FileNotFoundError):
                pass
    if pruned:
        print("\n  Pruning stale log archives...")
        print(f"  + Pruned {pruned} archive(s) older than {LOG_ARCHIVE_MAX_AGE_DAYS} days")


def _clean_globs(root: Path, patterns: list[str]) -> None:
    """Remove files matching glob patterns."""
    removed = []
    for pattern in patterns:
        for f in root.glob(pattern):
            f.unlink()
            removed.append(str(f))
    if removed:
        print("\n  Removing glob matches...")
        for f in removed:
            print(f"  + Removed {f}")


def _print_done() -> None:
    print("\n" + "=" * 60)
    print("+ Cleanup completed successfully")
    print("=" * 60 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean build artifacts.")
    parser.add_argument("--cache-only", action="store_true", help="Only clean cache directories")
    parser.add_argument("--tests-only", action="store_true", help="Only clean test artifacts")
    args = parser.parse_args()

    LOG.open("clean")
    LOG.session_header("clean", sys.argv[1:])
    rc = 0
    try:
        clean_build(cache_only=args.cache_only, tests_only=args.tests_only)
    except (OSError, RuntimeError) as e:
        print(f"x Cleanup failed: {e}")
        LOG.event("ERROR", f"Cleanup failed: {e}")
        rc = 1
    finally:
        LOG.session_footer(rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
