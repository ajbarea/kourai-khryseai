"""Build artifact and cache cleanup utility.

Removes build artifacts, test caches, and temporary files to maintain a clean
development environment. Supports selective cleanup via --cache-only and --tests-only.

Usage:
    python scripts/clean_build.py
    python scripts/clean_build.py --cache-only
    python scripts/clean_build.py --tests-only
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

try:
    from scripts.logging_utils import setup_logger
except ModuleNotFoundError:
    from logging_utils import setup_logger

logger = setup_logger(__name__, "clean_build.log")


def clean_build(cache_only: bool = False, tests_only: bool = False) -> None:
    """Remove build artifacts and cache directories.

    Args:
        cache_only: If True, only clean cache directories.
        tests_only: If True, only clean test artifacts.
    """
    if cache_only:
        print("\n  Kourai Cleanup (cache only)")
    elif tests_only:
        print("\n  Kourai Cleanup (test artifacts only)")
    else:
        print("\n  Kourai Cleanup")
    print("=" * 60)
    logger.info("Starting cleanup...")

    root = Path()
    skip_dirs = {".venv", ".venv-win", ".venv-wsl", "venv", "node_modules"}

    # Close logger handlers before cleaning logs directory
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    if tests_only:
        _clean_patterns(
            root, [".pytest_cache", "__pycache__", ".hypothesis", "MagicMock"], skip_dirs
        )
        _clean_files(root, [".coverage"])
        _clean_dirs(root, ["logs", "htmlcov"])
        _print_done()
        return

    if cache_only:
        _clean_dirs(root, [".ty_cache", ".mypy_cache", ".ruff_cache"])
        _print_done()
        return

    # Full clean
    _clean_dirs(
        root,
        [
            "logs",
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
    _clean_patterns(root, ["__pycache__", ".egg-info", "MagicMock"], skip_dirs)
    _clean_files(root, [".coverage", "docker-debug.log"])
    _clean_globs(root, [".coverage.*", "uv.lock.backup.*"])

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
    """Print completion message."""
    print("\n" + "=" * 60)
    print("+ Cleanup completed successfully")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean build artifacts.")
    parser.add_argument("--cache-only", action="store_true", help="Only clean cache directories")
    parser.add_argument("--tests-only", action="store_true", help="Only clean test artifacts")
    args = parser.parse_args()
    try:
        clean_build(cache_only=args.cache_only, tests_only=args.tests_only)
    except Exception as e:
        print(f"x Cleanup failed: {e}")
        sys.exit(1)
