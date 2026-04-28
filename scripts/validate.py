"""Quick validation: lint + unit tests for fast developer feedback.

Usage:
    python scripts/validate.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from kourai_common.dev_log import LOG

LINT_SCRIPT = Path(__file__).with_name("lint.py")


def run_validate_step(cmd: list[str], description: str) -> tuple[bool, str]:
    """Run a validation step and return (passed, output)."""
    print(f"  > {description}...")
    LOG.event("INFO", f"Running: {description}")
    result = subprocess.run(  # noqa: S603
        cmd, capture_output=True, text=True, encoding="utf-8", check=False
    )
    output = (result.stdout + result.stderr).strip()
    passed = result.returncode == 0
    if output:
        LOG.raw(output)
    return passed, output


def parse_pytest_summary(output: str) -> str:
    """Extract the short result line from pytest output.

    Args:
        output: Combined pytest stdout/stderr.

    Returns:
        Summary line like '2155 passed, 2 skipped in 48.98s', or empty string.
    """
    match = re.search(r"(\d+ passed.*?)\s*={3,}", output)
    if match:
        return match.group(1).strip()
    for line in reversed(output.splitlines()):
        if "passed" in line or "failed" in line or "error" in line:
            return line.strip()
    return ""


def _run_validate() -> int:
    print("\n  Kourai Validate")
    print("=" * 60)
    LOG.event("INFO", "Starting validation...")

    results: list[tuple[str, bool, str]] = []

    # `--check-only` skips the auto-format pass so this matches CI's strict
    # check exactly. `make fix` is the explicit auto-format path.
    passed, output = run_validate_step(
        [sys.executable, str(LINT_SCRIPT), "--check-only"],
        "Lint",
    )
    if passed:
        print("  + Lint")
    else:
        print("  x Lint failed")
        if output:
            print()
            for line in output.splitlines():
                print(f"    {line}")
            print()
    LOG.event("INFO", f"Lint: {'passed' if passed else 'FAILED'}")
    results.append(("Lint", passed, output))

    passed, output = run_validate_step(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/unit/",
            "-n",
            "auto",
            "--tb=short",
            "-q",
            "--no-header",
        ],
        "Unit tests",
    )
    summary = parse_pytest_summary(output)
    if passed:
        print(f"  + Unit tests -- {summary}")
    else:
        print(f"  x Unit tests -- {summary}")
        in_failure = False
        for line in output.splitlines():
            if line.startswith(("FAILED", "ERROR")):
                in_failure = True
            if in_failure:
                print(f"    {line}")
    LOG.event("INFO", f"Unit tests: {'passed' if passed else 'FAILED'} -- {summary}")
    results.append(("Unit tests", passed, output))

    all_passed = all(p for _, p, _ in results)
    passed_count = sum(1 for _, p, _ in results if p)
    total = len(results)

    print("\n" + "=" * 60)
    if all_passed:
        print(f"+ All checks passed ({passed_count}/{total})")
    else:
        print(f"x {total - passed_count}/{total} checks failed")
        print("  Full details: logs/dev-latest.log")
    print("=" * 60 + "\n")

    LOG.event("INFO", f"Validation complete -- {passed_count}/{total} passed")
    return 0 if all_passed else 1


def main() -> int:
    LOG.open("validate")
    LOG.session_header("validate", sys.argv[1:])
    rc = 1
    try:
        rc = _run_validate()
    finally:
        LOG.session_footer(rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
