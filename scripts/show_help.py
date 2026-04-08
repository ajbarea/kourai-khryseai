"""Display help message for Kourai developer commands.

Delegates to dev_cli.print_help() so there's a single source of truth.

Usage:
    python scripts/show_help.py
"""

from __future__ import annotations

import sys
from pathlib import Path


def _load_print_help():
    """Import print_help from kourai_common, with a local-path fallback."""
    try:
        from kourai_common.dev_cli import print_help
    except ModuleNotFoundError:
        repo_root = Path(__file__).resolve().parents[1]
        shared_src = repo_root / "shared" / "src"
        if str(shared_src) not in sys.path:
            sys.path.insert(0, str(shared_src))
        from kourai_common.dev_cli import print_help
    return print_help


def main() -> int:
    """Print help from dev_cli."""
    print_help = _load_print_help()
    print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
