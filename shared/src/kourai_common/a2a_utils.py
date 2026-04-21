"""Shared A2A protocol utilities for Kourai Khryseai agents.

Centralizes common A2A message handling patterns used across multiple agents.

# A2A Spec v1.0 migration notes
# The v1.0 spec replaces TextPart/FilePart/DataPart with a unified Part
# type using member-based discrimination ("text" in part, "url" in part, etc.)
# and renames mimeType → mediaType. All Part inspection is funnelled through
# _is_file_part() and _get_file_bytes() so migration is a single-function change.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from a2a.types import FileWithBytes

if TYPE_CHECKING:
    from a2a.server.agent_execution import RequestContext

# ── Project root extraction ───────────────────────────────────────────


_PROJECT_ROOT_PATTERNS = (
    re.compile(r"^Project root:\s*(.+)$", re.MULTILINE),
    re.compile(r"\[project_root:\s*([^\]]+)\]", re.IGNORECASE),
    re.compile(r"\[Project Settings\]:\s*root=([^\s\]]+)", re.IGNORECASE),
)
# The CLI runs as the host user (/home/<host_user>/.kourai_khryseai/...)
# while specialists run inside containers that bind-mount the same dir at
# /home/kourai/.kourai_khryseai. _translate_to_container rewrites any host
# path pointing into .kourai_khryseai to the container-local form.
_PROJECTS_MARKER = ".kourai_khryseai"


def _translate_to_container(path: Path) -> Path:
    """Remap host-side .kourai_khryseai paths into this process's $HOME mirror.

    On the host, the CLI emits paths like /home/ajbar/.kourai_khryseai/projects/...
    Inside a specialist container the same tree is mounted at
    /home/kourai/.kourai_khryseai, so the host prefix must be rewritten before
    the path can be opened.
    """
    parts = path.parts
    for i, segment in enumerate(parts):
        if segment == _PROJECTS_MARKER:
            local = Path.home() / _PROJECTS_MARKER
            return local.joinpath(*parts[i + 1 :]) if i + 1 < len(parts) else local
    return path


def parse_project_root(text: str) -> Path:
    """Recover the player's project directory from any context-injection format.

    Specialist agents (Kallos, Dokimasia, Techne) call this to get the worktree
    path so subprocesses and file writes land in the forge session directory
    instead of the Kourai codebase's cwd.

    Accepts all historical/current injection shapes defensively:
      * ``Project root: /path`` — canonical form injected by Hephaestus into the
        forge transcript.
      * ``[project_root: /path]`` — bracket tag the CLI prepends on the outbound
        prompt before Hephaestus strips it.
      * ``[Project Settings]: root=/path`` — legacy transcript key.

    Paths under ``.kourai_khryseai`` are translated from the host user's home
    to this process's home so the same path works from the CLI (host) and
    from specialist containers (bind-mounted at ``/home/kourai``).

    Falls back to ``Path.cwd()`` when no tag is present (internal tasks) or the
    parsed path no longer exists on disk.
    """
    for pattern in _PROJECT_ROOT_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = Path(match.group(1).strip())
            candidate = _translate_to_container(raw)
            if candidate.is_dir():
                return candidate
    return Path.cwd()


# ── Part inspection helpers (v1.0 migration firewall) ────────────────


def _is_file_part(root: Any) -> bool:
    """Return True if the Part root contains embedded file bytes.

    Currently checks SDK 0.3.x FilePart structure. When SDK reaches 1.0,
    update to check `"raw" in root` or `"url" in root` per the new spec.
    """
    return hasattr(root, "file") and isinstance(root.file, FileWithBytes)


def _get_file_bytes(root: Any) -> tuple[str, str]:
    """Extract (base64_bytes, mime_type) from a file Part root.

    Returns:
        (bytes_str, mime_type) — mime defaults to 'image/png' if unset.
    """
    # SDK 0.3.x path
    return root.file.bytes, root.file.mime_type or "image/png"  # type: ignore[union-attr]


# ── Public API ───────────────────────────────────────────────────────


def extract_image_parts(context: RequestContext) -> list[dict]:
    """Build LiteLLM image_url blocks from any FilePart in the incoming message.

    Args:
        context: A2A request context containing the incoming message.

    Returns:
        List of LiteLLM-compatible image_url dictionaries for multimodal chat.
        Empty list if no files present.

    Example:
        >>> image_parts = extract_image_parts(context)
        >>> messages = [
        ...     {"role": "user", "content": [{"type": "text", "text": "..."}, *image_parts]}
        ... ]
    """
    image_parts: list[dict] = []
    if not context.message:
        return image_parts

    for part in context.message.parts:
        root = part.root
        if _is_file_part(root):
            b64, mime = _get_file_bytes(root)
            image_parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                }
            )
    return image_parts


def extract_file_attachments(context: RequestContext) -> list[tuple[str, str]]:
    """Extract raw file data from A2A message as (bytes, mime_type) tuples.

    Args:
        context: A2A request context containing the incoming message.

    Returns:
        List of (base64_bytes, mime_type) tuples. Empty list if no files present.

    Example:
        >>> attachments = extract_file_attachments(context)
        >>> for bytes_data, mime_type in attachments:
        ...     process_file(bytes_data, mime_type)
    """
    attachments: list[tuple[str, str]] = []
    if not context.message:
        return attachments

    for part in context.message.parts:
        root = part.root
        if _is_file_part(root):
            attachments.append(_get_file_bytes(root))
    return attachments
