"""Shared subprocess utilities for Kourai Khryseai agents.

Centralizes run_command, parse_and_apply_fixes, and file extraction
so agents don't duplicate them.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

log = logging.getLogger(__name__)

_CONTEXT_LINES = 10

StatusCallback = Callable[[str], Awaitable[None]]


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
    cmd_str = " ".join(cmd)
    log.debug("Running: %s", cmd_str)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )

    if status_callback is None:
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )

    await status_callback(f"$ {cmd_str}")

    stdout_lines: list[str] = []

    async def _drain_stdout() -> None:
        assert proc.stdout is not None  # noqa: S101
        async for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip()
            stdout_lines.append(line)
            if line.strip():
                await status_callback(line)

    async def _drain_stderr() -> bytes:
        assert proc.stderr is not None  # noqa: S101
        return await proc.stderr.read()

    stderr_bytes, _ = await asyncio.gather(_drain_stderr(), _drain_stdout())
    await proc.wait()

    rc = proc.returncode or 0
    if rc != 0:
        await status_callback(f"exit {rc}")

    return rc, "\n".join(stdout_lines), stderr_bytes.decode("utf-8", errors="replace")


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


_PATCH_PATTERN = re.compile(
    r"FILE:\s*(.*?)\n.*?ORIGINAL:\n```(?:python)?\n(.*?)\n```.*?REPLACEMENT:\n```(?:python)?\n(.*?)\n```",
    re.DOTALL,
)


def parse_and_apply_fixes(
    llm_output: str,
    project_root: str | Path | None = None,
) -> int:
    """Parse FILE/ORIGINAL/REPLACEMENT blocks from LLM output and apply them to disk.

    Args:
        llm_output: LLM response containing FILE/ORIGINAL/REPLACEMENT blocks.
        project_root: Optional project root for path validation (safety check).
            If provided, all writes are validated to be inside this root.
            If not provided, writes proceed with a warning.

    Returns:
        Number of fixes successfully applied.

    Raises:
        PathViolation: If project_root is provided and any path escapes it.
    """
    from kourai_common.file_ops import PathViolation, validate_file_path

    fixes_applied = 0
    for match in _PATCH_PATTERN.finditer(llm_output):
        file_path = match.group(1).strip()
        original = match.group(2)
        replacement = match.group(3)

        if project_root:
            try:
                validated_path = validate_file_path(project_root, file_path)
            except PathViolation as e:
                log.error("Path validation failed: %s", e)
                continue
            path = validated_path
        else:
            path = Path(file_path)
            log.warning(
                "parse_and_apply_fixes called without project_root validation. "
                "This write may access files outside the intended project."
            )

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
