"""Shared A2A protocol utilities for Kourai Khryseai agents.

Centralizes common A2A message handling patterns used across multiple agents.
"""

from __future__ import annotations

from a2a.server.agent_execution import RequestContext
from a2a.types import FileWithBytes


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
        if hasattr(root, "file") and isinstance(root.file, FileWithBytes):
            mime = root.file.mime_type or "image/png"
            image_parts.append(
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{root.file.bytes}"}}
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
        if hasattr(root, "file") and isinstance(root.file, FileWithBytes):
            attachments.append((root.file.bytes, root.file.mime_type or "image/png"))
    return attachments
