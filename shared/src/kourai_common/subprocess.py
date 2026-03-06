"""Shared subprocess utilities for Kourai Khryseai agents.

Centralizes run_command, parse_and_apply_fixes, and file extraction
so agents don't duplicate them.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

# Context lines above/below each diagnostic when windowing file content
_CONTEXT_LINES = 10


async def run_command(cmd: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    log.debug("Running: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await proc.communicate()
    return (
        proc.returncode or 0,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )


# ── Ruff JSON output parsing ────────────────────────────────────────


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


# ── Smart context windowing ──────────────────────────────────────────


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

    # Small files: just return everything
    if not diagnostic_lines or len(all_lines) <= 200:
        return "\n".join(f"{i + 1}: {line}" for i, line in enumerate(all_lines))

    # Build set of line indices to include (0-based)
    included: set[int] = set()
    for diag_line in diagnostic_lines:
        start = max(0, diag_line - 1 - context_lines)
        end = min(len(all_lines), diag_line + context_lines)
        included.update(range(start, end))

    # Format with line numbers, adding "..." separators for gaps
    result_lines: list[str] = []
    prev_idx = -2
    for idx in sorted(included):
        if idx > prev_idx + 1:
            result_lines.append("...")
        result_lines.append(f"{idx + 1}: {all_lines[idx]}")
        prev_idx = idx

    return "\n".join(result_lines)


# ── Patch parsing and application ────────────────────────────────────

# Regex for FILE/ORIGINAL/REPLACEMENT patch blocks emitted by agents
_PATCH_PATTERN = re.compile(
    r"FILE:\s*(.*?)\n.*?ORIGINAL:\n```(?:python)?\n(.*?)\n```.*?REPLACEMENT:\n```(?:python)?\n(.*?)\n```",
    re.DOTALL,
)


def parse_and_apply_fixes(llm_output: str) -> int:
    """Parse FILE/ORIGINAL/REPLACEMENT blocks from LLM output and apply them to disk.

    Returns:
        Number of fixes successfully applied.
    """
    fixes_applied = 0
    for match in _PATCH_PATTERN.finditer(llm_output):
        file_path = match.group(1).strip()
        original = match.group(2)
        replacement = match.group(3)

        path = Path(file_path)
        if path.exists():
            content = path.read_text(encoding="utf-8")
            if original in content:
                new_content = content.replace(original, replacement, 1)
                path.write_text(new_content, encoding="utf-8")
                fixes_applied += 1
                log.info("Applied fix to %s", file_path)
            else:
                log.warning("Could not find exact original block in %s", file_path)
    return fixes_applied


# ── File extraction from tool output ─────────────────────────────────


def extract_files_from_output(output: str) -> set[str]:
    """Extract .py file paths from ruff/mypy/pytest output lines.

    Tries ruff JSON first, falls back to regex line parsing.
    Handles common prefixes like '--> ' and './' in tool output.
    """
    # Try structured JSON first
    json_files = extract_files_from_ruff_json(output)
    if json_files:
        return json_files

    # Fall back to regex parsing for mypy/pytest/plain ruff output
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
            if path.startswith("./") or path.startswith(".\\"):
                path = path[2:]
            files.add(path)
        elif " " in line:
            first_word = line.split(" ")[0].strip()
            if first_word.endswith(".py"):
                path = first_word
                if path.startswith("./") or path.startswith(".\\"):
                    path = path[2:]
                files.add(path)
    return files
