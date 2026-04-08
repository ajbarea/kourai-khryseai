"""Test suite runner with coverage reporting.

Runs unit, integration, and performance tests with coverage accumulation.
Supports running individual suites via --unit, --integration, --performance flags.

Usage:
    python scripts/test.py              # Run all suites (with lint first)
    python scripts/test.py --unit       # Unit tests only
    python scripts/test.py --integration  # Integration tests only (auto-starts containers)
    python scripts/test.py --performance  # Performance tests only
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

try:
    from scripts.logging_utils import setup_logger
except ModuleNotFoundError:
    from logging_utils import setup_logger

logger = setup_logger(__name__, "test.log")


def run_suite(cmd: list[str], description: str) -> tuple[bool, str]:
    """Execute a test suite and return (passed, output).

    Args:
        cmd: Command and arguments as a list.
        description: Human-readable description for logging.

    Returns:
        (True if successful, False otherwise), combined stdout+stderr.
    """
    logger.info(f"Running: {description}")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8")  # noqa: S603
        output = (result.stdout + result.stderr).strip()
        logger.info(f"+ {description} passed")
        if output:
            logger.debug(output)
        return True, output
    except subprocess.CalledProcessError as e:
        output = (e.stdout + e.stderr).strip()
        logger.error(f"x {description} failed (exit code: {e.returncode})")
        if output:
            logger.error(output)
        return False, output
    except FileNotFoundError:
        logger.error(f"x {description} - command not found")
        return False, ""


def parse_pytest_summary(output: str) -> str:
    """Extract the short result line from pytest output.

    Args:
        output: Combined pytest stdout/stderr.

    Returns:
        Summary string like '2155 passed, 2 skipped in 48.98s'.
    """
    matches = re.findall(r"=+ (.+?) =+\s*$", output, re.MULTILINE)
    if matches:
        return matches[-1].strip()
    for line in reversed(output.splitlines()):
        if any(kw in line for kw in ("passed", "failed", "error")):
            return line.strip()
    return ""


def main() -> int:
    """Run test suite with coverage.

    Returns:
        0 if all tests pass, 1 if any fail.
    """
    args = sys.argv[1:]
    run_unit = "--unit" in args
    run_integration = "--integration" in args
    run_performance = "--performance" in args
    run_all = not (run_unit or run_integration or run_performance)

    print("\n  Test Suite")
    print("=" * 60)
    logger.info("Starting test suite...")

    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    coverage_xml = log_dir / "coverage.xml"

    suites: list[tuple[list[str], str]] = []

    if run_all or run_unit:
        suites.append(
            (
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/unit/",
                    "-n",
                    "auto",
                    "-v",
                    "--tb=short",
                    "--cov=.",
                    f"--cov-report=xml:{coverage_xml}",
                    "--cov-report=term-missing",
                ],
                "Unit tests",
            )
        )

    if run_all or run_performance:
        cov_args = ["--cov-append"] if (run_all or run_unit) else []
        suites.append(
            (
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/performance/",
                    "-v",
                    "--tb=short",
                    "--cov=.",
                    *cov_args,
                    f"--cov-report=xml:{coverage_xml}",
                    "--cov-report=term-missing",
                ],
                "Performance tests",
            )
        )

    if run_all or run_integration:
        cov_args = ["--cov-append"] if (run_all or run_unit or run_performance) else []
        suites.append(
            (
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/integration/",
                    "-v",
                    "--tb=short",
                    "--cov=.",
                    *cov_args,
                    f"--cov-report=xml:{coverage_xml}",
                    "--cov-report=term-missing",
                ],
                "Integration tests",
            )
        )

    # If running all, run lint first
    if run_all:
        print(f"\n[0/{len(suites)}] Lint (pre-flight)...")
        lint_result = subprocess.run(  # noqa: S603
            [sys.executable, str(Path(__file__).with_name("lint.py"))],
            check=False,
        )
        if lint_result.returncode != 0:
            print("\nx Lint failed — fix issues before running tests\n")
            return 1

    results: list[tuple[str, bool, str]] = []
    try:
        for i, (cmd, description) in enumerate(suites, 1):
            print(f"\n[{i}/{len(suites)}] {description}...")
            passed, output = run_suite(cmd, description)
            results.append((description, passed, output))
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Test run cancelled by user", file=sys.stderr)
        return 130

    # Summary
    passed_count = sum(1 for _, p, _ in results if p)
    total = len(results)

    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    for description, passed, output in results:
        status = "+" if passed else "x"
        summary = parse_pytest_summary(output)
        suffix = f" -- {summary}" if summary else ""
        print(f"  {status} {description}{suffix}")

    print(f"\n  Coverage report: {coverage_xml}")
    print("=" * 60)

    if passed_count == total:
        print(f"+ All tests passed ({passed_count}/{total})\n")
        logger.info(f"All tests passed ({passed_count}/{total})")
        return 0
    else:
        failed = total - passed_count
        print(f"x {failed}/{total} suites failed")
        print("  See logs/test.log for details\n")
        logger.error(f"{failed}/{total} suites failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
