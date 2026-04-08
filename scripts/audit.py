"""Security audit for project dependencies.

Attempts to audit dependencies using pip-audit, falling back to uv audit.
Skipped packages are reported clearly when supported by the backend tool.

Usage:
    python scripts/audit.py
"""

from __future__ import annotations

import re
import subprocess
import sys

try:
    from scripts.logging_utils import setup_logger
except ModuleNotFoundError:
    from logging_utils import setup_logger

logger = setup_logger(__name__, "audit.log")


def parse_skipped(output: str) -> list[str]:
    """Extract skipped package names from pip-audit table output."""
    skipped = []
    in_table = False
    for line in output.splitlines():
        if "Name" in line and "Skip Reason" in line:
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("-"):
            continue
        if not line.strip():
            in_table = False
            continue
        parts = line.split(None, 1)
        if len(parts) >= 2 and any(kw in parts[1] for kw in ("PyPI", "audited", "not found")):
            skipped.append(parts[0])
        else:
            in_table = False
    return skipped


def run_audit(cmd: list[str], label: str) -> tuple[bool | None, str]:
    """Run an audit command and return (passed, full_output).

    Returns:
        True: command ran and found no vulnerabilities.
        False: command ran and reported vulnerabilities/failure.
        None: command unavailable in this environment.
    """
    print(f"  > Running {label}...")
    logger.info(f"Running: {label}")
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError:
        logger.debug(f"{label} not found")
        return None, ""

    output = (result.stdout or "") + (result.stderr or "")
    logger.debug(output.strip())

    # Older uv versions may not support "audit"; treat as unavailable.
    lowered = output.lower()
    if (
        result.returncode != 0
        and "uv audit" in label
        and ("no such command" in lowered or "unrecognized" in lowered)
    ):
        logger.debug("uv audit unsupported by this uv version")
        return None, output

    return result.returncode == 0, output


def parse_vulnerability_count(output: str) -> int | None:
    """Extract vulnerability count from known audit output formats."""
    uv_match = re.search(r"Found\s+(\d+)\s+known vulnerabilities", output, re.IGNORECASE)
    if uv_match:
        return int(uv_match.group(1))

    pip_match = re.search(r"(\d+)\s+vulnerabilit(?:y|ies)", output, re.IGNORECASE)
    if pip_match:
        return int(pip_match.group(1))
    return None


def extract_advisory_preview(output: str, limit: int = 3) -> list[str]:
    """Get a short preview of advisory IDs from audit output."""
    lines = []
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- GHSA-", "- CVE-")):
            lines.append(stripped.lstrip("- ").strip())
        if len(lines) >= limit:
            break
    return lines


def main() -> int:
    """Run a security audit on project dependencies."""
    print("\n  Security Audit")
    print("=" * 60)
    logger.info("Starting security audit...")

    tools = [
        (["pip-audit"], "pip-audit"),
        (["uv", "audit"], "uv audit"),
    ]

    for cmd, label in tools:
        passed, output = run_audit(cmd, label)
        if passed is None:
            continue

        skipped = parse_skipped(output)
        vuln_count = parse_vulnerability_count(output)
        advisory_preview = extract_advisory_preview(output)

        print(f"  > Backend: {label}")
        if passed:
            print("  + No vulnerabilities found")
            logger.info("Audit passed")
        else:
            print("  x Vulnerabilities found")
            logger.error("Audit failed")
            if vuln_count is not None:
                print(f"  ! Vulnerability count: {vuln_count}")
            if advisory_preview:
                print("  ! Sample advisories:")
                for advisory in advisory_preview:
                    print(f"    - {advisory}")

        if skipped:
            print(f"  ! Skipped packages ({len(skipped)}): {', '.join(skipped)}")
            logger.info(f"Skipped packages: {', '.join(skipped)}")

        print("\n" + "=" * 60)
        print("+ Audit passed" if passed else "x Audit failed")
        print("  Full details: logs/audit.log")
        print("=" * 60 + "\n")
        return 0 if passed else 1

    print("  ! No audit backend available (pip-audit or uv audit)")
    print("    Install pip-audit with: uv add --dev pip-audit")
    logger.warning("No audit backend available")
    print("\n" + "=" * 60)
    print("+ Audit skipped")
    print("  Full details: logs/audit.log")
    print("=" * 60 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
