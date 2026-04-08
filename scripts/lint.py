"""Code quality checks and formatting.

Runs ruff format, ruff check, and type checking with ty.
Provides clear output with progress counters and exits with appropriate status codes.

Usage:
    python scripts/lint.py
"""

from __future__ import annotations

import subprocess
import sys

try:
    from scripts.logging_utils import setup_logger
except ModuleNotFoundError:
    from logging_utils import setup_logger

logger = setup_logger(__name__, "lint.log")


def run_command(cmd: list[str], description: str) -> bool:
    """Execute a command and report results.

    Args:
        cmd: Command and arguments as a list.
        description: Human-readable description for logging.

    Returns:
        True if successful, False otherwise.
    """
    logger.info(f"Running: {description}")
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        logger.info(f"+ {description} passed")
        if result.stdout:
            logger.debug(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"x {description} failed (exit code: {e.returncode})")
        if e.stdout:
            logger.error(f"STDOUT:\n{e.stdout}")
        if e.stderr:
            logger.error(f"STDERR:\n{e.stderr}")
        return False
    except FileNotFoundError:
        logger.error(f"x {description} - command not found")
        return False


def main() -> int:
    """Run all linting checks.

    Returns:
        0 if all checks pass, 1 if any fail.
    """
    print("\n  Code Quality Checks")
    print("=" * 60)
    logger.info("Starting code quality checks...")

    checks: list[tuple[list[str], str]] = [
        (["ruff", "format", "."], "Ruff format"),
        (["ruff", "check", "--fix", "--unsafe-fixes", "--show-fixes", "."], "Ruff check"),
        (
            [
                "ty",
                "check",
                "agents",
                "hosts/cli",
                "hosts/gui",
                "mcp_servers",
                "shared/src",
                "tests",
            ],
            "Type checking (ty)",
        ),
    ]

    results: list[bool] = []
    for i, (cmd, description) in enumerate(checks, 1):
        print(f"\n[{i}/{len(checks)}] {description}...")
        results.append(run_command(cmd, description))

    # Summary
    passed = sum(results)
    total = len(results)

    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    for (_, description), result in zip(checks, results, strict=False):
        status = "+" if result else "x"
        print(f"  {status} {description}")

    print("=" * 60)
    if passed == total:
        print(f"+ All checks passed ({passed}/{total})\n")
        logger.info("All checks passed")
        return 0
    else:
        failed = total - passed
        print(f"x Some checks failed ({failed} failed, {passed} passed)")
        print("  Full details: logs/lint.log\n")
        logger.error(f"Some checks failed ({failed} failed, {passed} passed)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
