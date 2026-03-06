"""RemoteAgentConnection: connect, send, extract, close."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from a2a.types import Task, TaskArtifactUpdateEvent, TaskState, TaskStatus

from agents.hephaestus.remote_connections import AgentInputRequired, RemoteAgentConnection


class TestRemoteAgentConnectionInit:
    """Constructor and field setup."""

    def test_fields_set(self):
        conn = RemoteAgentConnection("metis", "http://localhost:10001/")
        assert conn.agent_name == "metis"
        assert conn.agent_url == "http://localhost:10001/"
        assert conn.client is None
        assert conn.card is None

    def test_http_client_created(self):
        conn = RemoteAgentConnection("techne", "http://localhost:10002/")
        assert conn.http is not None


class TestRemoteAgentConnectionConnect:
    """Agent card resolution and client init."""

    @pytest.mark.asyncio
    async def test_connect_sets_card_and_client(self):
        mock_card = MagicMock()
        mock_card.name = "Metis"

        mock_resolver = MagicMock()
        mock_resolver.get_agent_card = AsyncMock(return_value=mock_card)

        mock_client = MagicMock()
        mock_factory = MagicMock()
        mock_factory.create = MagicMock(return_value=mock_client)

        with (
            patch("agents.hephaestus.remote_connections.create_span"),
            patch(
                "agents.hephaestus.remote_connections.A2ACardResolver",
                return_value=mock_resolver,
            ),
            patch(
                "agents.hephaestus.remote_connections.ClientFactory",
                return_value=mock_factory,
            ),
        ):
            conn = RemoteAgentConnection("metis", "http://localhost:10001/")
            await conn.connect()

        assert conn.card == mock_card
        assert conn.client == mock_client
        mock_factory.create.assert_called_once_with(mock_card)

    @pytest.mark.asyncio
    async def test_connect_no_card_leaves_client_none(self):
        mock_resolver = MagicMock()
        mock_resolver.get_agent_card = AsyncMock(return_value=None)

        with (
            patch("agents.hephaestus.remote_connections.create_span"),
            patch(
                "agents.hephaestus.remote_connections.A2ACardResolver",
                return_value=mock_resolver,
            ),
        ):
            conn = RemoteAgentConnection("metis", "http://localhost:10001/")
            await conn.connect()

        assert conn.card is None
        assert conn.client is None


def _make_artifact_part(text: str) -> MagicMock:
    """Create a mock Part with .root.text."""
    part = MagicMock()
    part.root.text = text
    return part


def _make_task_with_artifact(text: str, state: TaskState = TaskState.completed) -> MagicMock:
    """Create a mock Task with artifacts containing text."""
    task = MagicMock(spec=Task)
    task.context_id = "ctx-1"
    task.id = "task-1"
    task.status = MagicMock(spec=TaskStatus)
    task.status.state = state
    artifact = MagicMock()
    artifact.parts = [_make_artifact_part(text)]
    task.artifacts = [artifact]
    return task


async def _async_iter(*items):
    """Create an async iterator from items."""
    for item in items:
        yield item


class TestRemoteAgentConnectionSend:
    """Message sending and response extraction."""

    @pytest.mark.asyncio
    async def test_send_raises_if_not_connected(self):
        conn = RemoteAgentConnection("metis", "http://localhost:10001/")
        with pytest.raises(RuntimeError, match="Not connected"):
            await conn.send.__wrapped__(conn, "hello", "ctx-1")

    @pytest.mark.asyncio
    async def test_send_extracts_artifact_from_task_snapshot(self):
        """Non-streaming: final Task snapshot with artifacts."""
        task = _make_task_with_artifact("generated code")

        mock_client = MagicMock()
        # send_message yields (Task, None) for non-streaming
        mock_client.send_message = MagicMock(return_value=_async_iter((task, None)))

        with (
            patch("agents.hephaestus.remote_connections.create_span"),
            patch("agents.hephaestus.remote_connections.get_trace_context", return_value={}),
        ):
            conn = RemoteAgentConnection("techne", "http://localhost:10002/")
            conn.client = mock_client
            result = await conn.send.__wrapped__(conn, "fix auth", "ctx-1")

        assert result == "generated code"

    @pytest.mark.asyncio
    async def test_send_extracts_artifact_from_event(self):
        """Streaming: TaskArtifactUpdateEvent with artifact."""
        task = MagicMock(spec=Task)
        task.context_id = "ctx-1"
        task.id = "task-1"

        artifact_event = MagicMock(spec=TaskArtifactUpdateEvent)
        artifact_event.artifact = MagicMock()
        artifact_event.artifact.parts = [_make_artifact_part("streamed code")]

        mock_client = MagicMock()
        mock_client.send_message = MagicMock(return_value=_async_iter((task, artifact_event)))

        with (
            patch("agents.hephaestus.remote_connections.create_span"),
            patch("agents.hephaestus.remote_connections.get_trace_context", return_value={}),
        ):
            conn = RemoteAgentConnection("techne", "http://localhost:10002/")
            conn.client = mock_client
            result = await conn.send.__wrapped__(conn, "fix auth", "ctx-1")

        assert result == "streamed code"

    @pytest.mark.asyncio
    async def test_send_raises_input_required(self):
        """TaskStatusUpdateEvent with input_required state raises."""
        from a2a.types import TaskStatusUpdateEvent

        task = MagicMock(spec=Task)
        task.context_id = "ctx-1"
        task.id = "task-1"

        status_event = MagicMock(spec=TaskStatusUpdateEvent)
        status_event.status = MagicMock()
        status_event.status.state = TaskState.input_required
        question_part = _make_artifact_part("Which file?")
        status_event.status.message.parts = [question_part]

        mock_client = MagicMock()
        mock_client.send_message = MagicMock(return_value=_async_iter((task, status_event)))

        with (
            patch("agents.hephaestus.remote_connections.create_span"),
            patch("agents.hephaestus.remote_connections.get_trace_context", return_value={}),
        ):
            conn = RemoteAgentConnection("metis", "http://localhost:10001/")
            conn.client = mock_client
            with pytest.raises(AgentInputRequired) as exc_info:
                await conn.send.__wrapped__(conn, "plan something", "ctx-1")

        assert exc_info.value.agent_name == "metis"
        assert "Which file" in exc_info.value.question


class TestRemoteAgentConnectionClose:
    """HTTP client cleanup."""

    @pytest.mark.asyncio
    async def test_close_calls_aclose(self):
        conn = RemoteAgentConnection("mneme", "http://localhost:10005/")
        conn.http = AsyncMock()
        conn.client = AsyncMock()
        await conn.close()
        conn.client.close.assert_called_once()
        conn.http.aclose.assert_called_once()


class TestExtractHelpers:
    """The _extract_*_text helper methods."""

    def test_extract_message_text(self):
        from a2a.types import Message

        msg = MagicMock(spec=Message)
        msg.parts = [_make_artifact_part("hello")]

        conn = RemoteAgentConnection("kallos", "http://localhost:10004/")
        assert conn._extract_message_text(msg) == "hello"

    def test_extract_task_text_from_artifacts(self):
        task = _make_task_with_artifact("artifact text")
        conn = RemoteAgentConnection("kallos", "http://localhost:10004/")
        assert conn._extract_task_text(task) == "artifact text"

    def test_extract_task_text_falls_back_to_status(self):
        task = MagicMock(spec=Task)
        task.artifacts = None
        task.status = MagicMock()
        task.status.message.parts = [_make_artifact_part("status text")]

        conn = RemoteAgentConnection("kallos", "http://localhost:10004/")
        assert conn._extract_task_text(task) == "status text"
