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

from kourai_common.dev_log import LOG


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


def _run_deps(args: argparse.Namespace) -> int:
    print("\n  Dependency Tree")
    print("=" * 60)
    LOG.event("INFO", "Starting dependency tree analysis...")

    try:
        LOG.event("INFO", "Running: uv tree")
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
        LOG.event("ERROR", error_msg)
        if e.stdout:
            LOG.raw(e.stdout)
        if e.stderr:
            LOG.raw(e.stderr)
        print("=" * 60)
        return 1
    except FileNotFoundError:
        error_msg = "uv not found. Install uv from https://docs.astral.sh/uv/"
        print(f"x {error_msg}")
        LOG.event("ERROR", error_msg)
        print("=" * 60)
        return 1

    output = result.stdout
    stderr = result.stderr
    total_packages = extract_package_count(stderr) or extract_package_count(output)
    dev_packages = count_dev_packages(output)
    main_packages = max(total_packages - dev_packages, 0)

    if stderr:
        LOG.raw(stderr)

    print(f"Total packages: {total_packages} (resolved)")
    print(f"  Main packages: {main_packages}")
    print(f"  Dev packages:  {dev_packages}")
    print("=" * 60)
    print("Dependency tree:")
    print("=" * 60)

    tree_lines = [line for line in output.splitlines() if line.strip()]
    LOG.raw("\n".join(tree_lines))

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
    print("  Full details: logs/dev-latest.log\n")
    LOG.event("INFO", "Dependency tree analysis complete")
    return 0


def main() -> int:
    args = _parse_args(sys.argv[1:])
    LOG.open("deps")
    LOG.session_header("deps", sys.argv[1:])
    rc = 1
    try:
        rc = _run_deps(args)
    finally:
        LOG.session_footer(rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
