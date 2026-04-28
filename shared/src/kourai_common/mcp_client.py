"""MCPToolkit — shared infrastructure for agent MCP server integration.

Two layers:

1. **MCPToolkit** — a registry of MCP server names + per-agent assignments,
   used by agents to decide *which* server to talk to (and to fail over
   when one is down). Pure data; no network I/O.

2. **Async MCP client functions** — opens a fresh ``streamable_http_client``
   + ``ClientSession`` per call and wraps each call in an OTEL span so the
   latency shows up in traces. See ``ROADMAP.md`` for why sessions are
   not pooled today (upstream PEP-789-flavoured constraint).

MCP Servers in Kourai Khryseai:
    - Context7: Documentation lookup via context7-mcp sidecar (HTTP Streamable, port 3001)
    - Memory: Player facts via memory-mcp sidecar (HTTP Streamable, port 5001)
    - Shell: pytest, ruff, npx, node (kourai_mcp_shell over stdio)
    - Forge: read_file / write_file / edit_file / delete_file scoped to the
      player's project root via the host-declared ``roots`` capability
      (kourai_mcp_forge over stdio)
    - Brave Search: Web search (direct curl subprocess)
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from kourai_common.tracing import create_span

if TYPE_CHECKING:
    from pathlib import Path

    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
    from mcp import ClientSession
    from mcp.shared.context import RequestContext
    from mcp.shared.message import SessionMessage
    from mcp.types import ListRootsResult

log = logging.getLogger(__name__)

# Active project root for the current request, surfaced to MCP servers via
# `_kourai_list_roots`. Set by the executor / host that already parses
# `[project_root: ...]` from incoming user messages; propagates through
# asyncio task children so any MCP call further down the stack picks it
# up without threading it through every signature.
kourai_project_root_var: ContextVar[Path | None] = ContextVar("kourai_project_root", default=None)

_KOURAI_CLIENT_INFO_NAME = "kourai-khryseai"
_KOURAI_CLIENT_INFO_VERSION = "0.1.0"


class MCPUnavailable(Exception):
    """Raised when a requested MCP server is not available.

    Agents catch this and fall back (e.g., Techne → direct subprocess).
    """


@dataclass
class ServerConfig:
    """Configuration for an MCP server instance."""

    name: str
    enabled: bool = True
    endpoint: str | None = None
    env_vars: dict[str, str] = field(default_factory=dict)
    timeout: int = 30


@dataclass
class AgentMCPAssignment:
    """MCP servers assigned to a specific agent."""

    agent_name: str
    servers: list[str]
    fallback_mode: str = "none"
    """'none' = fail, 'subprocess' = fallback to direct subprocess calls."""


class MCPToolkit:
    """Registry of MCP server configs + per-agent server assignments.

    Pure data; no network calls. Agents use ``get_available_server()`` to
    pick a server, then invoke the async MCP client functions below.
    """

    def __init__(self) -> None:
        self.server_registry: dict[str, ServerConfig] = {}
        self.agent_assignments: dict[str, AgentMCPAssignment] = {}

    def register_server(
        self,
        name: str,
        enabled: bool = True,
        endpoint: str | None = None,
        env_vars: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> None:
        self.server_registry[name] = ServerConfig(
            name=name,
            enabled=enabled,
            endpoint=endpoint,
            env_vars=env_vars or {},
            timeout=timeout,
        )
        log.debug("Registered MCP server: %s (enabled=%s)", name, enabled)

    def assign_servers(
        self,
        agent_name: str,
        servers: list[str],
        fallback_mode: str = "none",
    ) -> None:
        self.agent_assignments[agent_name] = AgentMCPAssignment(
            agent_name=agent_name,
            servers=servers,
            fallback_mode=fallback_mode,
        )
        log.debug("Assigned to %s: %s", agent_name, servers)

    def get_available_server(self, agent_name: str) -> ServerConfig | None:
        """First enabled server for ``agent_name``, else None."""
        assignment = self.agent_assignments.get(agent_name)
        if not assignment:
            log.warning("No MCP servers assigned to %s", agent_name)
            return None

        for server_name in assignment.servers:
            config = self.server_registry.get(server_name)
            if config and config.enabled:
                log.debug("%s using MCP server: %s", agent_name, server_name)
                return config

        log.warning(
            "%s: no available servers from %s. Fallback: %s",
            agent_name,
            assignment.servers,
            assignment.fallback_mode,
        )
        return None

    def is_server_enabled(self, server_name: str) -> bool:
        config = self.server_registry.get(server_name)
        return config is not None and config.enabled

    def disable_server(self, server_name: str) -> None:
        """Mark a server unreachable; callers fail over via ``get_available_server``."""
        if server_name in self.server_registry:
            self.server_registry[server_name].enabled = False
            log.warning("Disabled MCP server: %s", server_name)

    def enable_server(self, server_name: str) -> None:
        if server_name in self.server_registry:
            self.server_registry[server_name].enabled = True
            log.info("Enabled MCP server: %s", server_name)


_toolkit_instance: MCPToolkit | None = None


def get_mcp_toolkit() -> MCPToolkit:
    """Return the singleton toolkit, initialising the default registry on first access."""
    global _toolkit_instance
    if _toolkit_instance is None:
        _toolkit_instance = MCPToolkit()
        _initialize_default_registry(_toolkit_instance)
    return _toolkit_instance


def _initialize_default_registry(toolkit: MCPToolkit) -> None:
    toolkit.register_server("context7", enabled=True)
    toolkit.register_server("context_hub", enabled=True)
    toolkit.register_server("github", enabled=True)
    toolkit.register_server("memory", enabled=True)
    toolkit.register_server("shell", enabled=True)
    toolkit.register_server("brave_search", enabled=True)

    toolkit.assign_servers("hephaestus", ["github"], fallback_mode="none")
    toolkit.assign_servers(
        "metis", ["context7", "context_hub", "github"], fallback_mode="subprocess"
    )
    toolkit.assign_servers(
        "techne",
        ["context7", "context_hub", "github", "shell"],
        fallback_mode="subprocess",
    )
    toolkit.assign_servers("dokimasia", ["shell"], fallback_mode="subprocess")
    toolkit.assign_servers("kallos", ["shell"], fallback_mode="subprocess")
    toolkit.assign_servers("mneme", ["github", "memory"], fallback_mode="none")
    toolkit.assign_servers("puck", ["memory"], fallback_mode="none")
    toolkit.assign_servers("cupid", ["memory"], fallback_mode="none")
    toolkit.assign_servers("aidos", [], fallback_mode="none")
    toolkit.assign_servers("aletheia", ["brave_search"], fallback_mode="none")

    log.info("Initialized default MCP registry with %d servers", len(toolkit.server_registry))


# ── Client-side capability declarations ──────────────────────────────────────
#
# The MCP Python SDK gates capability declaration on callback presence:
# ClientSession.initialize() declares ``roots`` / ``elicitation`` /
# ``sampling`` only when the corresponding callback is non-default
# (mcp/client/session.py:148-188). Default callbacks return ErrorData
# saying "...not supported", so an all-three-with-stubs approach would
# declare capabilities while lying about supporting them. We declare
# only what we actually back: ``roots`` today (real callback below);
# ``elicitation`` will land alongside the INPUT_REQUIRED → elicitation
# migration; ``sampling`` lands when its first caller appears.


async def _kourai_list_roots(
    context: RequestContext[ClientSession, object],
) -> ListRootsResult:
    """Return the active project root as the sole MCP root.

    Reads ``kourai_project_root_var``. When unset, returns an empty
    list — honest "no roots scoped right now," distinct from the SDK
    default's "List roots not supported." When set, returns a single
    Root pointing at the project's ``file://`` URI.
    """
    from mcp.types import FileUrl, ListRootsResult, Root

    root = kourai_project_root_var.get()
    if root is None:
        return ListRootsResult(roots=[])
    return ListRootsResult(roots=[Root(uri=FileUrl(root.as_uri()), name="project_root")])


def build_client_session(
    read: MemoryObjectReceiveStream[SessionMessage | Exception],
    write: MemoryObjectSendStream[SessionMessage],
) -> ClientSession:
    """Construct a ``ClientSession`` with kourai's standard client capabilities.

    Today: declares ``roots`` (via ``_kourai_list_roots`` + the
    ``kourai_project_root_var`` contextvar) and ships ``client_info``
    identifying the host as kourai-khryseai. Elicitation and sampling
    are intentionally NOT wired — see the section comment above for why.
    """
    from mcp import ClientSession
    from mcp.types import Implementation

    return ClientSession(
        read,
        write,
        list_roots_callback=_kourai_list_roots,
        client_info=Implementation(
            name=_KOURAI_CLIENT_INFO_NAME,
            version=_KOURAI_CLIENT_INFO_VERSION,
        ),
    )


# ── Async MCP client functions ───────────────────────────────────────────────
#
# Each function opens a fresh streamable_http_client + ClientSession per call.
# We do NOT pool sessions: the MCP SDK's streamable_http_client yields inside
# an ``anyio.create_task_group()`` cancel scope (PEP 789 pattern), which
# raises ``RuntimeError: Attempted to exit cancel scope in a different task``
# whenever the session is torn down from a different task than it was opened
# in — e.g., the kind of cross-task teardown a session pool would do.
# Observed in Python-SDK issue #466 / #915 / #713. Reconsider when the SDK
# exposes pool-safe primitives.

_MCP_CALL_TIMEOUT = float(os.getenv("MCP_CALL_TIMEOUT", "15"))


async def close_all_mcp_sessions() -> None:
    """Placeholder shutdown hook. Sessions are per-call today so this is a no-op;
    kept stable so hosts can register it unconditionally."""


async def query_context7(library: str, topic: str, tokens: int = 5000) -> str:
    """Query the Context7 MCP sidecar for live documentation.

    Args:
        library: Library name to look up (e.g., "asyncio").
        topic: Specific topic within the library.
        tokens: Max token budget for the documentation response.

    Raises:
        MCPUnavailable: If the sidecar is unreachable or the call fails.
    """
    from mcp.client.streamable_http import streamable_http_client
    from mcp.types import TextContent

    url = os.getenv("CONTEXT7_MCP_URL", "http://context7-mcp:3001/mcp")
    try:
        async with asyncio.timeout(_MCP_CALL_TIMEOUT):
            async with streamable_http_client(url) as (read, write, _):
                async with build_client_session(read, write) as session:
                    await session.initialize()
                    with create_span(
                        "mcp.context7.query",
                        {"mcp.server": "Context7", "mcp.library": library, "mcp.topic": topic},
                    ):
                        lib_result = await session.call_tool(
                            "resolve-library-id", {"libraryName": library}
                        )
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

    Entity shape: ``{"name": str, "entityType": str, "observations": list[str]}``.

    Raises:
        MCPUnavailable: If the sidecar is unreachable or the call fails.
    """
    from mcp.client.streamable_http import streamable_http_client

    url = os.getenv("MEMORY_MCP_URL", "http://memory-mcp:5001/mcp")
    try:
        async with asyncio.timeout(_MCP_CALL_TIMEOUT):
            async with streamable_http_client(url) as (read, write, _):
                async with build_client_session(read, write) as session:
                    await session.initialize()
                    with create_span(
                        "mcp.memory.create_entities",
                        {"mcp.server": "Memory MCP", "mcp.tool": "create_entities"},
                    ):
                        await session.call_tool("create_entities", {"entities": entities})
    except MCPUnavailable:
        raise
    except Exception as e:
        log.warning("Memory MCP unavailable (create_entities): %s", e)
        raise MCPUnavailable(f"Memory MCP: {e}") from e


async def search_memory_nodes(query: str) -> str:
    """Search the Memory MCP knowledge graph for relevant nodes.

    Raises:
        MCPUnavailable: If the sidecar is unreachable or the call fails.
    """
    from mcp.client.streamable_http import streamable_http_client
    from mcp.types import TextContent

    url = os.getenv("MEMORY_MCP_URL", "http://memory-mcp:5001/mcp")
    try:
        async with asyncio.timeout(_MCP_CALL_TIMEOUT):
            async with streamable_http_client(url) as (read, write, _):
                async with build_client_session(read, write) as session:
                    await session.initialize()
                    with create_span(
                        "mcp.memory.search_nodes",
                        {"mcp.server": "Memory MCP", "mcp.tool": "search_nodes"},
                    ):
                        result = await session.call_tool("search_nodes", {"query": query})
                        text_items = [c for c in result.content if isinstance(c, TextContent)]
                        return text_items[0].text if text_items else ""
    except MCPUnavailable:
        raise
    except Exception as e:
        log.warning("Memory MCP unavailable (search_nodes): %s", e)
        raise MCPUnavailable(f"Memory MCP: {e}") from e
