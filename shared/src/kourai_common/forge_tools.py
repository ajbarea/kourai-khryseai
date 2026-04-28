"""Forge tool handlers — async file-op functions used by ``kourai-mcp-forge``.

These are the underlying async functions (``read_file``, ``write_file``,
``edit_file``, ``delete_file``) that the kourai-mcp-forge server delegates
to. Each takes ``project_root`` as a kw-only arg and routes file ops
through :func:`validate_file_path` so callers can't escape the worktree.
Path translation (:func:`_translate_to_container`) handles the
host-vs-container path mismatch when specialists run inside their own image.

The OpenAI-style tool surface specialists call against is sourced by
``kourai_common.mcp_bridge`` via ``await session.list_tools()`` against
``kourai-mcp-forge``, so the schema is single-sourced through MCP rather
than duplicated as a static export.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from kourai_common.a2a_utils import _translate_to_container
from kourai_common.file_ops import PathViolation, validate_file_path
from kourai_common.subprocess import read_file_with_context

log = logging.getLogger(__name__)


def _resolve(path: str, project_root: Path | str) -> Path:
    """Validate and translate a model-supplied path. Raises PathViolation."""
    candidate = _translate_to_container(Path(path))
    return validate_file_path(project_root, candidate)


async def write_file(path: str, content: str, *, project_root: Path | str) -> str:
    """Tool handler — create or overwrite a file inside ``project_root``."""
    try:
        target = _resolve(path, project_root)
    except PathViolation as exc:
        return f"ERROR: {exc}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not content.endswith("\n"):
        content += "\n"
    target.write_text(content, encoding="utf-8")
    log.info("forge tool write_file %s (%d chars)", path, len(content))
    return f"Wrote {path} ({len(content)} chars)."


async def edit_file(
    path: str,
    old_string: str,
    new_string: str,
    *,
    project_root: Path | str,
) -> str:
    """Tool handler — replace exactly one occurrence of ``old_string``."""
    try:
        target = _resolve(path, project_root)
    except PathViolation as exc:
        return f"ERROR: {exc}"
    if not target.exists():
        return f"ERROR: file not found: {path}"
    content = target.read_text(encoding="utf-8")
    occurrences = content.count(old_string)
    if occurrences == 0:
        return f"ERROR: old_string not found in {path}"
    if occurrences > 1:
        return (
            f"ERROR: old_string matched {occurrences} times in {path}; "
            "extend it with surrounding context for a unique match"
        )
    target.write_text(content.replace(old_string, new_string, 1), encoding="utf-8")
    log.info("forge tool edit_file %s", path)
    return f"Edited {path}."


async def delete_file(path: str, *, project_root: Path | str) -> str:
    """Tool handler — remove a file if it exists."""
    try:
        target = _resolve(path, project_root)
    except PathViolation as exc:
        return f"ERROR: {exc}"
    if target.exists():
        target.unlink()
        log.info("forge tool delete_file %s", path)
        return f"Deleted {path}."
    return f"No file at {path} (already absent)."


async def read_file(path: str, *, project_root: Path | str) -> str:
    """Tool handler — return line-numbered contents.

    Rejects directory paths explicitly so the model gets a clear error
    rather than a silent garbage-result. Round 6 caught Techne
    repeatedly trying directory paths through this handler; the schema
    description has been tightened too, but the runtime guard makes
    the error legible when the model still attempts it.
    """
    try:
        target = _resolve(path, project_root)
    except PathViolation as exc:
        return f"ERROR: {exc}"
    if not target.exists():
        return f"ERROR: file not found: {path}"
    if target.is_dir():
        return (
            f"ERROR: {path!r} is a directory; read_file expects a regular "
            "file. Use a more specific path or list the directory contents "
            "yourself before calling read_file."
        )
    return read_file_with_context(str(target))


MUTATING_TOOL_NAMES: frozenset[str] = frozenset({"write_file", "edit_file", "delete_file"})


def count_successful_writes(tool_log: list[dict[str, Any]]) -> int:
    """Count tool calls in ``tool_log`` that mutated disk without erroring."""
    return sum(
        1
        for entry in tool_log
        if entry["name"] in MUTATING_TOOL_NAMES and not entry["result"].startswith("ERROR:")
    )
