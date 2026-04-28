"""Bridges an MCP ``ClientSession`` to the ``chat_with_tools`` interface.

``chat_with_tools`` (``kourai_common.llm``) accepts ``tools: list[dict]``
in OpenAI tool-use shape plus ``tool_handlers: dict[str, Callable]``. The
in-process forge today supplies these from
``kourai_common.forge_tools.FORGE_TOOL_SCHEMAS`` /
``FORGE_TOOL_HANDLERS``. M2 Change 3 swaps that for an MCP-driven path:
launch ``kourai-mcp-forge`` as a stdio subprocess, fetch ``tools/list``,
and route each tool call through ``session.call_tool``.

This module is purely additive — Change 3a establishes the bridge and
its tests; specialist migration (Techne / Kallos / Dokimasia) lands in
follow-on PRs that flip the in-process path to call this bridge.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from kourai_common.mcp_client import build_client_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters
    from mcp.types import Tool

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MCPToolBridge:
    """Tool list + handlers shaped for ``chat_with_tools``, backed by an MCP session.

    ``tools`` are OpenAI-style schema dicts (``{"type": "function",
    "function": {...}}``) consumable directly by LiteLLM. Each entry in
    ``tool_handlers`` proxies to ``session.call_tool(name, args)`` and
    returns the text content of the result.
    """

    tools: list[dict[str, Any]]
    tool_handlers: dict[str, Callable[..., Awaitable[str]]]


def mcp_tool_to_openai_schema(tool: Tool) -> dict[str, Any]:
    """Convert an MCP ``Tool`` (name + description + JSON Schema input) into
    the OpenAI tool-use shape that LiteLLM / ``chat_with_tools`` expects.
    """
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }


def _extract_text(content: list[Any]) -> str:
    """Extract the concatenated text from a ``CallToolResult.content`` list.

    MCP content items can be ``TextContent``, ``ImageContent``, or
    ``EmbeddedResource``. The forge tools today return only text, so we
    pull ``.text`` from each text-typed item and join with newlines.
    Non-text items are ignored at this layer (they'd need a richer
    handler shape than ``-> str`` to surface anyway).
    """
    parts: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts)


def _make_mcp_tool_handler(
    session: ClientSession,
    tool_name: str,
) -> Callable[..., Awaitable[str]]:
    """Build an async handler that proxies kwargs through to
    ``session.call_tool(tool_name, kwargs)`` and returns the extracted text.

    Server-side errors come back as ``CallToolResult(isError=True, ...)``;
    the handler surfaces the error text verbatim so the existing tool-loop
    error path (which inspects ``"ERROR:"`` prefixes) keeps working — the
    forge server already prefixes its error returns with ``"ERROR: ..."``
    for this exact reason.
    """

    async def handler(**kwargs: Any) -> str:
        result = await session.call_tool(tool_name, kwargs)
        text = _extract_text(result.content)
        if result.isError and not text.startswith("ERROR:"):
            return f"ERROR: {text}" if text else "ERROR: tool call failed"
        return text

    return handler


@asynccontextmanager
async def mcp_tool_bridge(
    server_params: StdioServerParameters,
) -> AsyncIterator[MCPToolBridge]:
    """Launch an MCP server via stdio, open a kourai client session,
    fetch ``tools/list``, and yield an ``MCPToolBridge``.

    The session declares ``roots`` via ``build_client_session`` (M2
    Change 1), so a forge-style server can scope its file ops to the
    player's project root via ``ctx.session.list_roots()``. Set
    ``kourai_project_root_var`` before entering this context manager
    (specialist executors do this in `parse_project_root` follow-on).
    """
    from mcp.client.stdio import stdio_client

    async with (
        stdio_client(server_params) as (read, write),
        build_client_session(read, write) as session,
    ):
        await session.initialize()
        tools_result = await session.list_tools()
        tools = [mcp_tool_to_openai_schema(t) for t in tools_result.tools]
        tool_handlers = {
            t.name: _make_mcp_tool_handler(session, t.name) for t in tools_result.tools
        }
        log.info(
            "MCP bridge ready: %d tools (%s)",
            len(tools),
            ", ".join(t.name for t in tools_result.tools),
        )
        yield MCPToolBridge(tools=tools, tool_handlers=tool_handlers)


_FORGE_INHERITED_ENV_PREFIXES: tuple[str, ...] = ("OTEL_",)
_FORGE_INHERITED_ENV_KEYS: tuple[str, ...] = (
    "ENVIRONMENT",
    "SERVICE_VERSION",
    "KOURAI_LOG_LEVEL",
)


def _forge_subprocess_env() -> dict[str, str]:
    """Build the env dict the bridge passes to ``StdioServerParameters``.

    `mcp.client.stdio` deliberately ships a tiny safe-list
    (``DEFAULT_INHERITED_ENV_VARS`` = HOME/LOGNAME/PATH/SHELL/TERM/USER on
    Linux) so a subprocess can't accidentally leak the parent's secrets.
    That excludes the OTel exporter config — without it the forge
    subprocess's spans fall back to the SDK default
    ``http://localhost:4318`` and never reach Jaeger (verified live —
    spans showed "connection refused" against localhost from inside the
    agent container even though the parent had ``OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318``).

    We add OTel-relevant vars explicitly. Also kourai-specific ones the
    forge process honors (`KOURAI_LOG_LEVEL` for log verbosity).
    """
    import os

    from mcp.client.stdio import get_default_environment

    env = get_default_environment()
    for key, val in os.environ.items():
        if (
            any(key.startswith(prefix) for prefix in _FORGE_INHERITED_ENV_PREFIXES)
            or key in _FORGE_INHERITED_ENV_KEYS
        ):
            env[key] = val
    return env


@asynccontextmanager
async def forge_tool_bridge() -> AsyncIterator[MCPToolBridge]:
    """Convenience wrapper: open an ``mcp_tool_bridge`` for kourai-mcp-forge.

    Launches ``<sys.executable> -m kourai_mcp_forge`` as a stdio
    subprocess — the same Python interpreter that's running the bridge
    spawns the forge server. This works both on the dev host (where
    ``sys.executable`` is the workspace venv's Python) and inside the
    agent containers (where it's ``/app/.venv/bin/python3``). Avoids
    the dev-vs-container split that ``uv run kourai-mcp-forge`` would
    introduce — the runtime container images don't carry ``uv``,
    only the venv it produced at build time.
    """
    import sys

    from mcp.client.stdio import StdioServerParameters

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "kourai_mcp_forge"],
        env=_forge_subprocess_env(),
    )
    async with mcp_tool_bridge(params) as bridge:
        yield bridge
