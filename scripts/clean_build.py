#!/usr/bin/env python
"""Clean build artifacts, cache, and temp files (cross-platform).

Usage:
    python scripts/clean_build.py
    python scripts/clean_build.py --cache-only
    python scripts/clean_build.py --tests-only
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


def clean_pycache() -> None:
    """Remove __pycache__ and .egg-info directories."""
    for root, dirs, _ in os.walk("."):
        # Prevent diving into virtual environments
        dirs[:] = [d for d in dirs if not d.startswith(".venv") and d != "venv"]

        for dirname in dirs:
            if dirname in {"__pycache__", ".egg-info"}:
                path = Path(root) / dirname
                logger.info(f"Removing {path}")
                shutil.rmtree(path, ignore_errors=True)


def clean_pytest() -> None:
    """Remove pytest and coverage artifacts."""
    patterns = [".pytest_cache", "logs", ".coverage", "coverage.xml", "htmlcov"]
    for pattern in patterns:
        p = Path(pattern)
        if p.exists():
            if p.is_dir():
                logger.info(f"Removing directory {pattern}")
                shutil.rmtree(p, ignore_errors=True)
            else:
                logger.info(f"Removing file {pattern}")
                p.unlink()


def clean_mypy() -> None:
    """Remove mypy cache."""
    p = Path(".mypy_cache")
    if p.exists():
        logger.info("Removing .mypy_cache")
        shutil.rmtree(p, ignore_errors=True)


def clean_ruff() -> None:
    """Remove ruff cache."""
    p = Path(".ruff_cache")
    if p.exists():
        logger.info("Removing .ruff_cache")
        shutil.rmtree(p, ignore_errors=True)


def clean_build() -> None:
    """Remove build artifacts."""
    patterns = [".playwright-mcp", "site", "dist", "build"]
    for pattern in patterns:
        p = Path(pattern)
        if p.exists():
            logger.info(f"Removing {pattern}")
            shutil.rmtree(p, ignore_errors=True)


def clean_hypothesis() -> None:
    """Remove hypothesis cache."""
    p = Path(".hypothesis")
    if p.exists():
        logger.info("Removing .hypothesis")
        shutil.rmtree(p, ignore_errors=True)


def clean_uv_backups() -> None:
    """Remove uv.lock backup files."""
    for backup_file in Path().glob("uv.lock.backup.*"):
        logger.info(f"Removing {backup_file}")
        backup_file.unlink()


def main() -> int:
    """Clean all artifacts."""
    args = sys.argv[1:]

    if "--cache-only" in args:
        logger.info("[CLEAN] Cache only...")
        clean_mypy()
        clean_ruff()
    elif "--tests-only" in args:
        logger.info("[CLEAN] Test artifacts only...")
        clean_pytest()
        clean_pycache()
    else:
        logger.info("[CLEAN] Build artifacts and caches...")
        clean_pycache()
        clean_pytest()
        clean_mypy()
        clean_ruff()
        clean_build()
        clean_hypothesis()
        clean_uv_backups()

    logger.info("Done. Workspace cleaned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
