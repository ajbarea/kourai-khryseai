"""Forge tool registry — provider tool-use schemas and handlers for file ops.

These are the OpenAI-style tool definitions that Techne, Dokimasia, and Kallos
expose to the LLM via :func:`kourai_common.llm.chat_with_tools`. Each handler
takes a ``project_root`` (injected via ``handler_context``) and routes file
ops through :func:`validate_file_path` so the model cannot escape the
worktree. Path translation (:func:`_translate_to_container`) handles the
host-vs-container path mismatch when specialists run inside their own image.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from kourai_common.a2a_utils import _translate_to_container
from kourai_common.file_ops import PathViolation, validate_file_path
from kourai_common.subprocess import read_file_with_context

log = logging.getLogger(__name__)


FORGE_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Create a new file or overwrite an existing one. Use for new "
                "modules and full rewrites. Path is project-relative."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Project-relative file path (e.g. src/foo.py).",
                    },
                    "content": {
                        "type": "string",
                        "description": (
                            "Full file content. A trailing newline is added if missing."
                        ),
                    },
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Replace exactly one occurrence of `old_string` with `new_string` "
                "in an existing file. Fails if `old_string` is missing or "
                "appears more than once — extend it with surrounding context "
                "to make it unique. Use for surgical edits."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project-relative path."},
                    "old_string": {
                        "type": "string",
                        "description": ("Exact text to find. Must appear once and only once."),
                    },
                    "new_string": {"type": "string", "description": "Replacement text."},
                },
                "required": ["path", "old_string", "new_string"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": ("Remove a file from the project. No-op if the file does not exist."),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project-relative path."},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a file's contents to inspect what is already on disk before "
                "editing. Returns line-numbered text. Use this before edit_file "
                "if you are not certain of the exact text to match."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project-relative path."},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
]


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
    """Tool handler — return line-numbered contents."""
    try:
        target = _resolve(path, project_root)
    except PathViolation as exc:
        return f"ERROR: {exc}"
    if not target.exists():
        return f"ERROR: file not found: {path}"
    return read_file_with_context(str(target))


FORGE_TOOL_HANDLERS: dict[str, Any] = {
    "write_file": write_file,
    "edit_file": edit_file,
    "delete_file": delete_file,
    "read_file": read_file,
}


MUTATING_TOOL_NAMES: frozenset[str] = frozenset({"write_file", "edit_file", "delete_file"})


def count_successful_writes(tool_log: list[dict[str, Any]]) -> int:
    """Count tool calls in ``tool_log`` that mutated disk without erroring."""
    return sum(
        1
        for entry in tool_log
        if entry["name"] in MUTATING_TOOL_NAMES and not entry["result"].startswith("ERROR:")
    )
