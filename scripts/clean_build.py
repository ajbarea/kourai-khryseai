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

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


def clean_pycache() -> None:
    """Remove __pycache__ and .egg-info directories."""
    for root, dirs, _ in os.walk("."):
        # Prevent diving into virtual environments
        dirs[:] = [d for d in dirs if not d.startswith(".venv") and d != "venv"]

        for dirname in dirs:
            if dirname in {"__pycache__", ".egg-info"}:
                path = os.path.join(root, dirname)
                logger.info(f"Removing {path}")
                shutil.rmtree(path, ignore_errors=True)


def clean_pytest() -> None:
    """Remove pytest and coverage artifacts."""
    patterns = [".pytest_cache", "logs", ".coverage", "coverage.xml", "htmlcov"]
    for pattern in patterns:
        if os.path.exists(pattern):
            if os.path.isdir(pattern):
                logger.info(f"Removing directory {pattern}")
                shutil.rmtree(pattern, ignore_errors=True)
            else:
                logger.info(f"Removing file {pattern}")
                os.remove(pattern)


def clean_mypy() -> None:
    """Remove mypy cache."""
    if os.path.exists(".mypy_cache"):
        logger.info("Removing .mypy_cache")
        shutil.rmtree(".mypy_cache", ignore_errors=True)


def clean_ruff() -> None:
    """Remove ruff cache."""
    if os.path.exists(".ruff_cache"):
        logger.info("Removing .ruff_cache")
        shutil.rmtree(".ruff_cache", ignore_errors=True)


def clean_build() -> None:
    """Remove build artifacts."""
    patterns = [".playwright-mcp", "site", "dist", "build"]
    for pattern in patterns:
        if os.path.exists(pattern):
            logger.info(f"Removing {pattern}")
            shutil.rmtree(pattern, ignore_errors=True)


def clean_hypothesis() -> None:
    """Remove hypothesis cache."""
    if os.path.exists(".hypothesis"):
        logger.info("Removing .hypothesis")
        shutil.rmtree(".hypothesis", ignore_errors=True)


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

    logger.info("Done. Workspace cleaned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
