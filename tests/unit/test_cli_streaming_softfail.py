"""Soft-fail surface (#17) — host CLI banner when mneme reports zero commits.

When the pipeline cascades through specialists but mneme's commit_messages
artifact carries ``commit_count: 0`` (no diff to commit / LLM emitted no
conventional-commit lines), the CLI renders an explicit warning banner
above the "Forged in" line. Without this, the gold "Forged in N.Ns"
reads as success even when nothing actually landed on the worktree.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from a2a.types import Task, TaskArtifactUpdateEvent, TaskState

from hosts.cli.streaming import send_and_stream
from kourai_common.messaging import data_part, text_part
from tests.conftest import make_stream_response


def _completed_task() -> MagicMock:
    task = MagicMock(spec=Task)
    task.id = "task-1"
    task.context_id = "ctx-1"
    task.status = MagicMock()
    task.status.state = TaskState.TASK_STATE_COMPLETED
    return task


def _artifact_event(parts: list) -> MagicMock:
    event = MagicMock(spec=TaskArtifactUpdateEvent)
    event.context_id = "ctx-1"
    event.task_id = "task-1"
    event.artifact = MagicMock()
    event.artifact.parts = parts
    return event


@pytest.mark.asyncio
async def test_zero_commit_count_renders_softfail_banner(monkeypatch):
    captured: list[str] = []
    monkeypatch.setattr("hosts.cli.streaming._echo", captured.append)
    monkeypatch.setattr(
        "hosts.cli.streaming._render_markdown", lambda text: text
    )
    monkeypatch.setattr(
        "hosts.cli.streaming._extract_artifact_text", lambda _: "Final result"
    )
    monkeypatch.setattr("hosts.cli.streaming.get_last_seen_agent", lambda: "mneme")

    client = MagicMock()
    artifact = _artifact_event(
        [text_part("Final result"), data_part({"commit_count": 0, "commit_types": []})]
    )

    async def _events():
        yield make_stream_response(artifact)
        yield make_stream_response(_completed_task())

    client.send_message = MagicMock(return_value=_events())

    await send_and_stream(client, "prompt", "ctx-1")

    joined = "\n".join(captured)
    assert "No commits produced" in joined
    assert "the forge ran but" in joined


@pytest.mark.asyncio
async def test_nonzero_commit_count_no_banner(monkeypatch):
    captured: list[str] = []
    monkeypatch.setattr("hosts.cli.streaming._echo", captured.append)
    monkeypatch.setattr(
        "hosts.cli.streaming._render_markdown", lambda text: text
    )
    monkeypatch.setattr(
        "hosts.cli.streaming._extract_artifact_text", lambda _: "Final result"
    )
    monkeypatch.setattr("hosts.cli.streaming.get_last_seen_agent", lambda: "mneme")

    client = MagicMock()
    artifact = _artifact_event(
        [
            text_part("Final result"),
            data_part({"commit_count": 3, "commit_types": ["feat", "test"]}),
        ]
    )

    async def _events():
        yield make_stream_response(artifact)
        yield make_stream_response(_completed_task())

    client.send_message = MagicMock(return_value=_events())

    await send_and_stream(client, "prompt", "ctx-1")

    joined = "\n".join(captured)
    assert "No commits produced" not in joined


@pytest.mark.asyncio
async def test_no_commit_count_artifact_no_banner(monkeypatch):
    """A run that never reaches mneme (e.g. confirmation-only turn) must
    not show the soft-fail banner — observed_commit_count stays None."""
    captured: list[str] = []
    monkeypatch.setattr("hosts.cli.streaming._echo", captured.append)
    monkeypatch.setattr(
        "hosts.cli.streaming._render_markdown", lambda text: text
    )
    monkeypatch.setattr(
        "hosts.cli.streaming._extract_artifact_text", lambda _: "Final result"
    )
    monkeypatch.setattr("hosts.cli.streaming.get_last_seen_agent", lambda: "hephaestus")

    client = MagicMock()
    # Artifact carries text + a non-commit-count data part.
    artifact = _artifact_event(
        [text_part("Final result"), data_part({"mode": "pipeline", "agents": ["metis"]})]
    )

    async def _events():
        yield make_stream_response(artifact)
        yield make_stream_response(_completed_task())

    client.send_message = MagicMock(return_value=_events())

    await send_and_stream(client, "prompt", "ctx-1")

    joined = "\n".join(captured)
    assert "No commits produced" not in joined
