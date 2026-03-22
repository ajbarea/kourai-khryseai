"""MCPToolkit — shared infrastructure for agent MCP server integration.

Centralizes MCP client lifecycle, server registry, per-agent tool assignments,
and the real async MCP client functions for Context7 and Memory sidecars.

MCP Servers in Kourai Khryseai:
- Context7: Documentation lookup via context7-mcp sidecar (SSE on port 3001)
- Memory: Player facts, relationship persistence via memory-mcp sidecar (SSE on port 5001)
- GitHub: Issue/PR/repo operations (direct PyGithub)
- Shell: pytest, ruff, npx, node (direct subprocess)
- Playwright: Frontend E2E testing (direct subprocess)
- Brave Search: Web search (direct curl subprocess)
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


class MCPUnavailable(Exception):
    """Raised when a requested MCP server is not available.

    Agents should catch this and provide a graceful fallback
    (e.g., Techne falls back to direct subprocess calls).
    """


@dataclass
class ServerConfig:
    """Configuration for an MCP server instance."""

    name: str
    """Server name (e.g., 'github', 'context7', 'memory')."""

    enabled: bool = True
    """Whether this server is available/connected."""

    endpoint: str | None = None
    """Optional custom endpoint URL or socket path."""

    env_vars: dict[str, str] = field(default_factory=dict)
    """Environment variables required by the server (e.g., API keys)."""

    timeout: int = 30
    """Default timeout for operations (seconds)."""


@dataclass
class AgentMCPAssignment:
    """MCP servers assigned to a specific agent."""

    agent_name: str
    """Agent name (e.g., 'techne', 'metis')."""

    servers: list[str]
    """Ordered list of server names. First available is used."""

    fallback_mode: str = "none"
    """'none' = fail, 'subprocess' = fallback to direct subprocess calls."""


class MCPToolkit:
    """Centralizes MCP client lifecycle and per-agent server assignments.

    Attributes:
        server_registry: {server_name: ServerConfig} mapping.
        agent_assignments: {agent_name: AgentMCPAssignment} mapping.
    """

    def __init__(self) -> None:
        """Initialize empty toolkit. Populate via register_server() and assign_servers()."""
        self.server_registry: dict[str, ServerConfig] = {}
        self.agent_assignments: dict[str, AgentMCPAssignment] = {}
        self._client_pool: dict[str, Any] = {}  # In-memory client instances

    def register_server(
        self,
        name: str,
        enabled: bool = True,
        endpoint: str | None = None,
        env_vars: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> None:
        """Register an MCP server in the registry.

        Args:
            name: Server identifier (e.g., 'github', 'context7').
            enabled: Whether server is available.
            endpoint: Custom endpoint (socket, URL, etc.).
            env_vars: Environment variables (API keys, etc.).
            timeout: Default operation timeout in seconds.
        """
        self.server_registry[name] = ServerConfig(
            name=name,
            enabled=enabled,
            endpoint=endpoint,
            env_vars=env_vars or {},
            timeout=timeout,
        )
        log.debug(f"Registered MCP server: {name} (enabled={enabled})")

    def assign_servers(
        self,
        agent_name: str,
        servers: list[str],
        fallback_mode: str = "none",
    ) -> None:
        """Assign MCP servers to an agent.

        Args:
            agent_name: Agent identifier (e.g., 'techne').
            servers: Ordered list of server names to try.
            fallback_mode: 'none' (fail), 'subprocess' (fallback), or custom.
        """
        self.agent_assignments[agent_name] = AgentMCPAssignment(
            agent_name=agent_name,
            servers=servers,
            fallback_mode=fallback_mode,
        )
        log.debug(f"Assigned to {agent_name}: {servers}")

    def get_available_server(self, agent_name: str) -> ServerConfig | None:
        """Get the first available MCP server for an agent.

        Returns first server in the agent's assignment list that is enabled.
        Returns None if no servers are assigned or all are disabled.

        Args:
            agent_name: Agent identifier.

        Returns:
            ServerConfig of the first available server, or None.
        """
        assignment = self.agent_assignments.get(agent_name)
        if not assignment:
            log.warning(f"No MCP servers assigned to {agent_name}")
            return None

        for server_name in assignment.servers:
            config = self.server_registry.get(server_name)
            if config and config.enabled:
                log.debug(f"{agent_name} using MCP server: {server_name}")
                return config

        log.warning(
            f"{agent_name}: no available servers from {assignment.servers}. "
            f"Fallback mode: {assignment.fallback_mode}"
        )
        return None

    def get_tool(
        self,
        agent_name: str,
        tool_name: str,
    ) -> Any:
        """Get a tool/method from the assigned MCP server for an agent.

        Returns a callable wrapper that uses the appropriate server backend.
        Raises MCPUnavailable if no server is available.

        Args:
            agent_name: Agent identifier.
            tool_name: Tool/method name (e.g., 'search_github_code').

        Returns:
            Callable tool from the MCP server.

        Raises:
            MCPUnavailable: If no server is available.
        """
        server = self.get_available_server(agent_name)
        if not server:
            raise MCPUnavailable(f"No MCP server available for {agent_name}")

        # Tool factory: return appropriate wrapper based on server + tool
        # Agents will import and use these directly; this toolkit just validates availability
        log.debug(f"{agent_name}: requesting tool '{tool_name}' from {server.name}")

        # For now, return a stub that agents can detect (they have real implementations)
        # Real MCP client SDK integration happens in Phase E upgrade
        class ToolStub:
            def __init__(self, tool_name: str, server_name: str) -> None:
                self.tool_name = tool_name
                self.server_name = server_name

            def __call__(self, *args: Any, **kwargs: Any) -> Any:
                raise MCPUnavailable(
                    f"Tool '{self.tool_name}' on server '{self.server_name}' "
                    f"requires full MCP SDK integration (Phase E+). "
                    f"Agent should use fallback implementation."
                )

        return ToolStub(tool_name, server.name)

    def is_server_enabled(self, server_name: str) -> bool:
        """Check if a server is enabled.

        Args:
            server_name: Server identifier.

        Returns:
            True if server is registered and enabled.
        """
        config = self.server_registry.get(server_name)
        return config is not None and config.enabled

    def disable_server(self, server_name: str) -> None:
        """Disable a server (e.g., rate-limited, unreachable).

        Agents will fall back to the next available server in their assignment.

        Args:
            server_name: Server identifier.
        """
        if server_name in self.server_registry:
            self.server_registry[server_name].enabled = False
            log.warning(f"Disabled MCP server: {server_name}")

    def enable_server(self, server_name: str) -> None:
        """Re-enable a disabled server.

        Args:
            server_name: Server identifier.
        """
        if server_name in self.server_registry:
            self.server_registry[server_name].enabled = True
            log.info(f"Enabled MCP server: {server_name}")


# Global toolkit instance (singleton pattern)
_toolkit_instance: MCPToolkit | None = None


def get_mcp_toolkit() -> MCPToolkit:
    """Get or create the global MCP toolkit instance.

    Returns:
        The singleton MCPToolkit.
    """
    global _toolkit_instance
    if _toolkit_instance is None:
        _toolkit_instance = MCPToolkit()
        _initialize_default_registry(_toolkit_instance)
    return _toolkit_instance


def _initialize_default_registry(toolkit: MCPToolkit) -> None:
    """Initialize default MCP server registry and agent assignments.

    Follows assignments from MARCH_20.md MCP target assignment matrix.
    """
    # Register known servers (all free, all optional for Phase B+)
    toolkit.register_server("context7", enabled=True)
    toolkit.register_server("context_hub", enabled=True)
    toolkit.register_server("github", enabled=True)
    toolkit.register_server("memory", enabled=True)
    toolkit.register_server("shell", enabled=True)
    toolkit.register_server("playwright", enabled=False)  # Phase E
    toolkit.register_server("brave_search", enabled=True)
    toolkit.register_server("dbhub", enabled=False)  # Phase E

    # Assign servers to agents (from MARCH_20.md)
    toolkit.assign_servers("hephaestus", ["github"], fallback_mode="none")
    toolkit.assign_servers(
        "metis", ["context7", "context_hub", "github"], fallback_mode="subprocess"
    )
    toolkit.assign_servers(
        "techne",
        ["context7", "context_hub", "github", "shell"],
        fallback_mode="subprocess",
    )
    toolkit.assign_servers("dokimasia", ["shell", "playwright"], fallback_mode="subprocess")
    toolkit.assign_servers("kallos", ["shell"], fallback_mode="subprocess")
    toolkit.assign_servers("mneme", ["github", "memory"], fallback_mode="none")
    toolkit.assign_servers("puck", ["memory"], fallback_mode="none")
    toolkit.assign_servers("cupid", ["memory"], fallback_mode="none")
    # Aidos: no MCP servers (pure LLM + regex)
    toolkit.assign_servers("aidos", [], fallback_mode="none")
    toolkit.assign_servers("aletheia", ["brave_search"], fallback_mode="none")

    log.info("Initialized default MCP registry with %d servers", len(toolkit.server_registry))


# ── Real async MCP client functions ──────────────────────────────────────────
#
# Context7 and Memory sidecars expose SSE endpoints via supergateway.
# Agents import these directly; all failures raise MCPUnavailable.
# Callers should catch MCPUnavailable and fall back gracefully.

_MCP_CALL_TIMEOUT = 15.0  # seconds


async def query_context7(library: str, topic: str, tokens: int = 5000) -> str:
    """Query the Context7 MCP sidecar for live documentation.

    Connects to the context7-mcp Docker service (SSE transport, port 3001).
    Resolves the library ID then fetches documentation for the given topic.

    Args:
        library: Library name to look up (e.g., "asyncio", "react", "fastapi").
        topic: Specific topic within the library (e.g., "async context managers").
        tokens: Max token budget for the documentation response.

    Returns:
        Documentation text suitable for prompt injection.

    Raises:
        MCPUnavailable: If the context7-mcp sidecar is unreachable or the call fails.
    """
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    url = os.getenv("CONTEXT7_MCP_URL", "http://context7-mcp:3001/sse")
    try:
        async with asyncio.timeout(_MCP_CALL_TIMEOUT):
            async with sse_client(url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    lib_result = await session.call_tool(
                        "resolve-library-id", {"libraryName": library}
                    )
                    from mcp.types import TextContent

                    text_items = [c for c in lib_result.content if isinstance(c, TextContent)]
                    library_id = text_items[0].text.strip() if text_items else ""
                    if not library_id:
                        raise MCPUnavailable(f"Context7 could not resolve library: {library}")
                    docs_result = await session.call_tool(
                        "get-library-docs",
                        {
                            "context7CompatibleLibraryID": library_id,
                            "topic": topic,
                            "tokens": tokens,
                        },
                    )
                    text_items = [c for c in docs_result.content if isinstance(c, TextContent)]
                    return text_items[0].text if text_items else ""
    except MCPUnavailable:
        raise
    except Exception as e:
        log.warning("Context7 MCP unavailable: %s", e)
        raise MCPUnavailable(f"Context7: {e}") from e


async def create_memory_entities(entities: list[dict]) -> None:
    """Store entities in the shared Memory MCP knowledge graph.

    Connects to the memory-mcp Docker service (SSE transport, port 5001).
    Entity format: {"name": str, "entityType": str, "observations": list[str]}.

    Args:
        entities: List of entity dicts to create/update in the graph.

    Raises:
        MCPUnavailable: If the memory-mcp sidecar is unreachable or the call fails.
    """
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    url = os.getenv("MEMORY_MCP_SSE_URL", "http://memory-mcp:5001/sse")
    try:
        async with asyncio.timeout(_MCP_CALL_TIMEOUT):
            async with sse_client(url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    await session.call_tool("create_entities", {"entities": entities})
    except MCPUnavailable:
        raise
    except Exception as e:
        log.warning("Memory MCP unavailable (create_entities): %s", e)
        raise MCPUnavailable(f"Memory MCP: {e}") from e


async def search_memory_nodes(query: str) -> str:
    """Search the Memory MCP knowledge graph for relevant nodes.

    Connects to the memory-mcp Docker service (SSE transport, port 5001).

    Args:
        query: Search string to find relevant entities/observations.

    Returns:
        Search results as text, or empty string if no matches.

    Raises:
        MCPUnavailable: If the memory-mcp sidecar is unreachable or the call fails.
    """
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    url = os.getenv("MEMORY_MCP_SSE_URL", "http://memory-mcp:5001/sse")
    try:
        async with asyncio.timeout(_MCP_CALL_TIMEOUT):
            async with sse_client(url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool("search_nodes", {"query": query})
                    from mcp.types import TextContent

                    text_items = [c for c in result.content if isinstance(c, TextContent)]
                    return text_items[0].text if text_items else ""
    except MCPUnavailable:
        raise
    except Exception as e:
        log.warning("Memory MCP unavailable (search_nodes): %s", e)
        raise MCPUnavailable(f"Memory MCP: {e}") from e
