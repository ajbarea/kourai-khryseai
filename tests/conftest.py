"""Shared test fixtures for Kourai Khryseai."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from a2a.types import Message, Task, TaskArtifactUpdateEvent, TaskStatusUpdateEvent


@pytest.fixture
def agent_ports() -> dict[str, int]:
    """Port assignments for all agents."""
    return {
        "hephaestus": 10000,
        "metis": 10001,
        "techne": 10002,
        "dokimasia": 10003,
        "kallos": 10004,
        "mneme": 10005,
    }


def make_stream_response(event: object) -> MagicMock:
    """Wrap an event in a StreamResponse-shaped mock for v1.0 ``client.send_message`` tests.

    Production consumes ``client.send_message`` yields via
    ``kourai_common.messaging.stream_event(response)``, which calls
    ``response.HasField("message" | "task" | "status_update" |
    "artifact_update")`` to discriminate the inner event. Test mocks that
    yielded raw ``Message`` / ``(task, update)`` tuples (the v0.3 yield
    shape) trip ``stream_event`` because tuples have no ``HasField``.

    This helper accepts any of the four inner event types — including
    ``MagicMock(spec=Type)`` instances, which ``isinstance`` recognizes —
    and returns a ``StreamResponse``-like mock with both the field
    attribute and ``HasField(name)`` wired so ``stream_event`` decodes it
    correctly.
    """
    sr = MagicMock()
    is_message = isinstance(event, Message)
    is_task = isinstance(event, Task)
    is_status = isinstance(event, TaskStatusUpdateEvent)
    is_artifact = isinstance(event, TaskArtifactUpdateEvent)

    def has_field(name: str) -> bool:
        if name == "message":
            return is_message
        if name == "task":
            return is_task
        if name == "status_update":
            return is_status
        if name == "artifact_update":
            return is_artifact
        return False

    sr.HasField = has_field
    if is_message:
        sr.message = event
    if is_task:
        sr.task = event
    if is_status:
        sr.status_update = event
    if is_artifact:
        sr.artifact_update = event
    return sr
