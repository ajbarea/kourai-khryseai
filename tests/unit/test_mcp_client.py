"""Unit tests for MCPToolkit — MCP server registry, agent assignments,
and the async MCP client functions (Context7 + Memory sidecars).

Tests that async functions raise MCPUnavailable on connection
failure, and that the graceful-degradation contract is preserved.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent

from kourai_common.mcp_client import (
    MCPToolkit,
    MCPUnavailable,
    ServerConfig,
    create_memory_entities,
    get_mcp_toolkit,
    query_context7,
    search_memory_nodes,
)


def test_server_config_creation():
    """Test creating a server configuration."""
    config = ServerConfig(
        name="github",
        enabled=True,
        endpoint="https://api.github.com",
        env_vars={"GITHUB_TOKEN": "test_token"},
        timeout=60,
    )
    assert config.name == "github"
    assert config.enabled is True
    assert config.env_vars["GITHUB_TOKEN"] == "test_token"  # noqa: S105
    assert config.timeout == 60


def test_toolkit_register_server():
    """Test registering an MCP server."""
    toolkit = MCPToolkit()
    toolkit.register_server("github", enabled=True, endpoint="https://api.github.com")

    assert "github" in toolkit.server_registry
    config = toolkit.server_registry["github"]
    assert config.enabled is True
    assert config.endpoint == "https://api.github.com"


def test_toolkit_assign_servers():
    """Test assigning servers to an agent."""
    toolkit = MCPToolkit()
    toolkit.assign_servers("techne", ["context7", "github"], fallback_mode="subprocess")

    assert "techne" in toolkit.agent_assignments
    assignment = toolkit.agent_assignments["techne"]
    assert assignment.servers == ["context7", "github"]
    assert assignment.fallback_mode == "subprocess"


def test_get_available_server_first_enabled():
    """Test that get_available_server returns the first enabled server."""
    toolkit = MCPToolkit()
    toolkit.register_server("context7", enabled=True)
    toolkit.register_server("context_hub", enabled=True)
    toolkit.assign_servers("metis", ["context7", "context_hub"])

    server = toolkit.get_available_server("metis")
    assert server is not None
    assert server.name == "context7"


def test_get_available_server_skip_disabled():
    """Test that disabled servers are skipped."""
    toolkit = MCPToolkit()
    toolkit.register_server("context7", enabled=False)
    toolkit.register_server("context_hub", enabled=True)
    toolkit.assign_servers("metis", ["context7", "context_hub"])

    server = toolkit.get_available_server("metis")
    assert server is not None
    assert server.name == "context_hub"


def test_get_available_server_none_available():
    """Test that None is returned when no servers are available."""
    toolkit = MCPToolkit()
    toolkit.register_server("context7", enabled=False)
    toolkit.assign_servers("metis", ["context7"])

    server = toolkit.get_available_server("metis")
    assert server is None


def test_get_available_server_not_assigned():
    """Test that None is returned for agents with no assignments."""
    toolkit = MCPToolkit()

    server = toolkit.get_available_server("unknown_agent")
    assert server is None


def test_get_tool_unavailable():
    """Test that get_tool raises MCPUnavailable when no servers are available."""
    toolkit = MCPToolkit()
    toolkit.register_server("github", enabled=False)
    toolkit.assign_servers("techne", ["github"])

    with pytest.raises(MCPUnavailable):
        toolkit.get_tool("techne", "search_code")


def test_disable_enable_server():
    """Test disabling and re-enabling servers."""
    toolkit = MCPToolkit()
    toolkit.register_server("github", enabled=True)

    toolkit.disable_server("github")
    assert not toolkit.is_server_enabled("github")

    toolkit.enable_server("github")
    assert toolkit.is_server_enabled("github")


def test_is_server_enabled():
    """Test checking if a server is enabled."""
    toolkit = MCPToolkit()
    toolkit.register_server("github", enabled=True)
    toolkit.register_server("gitlab", enabled=False)

    assert toolkit.is_server_enabled("github") is True
    assert toolkit.is_server_enabled("gitlab") is False
    assert toolkit.is_server_enabled("nonexistent") is False


def test_default_registry_initialization():
    """Test that default registry is properly initialized."""
    toolkit = get_mcp_toolkit()

    # Check some servers are registered
    assert toolkit.is_server_enabled("github")
    assert toolkit.is_server_enabled("context7")
    assert toolkit.is_server_enabled("brave_search")

    # Check some assignments exist
    assert "techne" in toolkit.agent_assignments
    assert "mneme" in toolkit.agent_assignments
    assert "aletheia" in toolkit.agent_assignments

    # Verify Techne has context7 first (for documentation lookup)
    techne_servers = toolkit.agent_assignments["techne"].servers
    assert techne_servers[0] == "context7"

    # Verify Aletheia has brave_search
    aletheia_servers = toolkit.agent_assignments["aletheia"].servers
    assert "brave_search" in aletheia_servers


def test_mcp_unavailable_exception():
    """Test MCPUnavailable exception is properly defined."""
    with pytest.raises(MCPUnavailable) as exc_info:
        raise MCPUnavailable("Test error message")

    assert "Test error message" in str(exc_info.value)


# ── Helpers for async context manager mocks ──────────────────────────────────


def _make_session_mock(
    library_id: str = "/python/asyncio",
    docs_text: str = "asyncio gather documentation here",
    search_text: str = "Player entity found",
) -> MagicMock:
    """Build a mock ClientSession with canned call_tool responses."""
    lib_result = MagicMock()
    lib_result.content = [TextContent(type="text", text=library_id)]

    docs_result = MagicMock()
    docs_result.content = [TextContent(type="text", text=docs_text)]

    search_result = MagicMock()
    search_result.content = [TextContent(type="text", text=search_text)]

    create_result = MagicMock()
    create_result.content = [TextContent(type="text", text="ok")]

    session = AsyncMock()
    session.initialize = AsyncMock(return_value=None)
    # query_context7 makes 2 call_tool calls; others make 1
    session.call_tool = AsyncMock(
        side_effect=[lib_result, docs_result, create_result, search_result]
    )
    return session


@asynccontextmanager
async def _mock_sse_client(_url: str):
    """Async context manager that yields dummy (read, write) streams."""
    yield (MagicMock(), MagicMock())


# ── query_context7 (async MCP) ────────────────────────────────────────────────


class TestQueryContext7Async:
    @pytest.mark.asyncio
    async def test_raises_mcp_unavailable_when_sse_fails(self):
        """sse_client connection error is wrapped in MCPUnavailable."""

        def failing_sse(_url: str):
            raise ConnectionRefusedError("connection refused")

        with (
            patch("mcp.client.sse.sse_client", failing_sse),
            pytest.raises(MCPUnavailable, match="Context7"),
        ):
            await query_context7("asyncio", "gather")

    @pytest.mark.asyncio
    async def test_raises_mcp_unavailable_on_timeout(self):
        """asyncio.timeout expiry is wrapped in MCPUnavailable."""

        def timeout_sse(_url: str):
            raise TimeoutError()

        with patch("mcp.client.sse.sse_client", timeout_sse), pytest.raises(MCPUnavailable):
            await query_context7("asyncio", "gather")

    @pytest.mark.asyncio
    async def test_raises_mcp_unavailable_preserves_context7_prefix(self):
        """MCPUnavailable message starts with 'Context7:' for easier debugging."""

        def failing_sse(_url: str):
            raise OSError("ECONNREFUSED")

        with (
            patch("mcp.client.sse.sse_client", failing_sse),
            pytest.raises(MCPUnavailable) as exc_info,
        ):
            await query_context7("react", "hooks")

        assert "Context7" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_mcp_unavailable_when_library_not_resolved(self):
        """Empty library_id from sidecar raises MCPUnavailable (library not found)."""
        session = AsyncMock()
        session.initialize = AsyncMock(return_value=None)
        empty_result = MagicMock()
        empty_result.content = [TextContent(type="text", text="")]
        session.call_tool = AsyncMock(return_value=empty_result)

        @asynccontextmanager
        async def mock_client_session(_read: object, _write: object):
            yield session

        with (
            patch("mcp.client.sse.sse_client", _mock_sse_client),
            patch("mcp.ClientSession", mock_client_session),
            pytest.raises(MCPUnavailable, match="resolve library"),
        ):
            await query_context7("nonexistent_lib_xyz", "docs")

    @pytest.mark.asyncio
    async def test_returns_docs_text_on_success(self):
        """Returns the documentation text string when the full round-trip succeeds."""
        expected_docs = "asyncio.gather() runs awaitables concurrently."
        session = _make_session_mock(docs_text=expected_docs)

        @asynccontextmanager
        async def mock_client_session(_read: object, _write: object):
            yield session

        with (
            patch("mcp.client.sse.sse_client", _mock_sse_client),
            patch("mcp.ClientSession", mock_client_session),
        ):
            result = await query_context7("asyncio", "gather")

        assert result == expected_docs

    @pytest.mark.asyncio
    async def test_uses_env_var_url(self, monkeypatch: pytest.MonkeyPatch):
        """Passes CONTEXT7_MCP_URL env var to sse_client."""
        monkeypatch.setenv("CONTEXT7_MCP_URL", "http://custom-host:9999/sse")
        captured_url: list[str] = []

        @asynccontextmanager
        async def capturing_sse(url: str):
            captured_url.append(url)
            yield (MagicMock(), MagicMock())

        session = _make_session_mock()

        @asynccontextmanager
        async def mock_client_session(_read: object, _write: object):
            yield session

        with (
            patch("mcp.client.sse.sse_client", capturing_sse),
            patch("mcp.ClientSession", mock_client_session),
        ):
            await query_context7("asyncio", "gather")

        assert captured_url[0] == "http://custom-host:9999/sse"


# ── create_memory_entities (async MCP) ───────────────────────────────────────


class TestCreateMemoryEntitiesAsync:
    @pytest.mark.asyncio
    async def test_raises_mcp_unavailable_when_sse_fails(self):
        """Connection error is wrapped in MCPUnavailable."""

        def failing_sse(_url: str):
            raise ConnectionRefusedError("memory-mcp not running")

        with (
            patch("mcp.client.sse.sse_client", failing_sse),
            pytest.raises(MCPUnavailable, match="Memory MCP"),
        ):
            await create_memory_entities(
                [{"name": "Player1", "entityType": "Player", "observations": ["loves Python"]}]
            )

    @pytest.mark.asyncio
    async def test_calls_create_entities_tool(self):
        """Calls the 'create_entities' tool with the provided entity list."""
        session = AsyncMock()
        session.initialize = AsyncMock(return_value=None)
        session.call_tool = AsyncMock(return_value=MagicMock(content=[]))

        @asynccontextmanager
        async def mock_client_session(_read: object, _write: object):
            yield session

        entities = [
            {"name": "Player1", "entityType": "Player", "observations": ["prefers dark mode"]}
        ]

        with (
            patch("mcp.client.sse.sse_client", _mock_sse_client),
            patch("mcp.ClientSession", mock_client_session),
        ):
            await create_memory_entities(entities)

        session.call_tool.assert_called_once_with("create_entities", {"entities": entities})

    @pytest.mark.asyncio
    async def test_uses_memory_mcp_sse_url_env_var(self, monkeypatch: pytest.MonkeyPatch):
        """Uses MEMORY_MCP_SSE_URL env var for the connection endpoint."""
        monkeypatch.setenv("MEMORY_MCP_SSE_URL", "http://custom-memory:6000/sse")
        captured_url: list[str] = []

        @asynccontextmanager
        async def capturing_sse(url: str):
            captured_url.append(url)
            yield (MagicMock(), MagicMock())

        session = AsyncMock()
        session.initialize = AsyncMock(return_value=None)
        session.call_tool = AsyncMock(return_value=MagicMock(content=[]))

        @asynccontextmanager
        async def mock_client_session(_read: object, _write: object):
            yield session

        with (
            patch("mcp.client.sse.sse_client", capturing_sse),
            patch("mcp.ClientSession", mock_client_session),
        ):
            await create_memory_entities(
                [{"name": "P", "entityType": "Player", "observations": []}]
            )

        assert captured_url[0] == "http://custom-memory:6000/sse"


# ── search_memory_nodes (async MCP) ──────────────────────────────────────────


class TestSearchMemoryNodesAsync:
    @pytest.mark.asyncio
    async def test_raises_mcp_unavailable_when_sse_fails(self):
        """Connection error is wrapped in MCPUnavailable."""

        def failing_sse(_url: str):
            raise ConnectionRefusedError("memory-mcp not running")

        with (
            patch("mcp.client.sse.sse_client", failing_sse),
            pytest.raises(MCPUnavailable, match="Memory MCP"),
        ):
            await search_memory_nodes("Player1")

    @pytest.mark.asyncio
    async def test_returns_search_result_text(self):
        """Returns the content text from the search_nodes tool response."""
        expected_text = "Player1: prefers dark mode, uses Python"
        session = AsyncMock()
        session.initialize = AsyncMock(return_value=None)
        result = MagicMock()
        result.content = [TextContent(type="text", text=expected_text)]
        session.call_tool = AsyncMock(return_value=result)

        @asynccontextmanager
        async def mock_client_session(_read: object, _write: object):
            yield session

        with (
            patch("mcp.client.sse.sse_client", _mock_sse_client),
            patch("mcp.ClientSession", mock_client_session),
        ):
            text = await search_memory_nodes("Player1")

        assert text == expected_text

    @pytest.mark.asyncio
    async def test_returns_empty_string_when_no_content(self):
        """Returns '' when the tool response has no content."""
        session = AsyncMock()
        session.initialize = AsyncMock(return_value=None)
        result = MagicMock()
        result.content = []
        session.call_tool = AsyncMock(return_value=result)

        @asynccontextmanager
        async def mock_client_session(_read: object, _write: object):
            yield session

        with (
            patch("mcp.client.sse.sse_client", _mock_sse_client),
            patch("mcp.ClientSession", mock_client_session),
        ):
            text = await search_memory_nodes("Player1")

        assert text == ""

    @pytest.mark.asyncio
    async def test_calls_search_nodes_tool(self):
        """Verifies the tool name and query arg passed to the MCP session."""
        session = AsyncMock()
        session.initialize = AsyncMock(return_value=None)
        result = MagicMock()
        result.content = [MagicMock(text="result")]
        session.call_tool = AsyncMock(return_value=result)

        @asynccontextmanager
        async def mock_client_session(_read: object, _write: object):
            yield session

        with (
            patch("mcp.client.sse.sse_client", _mock_sse_client),
            patch("mcp.ClientSession", mock_client_session),
        ):
            await search_memory_nodes("dark mode preference")

        session.call_tool.assert_called_once_with("search_nodes", {"query": "dark mode preference"})
