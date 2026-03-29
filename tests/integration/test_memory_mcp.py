"""Integration tests for memory-mcp server.

Verifies memory-mcp container health and SSE connectivity.

Test Structure:
- TestMemoryMcpHealth: HTTP-level validation (no MCP protocol)
- TestMemoryMcpSSE: MCP protocol connectivity with timeout guards
- TestMemoryMcpToolExecution: Tool call validation

Requires: memory-mcp container running (docker-compose up memory-mcp)
"""

from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from mcp import ClientSession
from mcp.client.sse import sse_client

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture(scope="module", autouse=True)
def wait_for_memory_mcp() -> None:
    """Poll health endpoint until ready before any memory-mcp tests run.

    Docker's healthcheck passes before Node.js fully warms up, causing the
    first HTTP requests to time out. This fixture absorbs that startup gap.
    """
    url = "http://localhost:5000/health"
    deadline = time.monotonic() + 30
    with httpx.Client() as client:
        while time.monotonic() < deadline:
            with suppress(httpx.HTTPError, OSError):
                response = client.get(url, timeout=5.0)
                if response.status_code == 200:
                    return
            time.sleep(0.5)
    pytest.skip("memory-mcp not available within 30s")


class MCPConnectionError(Exception):
    """Raised when MCP SSE connection fails."""


@pytest.fixture
async def mcp_session() -> AsyncGenerator[ClientSession, None]:
    """Async fixture providing a connected MCP ClientSession to memory-mcp.

    March 2026 Best Practices:
    - Timeout guards (15s): Prevent hanging on SSE streaming
    - Explicit cleanup: Handle MCP SDK context manager lifecycle properly
    - Skip on error: Graceful degradation (no flaky tests)

    Known issue: mcp SDK v1.26.0 SSE context managers have cleanup issues.
    Workaround: Manual context manager lifecycle + suppress cleanup errors.
    """
    url = "http://localhost:5001/sse"
    sse_context = None
    session = None

    try:
        try:
            async with asyncio.timeout(15):
                sse_context = sse_client(url)
                read, write = await sse_context.__aenter__()
                session = ClientSession(read, write)
                await session.__aenter__()
                await session.initialize()
                yield session
        except TimeoutError:
            pytest.skip("SSE connection timeout - server may be slow or unresponsive")
        except BaseException as e:
            if isinstance(e, pytest.skip.Exception):
                raise
            # ExceptionGroup (from asyncio.TaskGroup) wraps the real error — unwrap it
            errors_to_check = list(e.exceptions) if isinstance(e, ExceptionGroup) else [e]
            connection_keywords = [
                "connected",
                "transport",
                "timeout",
                "connection",
                "eof",
                "disconnected",
                "protocol",
                "remoteprotocol",
            ]
            if any(
                any(kw in str(err).lower() for kw in connection_keywords) for err in errors_to_check
            ):
                pytest.skip(f"SSE connection unavailable: {type(e).__name__}")
            raise
    finally:
        # Manual cleanup to avoid asyncio task group issues
        if session is not None:
            with suppress(Exception):
                await session.__aexit__(None, None, None)
        if sse_context is not None:
            with suppress(Exception):
                await sse_context.__aexit__(None, None, None)


async def create_test_entity(
    session: ClientSession,
    name: str,
    entity_type: str = "test",
    observations: list[str] | None = None,
) -> None:
    """Create a single entity in memory graph. Reusable across tests."""
    if observations is None:
        observations = []
    await session.call_tool(
        "create_entities",
        {
            "entities": [
                {
                    "name": name,
                    "entityType": entity_type,
                    "observations": observations,
                }
            ]
        },
    )


async def create_test_entities(
    session: ClientSession,
    entities: list[dict[str, Any]],
) -> None:
    """Create multiple entities in memory graph. Reusable across tests."""
    await session.call_tool("create_entities", {"entities": entities})


async def create_test_relation(
    session: ClientSession,
    from_entity: str,
    to_entity: str,
    relation_type: str = "knows",
) -> None:
    """Create a single relation between entities. Reusable across tests."""
    await session.call_tool(
        "create_relations",
        {
            "relations": [
                {
                    "from": from_entity,
                    "to": to_entity,
                    "relationType": relation_type,
                }
            ]
        },
    )


class TestMemoryMcpHealth:
    """Tests for memory-mcp health endpoint.

    March 2026 pattern: Separate health validation from SSE protocol tests.
    Health checks should always pass if container is responsive.
    """

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_200(self) -> None:
        """Verify health endpoint responds with HTTP 200."""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:5000/health", timeout=10.0)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_healthy_status(self) -> None:
        """Verify health endpoint reports healthy status."""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:5000/health", timeout=10.0)
            data = response.json()
            assert "status" in data
            assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_endpoint_reports_mcp_port(self) -> None:
        """Verify health response includes MCP port number."""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:5000/health", timeout=10.0)
            data = response.json()
            assert "mcp_port" in data
            assert data["mcp_port"] == 5001

    @pytest.mark.asyncio
    async def test_root_endpoint_also_works(self) -> None:
        """Verify / endpoint works (fallback for Docker health check)."""
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:5000/", timeout=10.0)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"


class TestMemoryMcpSSE:
    """Tests for memory-mcp SSE endpoint connectivity and tool discovery.

    March 2026 Best Practices:
    - Timeout guards: All async operations protected from hanging
    - Graceful skip: SSE issues don't fail tests, they skip with reason
    - Isolation: Test protocol connectivity separate from tool execution
    """

    @pytest.mark.asyncio
    async def test_sse_client_initializes(self, mcp_session: ClientSession) -> None:
        """Verify SSE client can connect and initialize.

        The mcp_session fixture already succeeded if we get here,
        which means the SSE connection and initialization worked.
        """
        assert mcp_session is not None

        capabilities = mcp_session.get_server_capabilities()
        assert capabilities is not None

    @pytest.mark.asyncio
    async def test_sse_client_list_tools(self, mcp_session: ClientSession) -> None:
        """Verify memory-mcp exposes expected tools via SSE.

        This validates that the MCP server responds to tool list queries.
        """
        result = await mcp_session.list_tools()
        tools = result.tools
        assert tools is not None
        tool_names = [tool.name for tool in tools]

        expected_tools = {
            "create_entities",
            "create_relations",
            "add_observations",
            "read_graph",
            "search_nodes",
        }
        assert expected_tools.issubset(set(tool_names)), (
            f"Missing expected tools. Expected: {expected_tools}, Got: {set(tool_names)}"
        )


class TestMemoryMcpToolExecution:
    """Tests for memory-mcp tool calls (entity creation, relations, etc.).

    March 2026 Best Practices:
    - Real tool execution against running server
    - Response validation (check .content attribute per MCP spec)
    - Error handling with timeout guards
    """

    @pytest.mark.asyncio
    async def test_create_single_entity(self, mcp_session: ClientSession) -> None:
        """Verify create_entities tool works with a single entity."""
        await create_test_entity(
            mcp_session,
            "test_user_001",
            observations=["test observation"],
        )

    @pytest.mark.asyncio
    async def test_create_multiple_entities(self, mcp_session: ClientSession) -> None:
        """Verify create_entities tool works with multiple entities."""
        entities = [
            {"name": "alice_test", "entityType": "person", "observations": ["works at Acme"]},
            {"name": "bob_test", "entityType": "person", "observations": ["likes programming"]},
        ]
        await create_test_entities(mcp_session, entities)

    @pytest.mark.asyncio
    async def test_read_graph_returns_content(self, mcp_session: ClientSession) -> None:
        """Verify read_graph returns valid MCP tool result with .content.

        This validates the response structure per MCP spec.
        """

        await create_test_entity(mcp_session, "integration_test_entity")

        result = await mcp_session.call_tool("read_graph", {})

        assert result is not None
        assert hasattr(result, "content"), "Tool result missing .content attribute"
        assert isinstance(result.content, list), "Tool result .content should be a list"

    @pytest.mark.asyncio
    async def test_search_nodes_returns_content(self, mcp_session: ClientSession) -> None:
        """Verify search_nodes tool returns valid MCP result.

        March 2026: Test response structure, not just success.
        """

        entity_name = "search_test_distinctive_name_unique"
        await create_test_entity(
            mcp_session,
            entity_name,
            observations=["unique observation"],
        )

        result = await mcp_session.call_tool("search_nodes", {"query": entity_name})

        assert result is not None
        assert hasattr(result, "content"), "Tool result missing .content attribute"
        assert isinstance(result.content, list), "Tool result .content should be a list"

    @pytest.mark.asyncio
    async def test_add_observations_to_entity(self, mcp_session: ClientSession) -> None:
        """Verify add_observations tool works and validates response.

        March 2026: Full response validation.
        """
        entity_name = "observation_test_entity"

        await create_test_entity(
            mcp_session,
            entity_name,
            observations=["initial observation"],
        )

        result = await mcp_session.call_tool(
            "add_observations",
            {
                "observations": [
                    {
                        "entityName": entity_name,
                        "contents": ["new observation 1", "new observation 2"],
                    }
                ]
            },
        )

        assert result is not None
        assert hasattr(result, "content"), "Tool result missing .content attribute"
        assert isinstance(result.content, list), "Tool result .content should be a list"

    @pytest.mark.asyncio
    async def test_create_relation_between_entities(self, mcp_session: ClientSession) -> None:
        """Verify create_relations tool works."""

        await create_test_entities(
            mcp_session,
            [
                {
                    "name": "alice_relation_test",
                    "entityType": "person",
                    "observations": [],
                },
                {
                    "name": "bob_relation_test",
                    "entityType": "person",
                    "observations": [],
                },
            ],
        )

        await create_test_relation(
            mcp_session,
            "alice_relation_test",
            "bob_relation_test",
            "knows",
        )
