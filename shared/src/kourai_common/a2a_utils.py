"""Shared A2A protocol utilities for Kourai Khryseai agents.

Centralizes common A2A message handling patterns used across multiple agents.

# A2A Spec v1.0 migration notes
# WHY: The v1.0 spec replaces TextPart/FilePart/DataPart with a unified Part
# type using member-based discrimination ("text" in part, "url" in part, etc.)
# and renames mimeType → mediaType. All Part inspection is funnelled through
# _is_file_part() and _get_file_bytes() so migration is a single-function change.
"""

from __future__ import annotations

from typing import Any

from a2a.server.agent_execution import RequestContext
from a2a.types import FileWithBytes

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
