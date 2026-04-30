"""A2A text extraction helpers shared across hosts and agents.

Wraps SDK 1.0 protobuf attribute access behind one module so future
shape tweaks land in one place.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from google.protobuf.json_format import MessageToDict

if TYPE_CHECKING:
    from a2a.types import Message, Task, TaskArtifactUpdateEvent, TaskStatusUpdateEvent


def _has_field(part: object, field: str) -> bool:
    """Tolerant ``HasField`` check that copes with non-protobuf mocks.

    Real protobuf Parts answer ``HasField('text' | 'raw' | 'url' | 'data')``;
    test fixtures often use MagicMocks where ``HasField`` returns another
    MagicMock (truthy) regardless of which field is set. Fall back to a
    plain ``hasattr`` check in that case.
    """
    has_field = getattr(part, "HasField", None)
    if callable(has_field):
        try:
            result = has_field(field)
        except (TypeError, ValueError):
            return hasattr(part, field)
        if isinstance(result, bool):
            return result
    return hasattr(part, field)


def extract_parts_text(parts: object) -> str:
    """Extract text/data payloads from A2A parts."""
    if not isinstance(parts, list) and not hasattr(parts, "__iter__"):
        return ""

    extracted: list[str] = []
    for part in parts:  # ty: ignore[not-iterable]
        if _has_field(part, "text"):
            text = getattr(part, "text", None)
            if isinstance(text, str) and text:
                extracted.append(text)
                continue
        if _has_field(part, "data"):
            data = getattr(part, "data", None)
            if data is None:
                continue
            try:
                payload = MessageToDict(data)
            except Exception:
                payload = data
            try:
                extracted.append(json.dumps(payload, sort_keys=True))
            except TypeError:
                extracted.append(str(payload))
    return "\n".join(extracted)


def extract_parts_data(parts: object) -> list[dict]:
    """Pull structured-data payloads (DataPart) out of an A2A parts list.

    Mirror of ``extract_parts_text`` but returning the parsed dicts
    instead of a JSON-serialized blob — callers that need to inspect
    fields (e.g. host CLI checking ``commit_count``) get a typed view.
    """
    if not isinstance(parts, list) and not hasattr(parts, "__iter__"):
        return []

    out: list[dict] = []
    for part in parts:  # ty: ignore[not-iterable]
        if not _has_field(part, "data"):
            continue
        data = getattr(part, "data", None)
        if data is None:
            continue
        try:
            payload = MessageToDict(data)
        except Exception:
            payload = None
        if isinstance(payload, dict):
            out.append(payload)
    return out


def extract_artifact_data(event: TaskArtifactUpdateEvent) -> list[dict]:
    """Return the structured-data dicts emitted by an artifact event.

    Tolerant of ``MagicMock(spec=TaskArtifactUpdateEvent)`` instances that
    don't expose ``.artifact`` — the upstream protobuf class hides the
    field behind a descriptor that ``unittest.mock`` doesn't auto-mock.
    Pre-existing memoir/CLI tests build the mock without setting the
    attribute and rely on the host stubbing extractors at call time;
    this getattr keeps the new commit-count probe equally tolerant.
    """
    artifact = getattr(event, "artifact", None)
    if artifact and hasattr(artifact, "parts"):
        return extract_parts_data(list(artifact.parts))
    return []


def extract_message_text(message: Message) -> str:
    """Pull text from a direct Message response."""
    return extract_parts_text(list(message.parts))


def extract_status_text(event: TaskStatusUpdateEvent) -> str:
    """Pull text from a status update event."""
    if event.status.message and hasattr(event.status.message, "parts"):
        return extract_parts_text(list(event.status.message.parts))
    return ""


def extract_artifact_text(event: TaskArtifactUpdateEvent) -> str:
    """Pull text from an artifact update event."""
    if event.artifact and hasattr(event.artifact, "parts"):
        return extract_parts_text(list(event.artifact.parts))
    return ""


def extract_task_text(task: Task) -> str:
    """Pull text from a completed task's artifacts or fallback status message."""
    if task.artifacts:
        artifact_text = "\n".join(
            extract_parts_text(list(artifact.parts))
            for artifact in task.artifacts
            if hasattr(artifact, "parts")
        )
        if artifact_text:
            return artifact_text

    if task.status.message and hasattr(task.status.message, "parts"):
        return extract_parts_text(list(task.status.message.parts))
    return ""
