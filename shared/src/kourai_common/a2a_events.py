"""A2A text extraction helpers shared across hosts and agents.

These helpers isolate SDK event/message shape handling behind a single module
so protocol-version changes (A2A 0.3 -> 1.0) can be migrated in one place.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from a2a.types import Message, Task, TaskArtifactUpdateEvent, TaskStatusUpdateEvent


def extract_parts_text(parts: object) -> str:
    """Extract text/data payloads from A2A parts."""
    if not isinstance(parts, list):
        return ""

    extracted: list[str] = []
    for part in parts:
        root = getattr(part, "root", None)
        text = getattr(root, "text", None)
        if isinstance(text, str) and text:
            extracted.append(text)
            continue

        data = getattr(root, "data", None)
        if data is not None:
            try:
                extracted.append(json.dumps(data, sort_keys=True))
            except TypeError:
                extracted.append(str(data))
    return "\n".join(extracted)


def extract_message_text(message: Message) -> str:
    """Pull text from a direct Message response."""
    return extract_parts_text(message.parts)


def extract_status_text(event: TaskStatusUpdateEvent) -> str:
    """Pull text from a status update event."""
    if event.status.message and hasattr(event.status.message, "parts"):
        return extract_parts_text(event.status.message.parts)
    return ""


def extract_artifact_text(event: TaskArtifactUpdateEvent) -> str:
    """Pull text from an artifact update event."""
    if event.artifact and hasattr(event.artifact, "parts"):
        return extract_parts_text(event.artifact.parts)
    return ""


def extract_task_text(task: Task) -> str:
    """Pull text from a completed task's artifacts or fallback status message."""
    if task.artifacts:
        artifact_text = "\n".join(
            extract_parts_text(artifact.parts)
            for artifact in task.artifacts
            if hasattr(artifact, "parts")
        )
        if artifact_text:
            return artifact_text

    if task.status.message and hasattr(task.status.message, "parts"):
        return extract_parts_text(task.status.message.parts)
    return ""
