"""RemoteAgentConnection: connect, send, extract, close."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from a2a.types import TaskState

from agents.hephaestus.remote_connections import (
    AgentInputRequired,
    RemoteAgentConnection,
)


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

        with (
            patch("agents.hephaestus.remote_connections.create_span"),
            patch(
                "agents.hephaestus.remote_connections.A2ACardResolver",
                return_value=mock_resolver,
            ),
            patch("agents.hephaestus.remote_connections.A2AClient") as mock_client_cls,
        ):
            conn = RemoteAgentConnection("metis", "http://localhost:10001/")
            await conn.connect()

        assert conn.card == mock_card
        mock_client_cls.assert_called_once()

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


class TestRemoteAgentConnectionSend:
    """Message sending and response extraction."""

    @pytest.mark.asyncio
    async def test_send_raises_if_not_connected(self):
        conn = RemoteAgentConnection("metis", "http://localhost:10001/")
        with pytest.raises(RuntimeError, match="Not connected"):
            await conn.send.__wrapped__(conn, "hello", "ctx-1")

    @pytest.mark.asyncio
    async def test_send_extracts_artifact_text(self):
        # Build mock response with artifacts
        mock_part = MagicMock()
        mock_part.root.text = "generated code"
        mock_artifact = MagicMock()
        mock_artifact.parts = [mock_part]
        mock_result = MagicMock()
        mock_result.artifacts = [mock_artifact]
        mock_result.status = MagicMock()
        mock_result.status.state = TaskState.completed
        mock_response = MagicMock()
        mock_response.root.result = mock_result

        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value=mock_response)

        with (
            patch("agents.hephaestus.remote_connections.create_span"),
            patch("agents.hephaestus.remote_connections.get_trace_context", return_value={}),
        ):
            conn = RemoteAgentConnection("techne", "http://localhost:10002/")
            conn.client = mock_client
            result = await conn.send.__wrapped__(conn, "fix auth", "ctx-1")

        assert result == "generated code"

    @pytest.mark.asyncio
    async def test_send_raises_input_required(self):
        mock_part = MagicMock()
        mock_part.root.text = "Which file?"
        mock_status = MagicMock()
        mock_status.state = TaskState.input_required
        mock_status.message.parts = [mock_part]
        mock_result = MagicMock()
        mock_result.status = mock_status
        mock_result.artifacts = None
        mock_response = MagicMock()
        mock_response.root.result = mock_result

        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(return_value=mock_response)

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
        await conn.close()
        conn.http.aclose.assert_called_once()


class TestExtractText:
    """The _extract_text fallback paths."""

    def test_fallback_to_status_message(self):
        # Response with no artifacts, but status message
        mock_part = MagicMock()
        mock_part.root.text = "status text"
        mock_status = MagicMock()
        mock_status.state = TaskState.completed
        mock_status.message.parts = [mock_part]
        mock_result = MagicMock()
        mock_result.artifacts = None
        mock_result.status = mock_status
        mock_response = MagicMock()
        mock_response.root.result = mock_result

        conn = RemoteAgentConnection("kallos", "http://localhost:10004/")
        result = conn._extract_text(mock_response)
        assert result == "status text"

    def test_fallback_to_str_on_attribute_error(self):
        mock_response = MagicMock()
        mock_response.root.result = None  # Will cause AttributeError

        conn = RemoteAgentConnection("kallos", "http://localhost:10004/")
        result = conn._extract_text(mock_response)
        assert isinstance(result, str)
