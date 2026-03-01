"""CLI host: send_and_stream, banner, constants, REPL helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
from a2a.types import (
    JSONRPCErrorResponse,
    TaskState,
    TaskStatusUpdateEvent,
)

from hosts.cli.__main__ import (
    AGENT_EMOJI,
    BANNER,
    _extract_artifact_text,
    _extract_status_text,
    send_and_stream,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestCLIConstants:
    """Banner, emoji map, and ANSI codes."""

    def test_banner_contains_project_name(self):
        assert "Kourai Khryseai" in BANNER

    def test_emoji_map_has_all_agents(self):
        expected = {"hephaestus", "metis", "techne", "dokimasia", "kallos", "mneme"}
        assert set(AGENT_EMOJI.keys()) == expected


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
        del p1.root.text  # Simulate a part without .root.text
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
# send_and_stream
# ---------------------------------------------------------------------------


class TestSendAndStream:
    """Core streaming function."""

    @pytest.mark.asyncio
    async def test_handles_status_updates(self):
        inner = MagicMock()
        inner.task_id = "task-1"
        inner.context_id = "ctx-1"
        inner.status.state = TaskState.working
        inner.status.message = None
        # Make isinstance check work
        inner.__class__ = TaskStatusUpdateEvent  # type: ignore[assignment]

        result_mock = MagicMock()
        result_mock.root.result = inner

        async def mock_stream(request):
            yield result_mock

        client = MagicMock()
        client.send_message_streaming = mock_stream

        cont, ctx, tid = await send_and_stream(client, "hello", "ctx-1")
        assert cont is True

    @pytest.mark.asyncio
    async def test_handles_connect_error(self):
        async def mock_stream(request):
            raise httpx.ConnectError("refused")
            yield  # noqa: E501 — unreachable, needed for async generator

        client = MagicMock()
        client.send_message_streaming = mock_stream

        cont, ctx, tid = await send_and_stream(client, "hello", "ctx-1")
        assert cont is True

    @pytest.mark.asyncio
    async def test_handles_timeout(self):
        async def mock_stream(request):
            raise httpx.TimeoutException("timed out")
            yield  # noqa: E501

        client = MagicMock()
        client.send_message_streaming = mock_stream

        cont, ctx, tid = await send_and_stream(client, "hello", "ctx-1")
        assert cont is True

    @pytest.mark.asyncio
    async def test_handles_jsonrpc_error(self):
        error_response = MagicMock(spec=JSONRPCErrorResponse)
        error_response.error = "something broke"

        result_mock = MagicMock()
        result_mock.root = error_response

        async def mock_stream(request):
            yield result_mock

        client = MagicMock()
        client.send_message_streaming = mock_stream

        cont, ctx, tid = await send_and_stream(client, "hello", "ctx-1")
        assert cont is True

    @pytest.mark.asyncio
    async def test_verbose_mode(self):
        async def mock_stream(request):
            return
            yield  # noqa: E501

        client = MagicMock()
        client.send_message_streaming = mock_stream

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
