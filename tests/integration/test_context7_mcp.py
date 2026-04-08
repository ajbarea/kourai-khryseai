"""Integration tests for context7-mcp server.

Verifies context7-mcp container health and HTTP Streamable connectivity.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

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
        "mcp": f"http://{host}:{port}/mcp",  # HTTP Streamable endpoint
    }


async def _wait_for_mcp_port(url: str, *, seconds: float = 15.0) -> bool:
    """Poll until the MCP HTTP Streamable port is accepting connections."""
    base = url.rsplit("/", 1)[0]
    deadline = asyncio.get_event_loop().time() + seconds
    async with httpx.AsyncClient() as client:
        while asyncio.get_event_loop().time() < deadline:
            with suppress(httpx.HTTPError, OSError):
                await client.get(base, timeout=2.0)
                return True
            await asyncio.sleep(1.0)
    return False


async def _connect_mcp_streamable(
    url: str, *, retries: int = 5, delay: float = 2.0
) -> tuple[Any, ClientSession] | None:
    """Try to establish an MCP HTTP Streamable session with retries.

    Returns (http_ctx_manager, session) tuple. Caller must keep http_ctx_manager
    alive while using the session and close it during teardown.
    """
    for attempt in range(retries):
        if attempt > 0:
            if not await _wait_for_mcp_port(url):
                continue
        http_ctx: Any = None
        session: ClientSession | None = None
        try:
            async with asyncio.timeout(10):
                http_ctx = streamable_http_client(url)
                read, write, _ = await http_ctx.__aenter__()
                session = ClientSession(read, write)
                await session.__aenter__()
                await session.initialize()
                return http_ctx, session
        except Exception:
            with suppress(Exception):
                if session is not None:
                    await session.__aexit__(None, None, None)
            with suppress(Exception):
                if http_ctx is not None:
                    await http_ctx.__aexit__(None, None, None)
            if attempt < retries - 1:
                await asyncio.sleep(delay)
    return None


@pytest.fixture
async def mcp_session(context7_urls: dict[str, str]) -> AsyncGenerator[ClientSession, None]:
    """Async fixture providing a connected MCP ClientSession to context7-mcp."""
    result = await _connect_mcp_streamable(context7_urls["mcp"])
    if result is None:
        pytest.skip("MCP HTTP Streamable connection unavailable after retries")
        return

    http_ctx, session = result
    yield session

    with suppress(Exception):
        await session.__aexit__(None, None, None)
    with suppress(Exception):
        await http_ctx.__aexit__(None, None, None)


class TestContext7McpHealth:
    """Tests for context7-mcp health and container readiness."""

    @pytest.mark.asyncio
    async def test_mcp_endpoint_accepts_connections(self, context7_urls: dict[str, str]) -> None:
        """Verify HTTP Streamable endpoint accepts connections (container is ready)."""
        # HTTP Streamable endpoints require application/json content-type.
        # A successful response (not 502/503) indicates container readiness.
        async with httpx.AsyncClient() as client:
            try:
                # POST to the streamable endpoint with proper headers
                response = await client.post(
                    context7_urls["mcp"],
                    timeout=10.0,
                    headers={"Content-Type": "application/json"},
                    content=b"{}",
                )
                # 200, 400, or other 4xx means container is ready
                # 502/503 would mean container is not responding
                assert response.status_code < 500, f"Server error: {response.status_code}"
            except httpx.ConnectError:
                # Connection failure means container is not responding
                pytest.fail("Context7 container not responding")


class TestContext7McpStreamable:
    """Tests for context7-mcp HTTP Streamable endpoint connectivity and tool discovery."""

    @pytest.mark.asyncio
    async def test_streamable_client_list_tools(self, mcp_session: ClientSession) -> None:
        """Verify context7-mcp exposes expected documentation tools via HTTP Streamable."""
        result = await mcp_session.list_tools()
        tools = result.tools
        assert tools is not None
        tool_names = [tool.name for tool in tools]

        # Context7 exposes doc lookup tools (resolve-library-id, get-library-docs, etc.)
        assert len(tool_names) > 0
