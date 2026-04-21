"""Shared subprocess utilities for Kourai Khryseai agents.

Centralizes run_command and file extraction so agents don't duplicate them.

run_command delegates to a pluggable runner (see sandbox.py) chosen by the
KOURAI_SANDBOX env var; agent code is unaware of host vs container mode.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from kourai_common.sandbox import StatusCallback, get_runner

log = logging.getLogger(__name__)

_CONTEXT_LINES = 10

# Re-export so existing `from kourai_common.subprocess import StatusCallback` keeps working.
__all__ = [
    "StatusCallback",
    "extract_files_from_output",
    "extract_files_from_ruff_json",
    "get_diagnostic_line_ranges",
    "parse_ruff_json",
    "read_file_with_context",
    "run_command",
]


async def run_command(
    cmd: list[str],
    cwd: str | None = None,
    status_callback: StatusCallback | None = None,
) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr).

    Args:
        cmd: Command and arguments to run.
        cwd: Working directory (defaults to process cwd).
        status_callback: Optional async callback called with each stdout line
            as it arrives. Also receives the invoked command on start and the
            exit code on failure. Skips blank lines to reduce noise.
    """
    return await get_runner().run(cmd, cwd=cwd, status_callback=status_callback)


def parse_ruff_json(output: str) -> list[dict]:
    """Parse ruff --output-format json diagnostics.

    Returns list of dicts with keys: filename, row, col, code, message, fix.
    Falls back to empty list if output is not valid JSON.
    """
    try:
        diagnostics = json.loads(output)
        if not isinstance(diagnostics, list):
            return []
        return [
            {
                "filename": d.get("filename", ""),
                "row": d.get("location", {}).get("row", 0),
                "col": d.get("location", {}).get("column", 0),
                "code": d.get("code", ""),
                "message": d.get("message", ""),
                "fix": d.get("fix"),
            }
            for d in diagnostics
        ]
    except (json.JSONDecodeError, TypeError):
        return []


def extract_files_from_ruff_json(output: str) -> set[str]:
    """Extract unique file paths from ruff JSON output."""
    diagnostics = parse_ruff_json(output)
    return {d["filename"] for d in diagnostics if d["filename"]}


def get_diagnostic_line_ranges(output: str) -> dict[str, set[int]]:
    """Extract per-file line numbers from ruff JSON output.

    Returns {filename: {line1, line2, ...}} for use in context windowing.
    """
    diagnostics = parse_ruff_json(output)
    ranges: dict[str, set[int]] = {}
    for d in diagnostics:
        if d["filename"] and d["row"]:
            ranges.setdefault(d["filename"], set()).add(d["row"])
    return ranges


def read_file_with_context(
    file_path: str,
    diagnostic_lines: set[int] | None = None,
    context_lines: int = _CONTEXT_LINES,
) -> str:
    """Read a file, optionally windowing to only relevant lines.

    If diagnostic_lines is provided, returns only the lines around each
    diagnostic (with context_lines padding above/below). Otherwise returns
    the full file. For files under 200 lines, always returns the full file
    (windowing overhead isn't worth it).

    Each returned line is prefixed with its 1-based line number for the LLM.
    """
    path = Path(file_path)
    if not path.exists():
        return ""

    all_lines = path.read_text(encoding="utf-8").splitlines()

    if not diagnostic_lines or len(all_lines) <= 200:
        return "\n".join(f"{i + 1}: {line}" for i, line in enumerate(all_lines))

    included: set[int] = set()
    for diag_line in diagnostic_lines:
        start = max(0, diag_line - 1 - context_lines)
        end = min(len(all_lines), diag_line + context_lines)
        included.update(range(start, end))

    result_lines: list[str] = []
    prev_idx = -2
    for idx in sorted(included):
        if idx > prev_idx + 1:
            result_lines.append("...")
        result_lines.append(f"{idx + 1}: {all_lines[idx]}")
        prev_idx = idx

    return "\n".join(result_lines)


def extract_files_from_output(output: str) -> set[str]:
    """Extract .py file paths from ruff/ty/pytest output lines.

    Tries ruff JSON first, falls back to regex line parsing.
    Handles common prefixes like '--> ' and './' in tool output.
    """
    json_files = extract_files_from_ruff_json(output)
    if json_files:
        return json_files

    files = set()
    for line in output.splitlines():
        line = line.strip()
        parts = line.split(":")
        if len(parts) >= 2 and parts[0].strip().endswith(".py"):
            path = parts[0].strip()
            if path.startswith("E "):
                path = path[2:].strip()
            if path.startswith("--> "):
                path = path[4:].strip()
            if path.startswith(("./", ".\\")):
                path = path[2:]
            files.add(path)
        elif " " in line:
            first_word = line.split(" ")[0].strip()
            if first_word.endswith(".py"):
                path = first_word
                if path.startswith(("./", ".\\")):
                    path = path[2:]
                files.add(path)
    return files
