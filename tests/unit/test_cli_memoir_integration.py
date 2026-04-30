"""Integration: CLI streaming writes ordered Memoir entries to a session workdir."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from a2a.types import Task, TaskArtifactUpdateEvent, TaskState

from hosts.cli.streaming import send_and_stream
from kourai_common.federation.host_helpers import derive_scene_id
from kourai_common.federation.memoir import Memoir
from tests.conftest import make_stream_response


def _make_completed_task() -> MagicMock:
    task = MagicMock(spec=Task)
    task.id = "task-1"
    task.context_id = "ctx-1"
    task.status = MagicMock()
    task.status.state = TaskState.TASK_STATE_COMPLETED
    return task


@pytest.mark.asyncio
async def test_two_turns_produce_two_ordered_entries(monkeypatch, tmp_path):
    """A session that runs twice writes two MemoirEntries in turn order."""

    monkeypatch.setattr(
        "hosts.cli.streaming.get_last_seen_agent",
        lambda: "techne",
    )

    artifact_texts = iter(["first artifact", "second artifact"])
    monkeypatch.setattr(
        "hosts.cli.streaming._extract_artifact_text",
        lambda _: next(artifact_texts),
    )

    memoir = Memoir(tmp_path)
    session_id = "deadbeef0000ffff"

    for turn in (1, 2):
        client = MagicMock()
        task = _make_completed_task()
        artifact_event = MagicMock(spec=TaskArtifactUpdateEvent)
        artifact_event.context_id = "ctx-1"
        artifact_event.task_id = "task-1"

        async def _events(task=task, artifact_event=artifact_event):
            yield make_stream_response(artifact_event)
            yield make_stream_response(task)

        client.send_message = MagicMock(return_value=_events())

        await send_and_stream(
            client,
            f"prompt-{turn}",
            "ctx-1",
            memoir=memoir,
            scene_id=derive_scene_id(session_id, turn_number=turn),
        )

    entries = list(memoir.entries())
    assert len(entries) == 2
    assert entries[0].scene_id == "session-deadbeef.turn-1"
    assert entries[0].agent_proposed == "first artifact"
    assert entries[1].scene_id == "session-deadbeef.turn-2"
    assert entries[1].agent_proposed == "second artifact"


@pytest.mark.asyncio
async def test_unknown_agent_does_not_break_pipeline(monkeypatch, tmp_path):
    """If get_last_seen_agent returns something not in ALL_AGENTS, the pipeline
    still completes successfully; the entry is silently skipped."""

    monkeypatch.setattr(
        "hosts.cli.streaming.get_last_seen_agent",
        lambda: "nobody",  # not a known maiden
    )
    monkeypatch.setattr(
        "hosts.cli.streaming._extract_artifact_text",
        lambda _: "some artifact",
    )

    client = MagicMock()
    task = _make_completed_task()
    artifact_event = MagicMock(spec=TaskArtifactUpdateEvent)
    artifact_event.context_id = "ctx-1"
    artifact_event.task_id = "task-1"

    async def _events():
        yield make_stream_response(artifact_event)
        yield make_stream_response(task)

    client.send_message = MagicMock(return_value=_events())

    memoir = Memoir(tmp_path)
    cont, ctx, tid = await send_and_stream(
        client,
        "prompt",
        "ctx-1",
        memoir=memoir,
        scene_id="session-deadbeef.turn-1",
    )

    # Pipeline must still report success.
    assert cont is True
    # No entry written because the agent is unknown.
    assert list(memoir.entries()) == []
