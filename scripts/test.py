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

from kourai_common.dev_log import LOG


def run_suite(cmd: list[str], description: str) -> tuple[bool, str]:
    """Execute a test suite and return (passed, output)."""
    LOG.event("INFO", f"Running: {description}")
    try:
        result = subprocess.run(  # noqa: S603
            cmd, check=True, capture_output=True, text=True, encoding="utf-8"
        )
        output = (result.stdout + result.stderr).strip()
        LOG.event("INFO", f"{description} passed")
        if output:
            LOG.raw(output)
        return True, output
    except subprocess.CalledProcessError as e:
        output = (e.stdout + e.stderr).strip()
        LOG.event("ERROR", f"{description} failed (exit code: {e.returncode})")
        if output:
            LOG.raw(output)
        return False, output
    except FileNotFoundError:
        LOG.event("ERROR", f"{description} - command not found")
        return False, ""


def parse_pytest_summary(output: str) -> str:
    """Extract the short result line from pytest output."""
    matches = re.findall(r"=+ (.+?) =+\s*$", output, re.MULTILINE)
    if matches:
        return matches[-1].strip()
    for line in reversed(output.splitlines()):
        if any(kw in line for kw in ("passed", "failed", "error")):
            return line.strip()
    return ""


def _build_suites(
    *, run_all: bool, run_unit: bool, run_integration: bool, run_performance: bool
) -> list[tuple[list[str], str]]:
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
                    # Skip @pytest.mark.slow on the push/PR fast lane —
                    # those tests (Kokoro neural inference, etc.) are
                    # heavyweight and flake on shared CI runners with
                    # SystemExit:1 from model load timeouts. The nightly
                    # workflow runs them by inverting the marker.
                    "-m",
                    "not slow",
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
                    "-m",
                    "integration",
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

    return suites


def _run_tests() -> int:
    args = sys.argv[1:]
    run_unit = "--unit" in args
    run_integration = "--integration" in args
    run_performance = "--performance" in args
    run_all = not (run_unit or run_integration or run_performance)

    suites = _build_suites(
        run_all=run_all,
        run_unit=run_unit,
        run_integration=run_integration,
        run_performance=run_performance,
    )
    coverage_xml = Path("logs") / "coverage.xml"

    print("\n  Test Suite")
    print("=" * 60)
    LOG.event("INFO", "Starting test suite...")

    if run_all:
        print(f"\n[0/{len(suites)}] Lint (pre-flight)...")
        LOG.event("INFO", "Running: Lint (pre-flight)")
        lint_result = subprocess.run(  # noqa: S603
            [sys.executable, str(Path(__file__).with_name("lint.py"))],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if lint_result.returncode != 0:
            print("\nx Lint failed — fix issues before running tests\n")
            LOG.event("ERROR", "Lint failed")
            if lint_result.stdout or lint_result.stderr:
                LOG.raw(lint_result.stdout + lint_result.stderr)
            return 1
        LOG.event("INFO", "Lint passed")

    results: list[tuple[str, bool, str]] = []
    try:
        for i, (cmd, description) in enumerate(suites, 1):
            print(f"\n[{i}/{len(suites)}] {description}...")
            passed, output = run_suite(cmd, description)
            results.append((description, passed, output))
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Test run cancelled by user", file=sys.stderr)
        return 130

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
        LOG.event("INFO", f"All tests passed ({passed_count}/{total})")
        return 0
    failed = total - passed_count
    print(f"x {failed}/{total} suites failed")
    print("  See logs/dev-runner-latest.log for details\n")
    LOG.event("ERROR", f"{failed}/{total} suites failed")
    return 1


def main() -> int:
    LOG.open("test")
    LOG.session_header("test", sys.argv[1:])
    rc = 1
    try:
        rc = _run_tests()
    finally:
        LOG.session_footer(rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
