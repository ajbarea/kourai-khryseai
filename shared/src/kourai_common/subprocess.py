"""Shared subprocess utilities for Kourai Khryseai agents.

Centralizes run_command and parse_and_apply_fixes so agents don't duplicate them.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)


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


def extract_files_from_output(output: str) -> set[str]:
    """Extract .py file paths from ruff/mypy/pytest output lines.

    Handles common prefixes like '--> ' and './' in tool output.
    """
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
