#!/usr/bin/env python
"""Display Makefile help message."""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
MAKEFILE = SCRIPT_DIR.parent / "Makefile"


def main() -> int:
    """Print help from Makefile."""
    if not MAKEFILE.exists():
        logger.error(f"Makefile not found at {MAKEFILE}")
        return 1

    content = MAKEFILE.read_text(encoding="utf-8")
    lines = content.split("\n")

    logger.info("")
    logger.info("=" * 66)
    logger.info("  Kourai Khryseai - Make Commands")
    logger.info("=" * 66)
    logger.info("")

    for line in lines:
        match = re.match(r"^([a-zA-Z_-]+):\s+##\s+(.*)", line)
        if match:
            target, help_text = match.groups()
            logger.info(f"  {target:<18} {help_text}")

    logger.info("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
