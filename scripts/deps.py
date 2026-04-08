"""Display and log dependency tree information.

Shows a formatted summary of the project's dependencies with counts and groups.

Usage:
    python scripts/deps.py
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

try:
    from scripts.logging_utils import setup_logger
except ModuleNotFoundError:
    from logging_utils import setup_logger

logger = setup_logger(__name__, "deps.log")


def extract_package_count(output: str) -> int:
    """Extract total resolved package count from uv tree output."""
    match = re.search(r"Resolved (\d+) packages?", output)
    return int(match.group(1)) if match else 0


def count_dev_packages(output: str) -> int:
    """Count dev-group packages from uv tree output."""
    return output.count("(group: dev)")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show project dependency tree")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Print the full dependency tree to terminal (default shows a concise preview).",
    )
    parser.add_argument(
        "--preview-lines",
        type=int,
        default=80,
        help="When not using --full, number of dependency-tree lines to preview (default: 80).",
    )
    return parser.parse_args(argv)


def main() -> int:
    """Display dependency tree with summary."""
    args = _parse_args(sys.argv[1:])
    print("\n  Dependency Tree")
    print("=" * 60)
    logger.info("Starting dependency tree analysis...")

    try:
        logger.info("Running: uv tree")
        result = subprocess.run(
            ["uv", "tree"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to run uv tree: {e}"
        print(f"x {error_msg}")
        logger.error(error_msg)
        if e.stdout:
            logger.debug(f"stdout: {e.stdout}")
        if e.stderr:
            logger.debug(f"stderr: {e.stderr}")
        print("=" * 60)
        return 1
    except FileNotFoundError:
        error_msg = "uv not found. Install uv from https://docs.astral.sh/uv/"
        print(f"x {error_msg}")
        logger.error(error_msg)
        print("=" * 60)
        return 1

    output = result.stdout
    stderr = result.stderr
    total_packages = extract_package_count(stderr) or extract_package_count(output)
    dev_packages = count_dev_packages(output)
    main_packages = max(total_packages - dev_packages, 0)

    if stderr:
        logger.debug(f"stderr: {stderr}")

    print(f"Total packages: {total_packages} (resolved)")
    print(f"  Main packages: {main_packages}")
    print(f"  Dev packages:  {dev_packages}")
    print("=" * 60)
    print("Dependency tree:")
    print("=" * 60)

    tree_lines = [line for line in output.splitlines() if line.strip()]
    for line in tree_lines:
        logger.debug(line)

    if args.full:
        for line in tree_lines:
            print(line)
    else:
        preview = tree_lines[: max(args.preview_lines, 1)]
        for line in preview:
            print(line)
        remaining = len(tree_lines) - len(preview)
        if remaining > 0:
            print(f"... ({remaining} more lines)")
            print(
                "Tip: run `uv run --no-active --package kourai-common kourai-dev deps -- --full`."
            )

    print("=" * 60)
    print("+ Dependency tree generated")
    print("  Full details: logs/deps.log\n")
    logger.info("Dependency tree analysis complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
