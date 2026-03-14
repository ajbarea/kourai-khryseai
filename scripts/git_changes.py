"""Collect git changes for Mneme's commit message generation.

Gathers git status + diffs (staged and unstaged) into a single string.
Truncates large diffs to stay within LLM context limits.

Usage:
    # As a module
    from scripts.git_changes import collect_git_changes
    output = collect_git_changes()

    # Standalone
    uv run python scripts/git_changes.py
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

# Budget limits — keep total output under ~15k chars so Mneme's LLM
# has room for the system prompt + response.
MAX_TOTAL_CHARS = 15_000
MAX_PER_FILE_CHARS = 3_000
TRUNCATION_NOTICE = "\n... [truncated — diff too large] ...\n"


def _run_git(*args: str, cwd: str | Path | None = None) -> str:
    """Run a git command and return stdout, or empty string on failure."""
    git_bin = shutil.which("git")
    if not git_bin:
        log.warning("git binary not found in PATH")
        return ""

    try:
        result = subprocess.run(  # noqa: S603 — no untrusted input to git args
            [git_bin, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            timeout=10,
        )
        return result.stdout
    except Exception as e:
        log.warning("git %s failed: %s", " ".join(args), e)
        return ""


def _truncate_diff_per_file(diff_text: str) -> str:
    """Truncate individual file diffs that exceed MAX_PER_FILE_CHARS.

    Splits on 'diff --git' boundaries, caps each section, reassembles.
    """
    if not diff_text:
        return diff_text

    sections = diff_text.split("diff --git ")
    result_parts: list[str] = []

    for section in sections:
        if not section.strip():
            continue
        prefixed = f"diff --git {section}"
        if len(prefixed) > MAX_PER_FILE_CHARS:
            # Keep the header (first 3 lines) + truncation notice
            lines = prefixed.splitlines(keepends=True)
            header = "".join(lines[:4])
            result_parts.append(header + TRUNCATION_NOTICE)
        else:
            result_parts.append(prefixed)

    return "\n".join(result_parts)


def collect_git_changes(cwd: str | Path | None = None) -> str:
    """Collect git status and diffs into a structured string for Mneme.

    Args:
        cwd: Working directory for git commands. Defaults to current dir.

    Returns:
        Combined git status + diff output, truncated to fit LLM context.
    """
    status = _run_git("status", "--porcelain", cwd=cwd)
    if not status.strip():
        return "No changes detected (working tree clean)."

    unstaged = _run_git("diff", cwd=cwd)
    staged = _run_git("diff", "--staged", cwd=cwd)

    # Truncate per-file diffs before assembling
    unstaged = _truncate_diff_per_file(unstaged)
    staged = _truncate_diff_per_file(staged)

    parts: list[str] = []
    parts.append("=== git status ===")
    parts.append(status.rstrip())

    if staged.strip():
        parts.append("\n=== Staged changes (git diff --staged) ===")
        parts.append(staged.rstrip())

    if unstaged.strip():
        parts.append("\n=== Unstaged changes (git diff) ===")
        parts.append(unstaged.rstrip())

    output = "\n".join(parts)

    # Final total truncation — keep the status + as much diff as fits
    if len(output) > MAX_TOTAL_CHARS:
        output = output[:MAX_TOTAL_CHARS] + TRUNCATION_NOTICE
        log.info("Git changes truncated to %d chars", MAX_TOTAL_CHARS)

    log.info("Collected %d chars of git changes", len(output))
    return output


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log.info(collect_git_changes())
