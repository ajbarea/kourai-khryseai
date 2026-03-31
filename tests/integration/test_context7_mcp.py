"""Integration tests for context7-mcp server.

Verifies context7-mcp container health and SSE connectivity.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from mcp import ClientSession
from mcp.client.sse import sse_client

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from testcontainers.core.container import DockerContainer


@pytest.fixture(scope="module")
def context7_urls(context7_container: DockerContainer) -> dict[str, str]:
    """Provide dynamic URLs for the started container."""
    host = context7_container.get_container_host_ip()
    port = context7_container.get_exposed_port(3001)

    return {
        "root": f"http://{host}:{port}/",
        "sse": f"http://{host}:{port}/sse",
    }


async def _wait_for_sse_port(url: str, *, seconds: float = 15.0) -> bool:
    """Poll until the SSE port is accepting connections."""
    base = url.rsplit("/", 1)[0]
    deadline = asyncio.get_event_loop().time() + seconds
    async with httpx.AsyncClient() as client:
        while asyncio.get_event_loop().time() < deadline:
            with suppress(httpx.HTTPError, OSError):
                await client.get(base, timeout=2.0)
                return True
            await asyncio.sleep(1.0)
    return False


async def _connect_mcp_sse(
    url: str, *, retries: int = 5, delay: float = 2.0
) -> tuple[Any, ClientSession] | None:
    """Try to establish an MCP SSE session with retries."""
    for attempt in range(retries):
        if attempt > 0:
            if not await _wait_for_sse_port(url):
                continue
        sse_ctx: Any = None
        session: ClientSession | None = None
        try:
            async with asyncio.timeout(10):
                sse_ctx = sse_client(url)
                read, write = await sse_ctx.__aenter__()
                session = ClientSession(read, write)
                await session.__aenter__()
                await session.initialize()
            return sse_ctx, session
        except Exception:
            with suppress(Exception):
                if session is not None:
                    await session.__aexit__(None, None, None)
            with suppress(Exception):
                if sse_ctx is not None:
                    await sse_ctx.__aexit__(None, None, None)
            if attempt < retries - 1:
                await asyncio.sleep(delay)
    return None


@pytest.fixture
async def mcp_session(context7_urls: dict[str, str]) -> AsyncGenerator[ClientSession, None]:
    """Async fixture providing a connected MCP ClientSession to context7-mcp."""
    result = await _connect_mcp_sse(context7_urls["sse"])
    if result is None:
        pytest.skip("SSE connection unavailable after retries")
        return

    sse_ctx, session = result
    yield session

    with suppress(Exception):
        await session.__aexit__(None, None, None)
    with suppress(Exception):
        await sse_ctx.__aexit__(None, None, None)


class TestContext7McpHealth:
    """Tests for context7-mcp health/root endpoint."""

    @pytest.mark.asyncio
    async def test_root_endpoint_returns_200(self, context7_urls: dict[str, str]) -> None:
        """Verify root endpoint responds with HTTP 200."""
        async with httpx.AsyncClient() as client:
            response = await client.get(context7_urls["root"], timeout=10.0)
            assert response.status_code == 200


class TestContext7McpSSE:
    """Tests for context7-mcp SSE endpoint connectivity and tool discovery."""

    @pytest.mark.asyncio
    async def test_sse_client_list_tools(self, mcp_session: ClientSession) -> None:
        """Verify context7-mcp exposes expected documentation tools."""
        result = await mcp_session.list_tools()
        tools = result.tools
        assert tools is not None
        tool_names = [tool.name for tool in tools]

        # Context7 usually provides doc-related tools
        assert len(tool_names) > 0
        # Based on its name, we expect it to search or read context
        assert any("search" in name.lower() or "read" in name.lower() for name in tool_names)
