"""CLI host: send_and_stream, banner, extract helpers, REPL config."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
from a2a.types import Message, Task, TaskState, TaskStatusUpdateEvent

from hosts.cli.__main__ import _extract_artifact_text, _extract_status_text, send_and_stream

# ---------------------------------------------------------------------------
# Extract helpers
# ---------------------------------------------------------------------------


class TestExtractStatusText:
    """_extract_status_text edge cases."""

    def test_returns_empty_for_none_message(self):
        event = MagicMock()
        event.status.message = None
        assert _extract_status_text(event) == ""

    def test_extracts_text_from_parts(self):
        part = MagicMock()
        part.root.text = "Working..."
        event = MagicMock()
        event.status.message.parts = [part]
        assert _extract_status_text(event) == "Working..."

    def test_joins_multiple_parts(self):
        p1 = MagicMock()
        p1.root.text = "line 1"
        p2 = MagicMock()
        p2.root.text = "line 2"
        event = MagicMock()
        event.status.message.parts = [p1, p2]
        assert _extract_status_text(event) == "line 1\nline 2"

    def test_skips_non_text_parts(self):
        p1 = MagicMock()
        del p1.root.text
        p2 = MagicMock()
        p2.root.text = "text part"
        event = MagicMock()
        event.status.message.parts = [p1, p2]
        result = _extract_status_text(event)
        assert "text part" in result


class TestExtractArtifactText:
    """_extract_artifact_text edge cases."""

    def test_returns_empty_for_none_artifact(self):
        event = MagicMock()
        event.artifact = None
        assert _extract_artifact_text(event) == ""

    def test_returns_empty_for_no_parts(self):
        event = MagicMock()
        event.artifact.parts = []
        assert _extract_artifact_text(event) == ""

    def test_extracts_text(self):
        part = MagicMock()
        part.root.text = "final result"
        event = MagicMock()
        event.artifact.parts = [part]
        assert _extract_artifact_text(event) == "final result"


# ---------------------------------------------------------------------------
# send_and_stream — new ClientFactory API
# ---------------------------------------------------------------------------


def _make_task(state: TaskState = TaskState.working) -> MagicMock:
    task = MagicMock(spec=Task)
    task.id = "task-1"
    task.context_id = "ctx-1"
    task.status = MagicMock()
    task.status.state = state
    return task


class TestSendAndStream:
    """Core streaming function using new Client.send_message API."""

    @pytest.mark.asyncio
    async def test_handles_status_updates(self):
        task = _make_task()
        status = MagicMock()
        status.__class__ = TaskStatusUpdateEvent  # type: ignore[assignment]
        status.status.state = TaskState.working
        status.status.message = None

        async def mock_send(message, **kwargs):
            yield (task, status)

        client = MagicMock()
        client.send_message = mock_send

        cont, ctx, tid = await send_and_stream(client, "hello", "ctx-1")
        assert cont is True

    @pytest.mark.asyncio
    async def test_handles_connect_error(self):
        async def mock_send(message, **kwargs):
            raise httpx.ConnectError("refused")
            yield  # noqa: E501

        client = MagicMock()
        client.send_message = mock_send

        cont, ctx, tid = await send_and_stream(client, "hello", "ctx-1")
        assert cont is True

    @pytest.mark.asyncio
    async def test_handles_timeout(self):
        async def mock_send(message, **kwargs):
            raise httpx.TimeoutException("timed out")
            yield  # noqa: E501

        client = MagicMock()
        client.send_message = mock_send

        cont, ctx, tid = await send_and_stream(client, "hello", "ctx-1")
        assert cont is True

    @pytest.mark.asyncio
    async def test_handles_message_response(self):
        """Direct Message response (no task created)."""
        part = MagicMock()
        part.root.text = "direct reply"
        msg = MagicMock(spec=Message)
        msg.parts = [part]

        async def mock_send(message, **kwargs):
            yield msg

        client = MagicMock()
        client.send_message = mock_send

        cont, ctx, tid = await send_and_stream(client, "hello", "ctx-1")
        assert cont is True

    @pytest.mark.asyncio
    async def test_verbose_mode(self):
        async def mock_send(message, **kwargs):
            return
            yield  # noqa: E501

        client = MagicMock()
        client.send_message = mock_send

        cont, ctx, tid = await send_and_stream(client, "hello", "ctx-1", verbose=True)
        assert cont is True


class TestMainCommand:
    """CLI main command configuration."""

    def test_has_agent_option(self):
        from hosts.cli.__main__ import main

        param_names = [p.name for p in main.params]
        assert "agent" in param_names

    def test_has_timeout_option(self):
        from hosts.cli.__main__ import main

        param_names = [p.name for p in main.params]
        assert "timeout" in param_names
