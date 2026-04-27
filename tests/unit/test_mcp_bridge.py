"""Tests for ``kourai_common.mcp_bridge``.

Three layers covered:
    1. Pure helpers (``mcp_tool_to_openai_schema``, ``_extract_text``).
    2. Handler factory (``_make_mcp_tool_handler``) against a mock
       ``ClientSession``.
    3. Live integration: ``forge_tool_bridge()`` actually launches
       ``uv run kourai-mcp-forge`` as a stdio subprocess and roundtrips
       a write_file call. Slow (~few seconds for subprocess spawn) but
       verifies the full M2 Change 1 + 2 + 3a stack end-to-end.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.types import CallToolResult, TextContent, Tool

from kourai_common.mcp_bridge import (
    MCPToolBridge,
    _extract_text,
    _make_mcp_tool_handler,
    forge_tool_bridge,
    mcp_tool_to_openai_schema,
)
from kourai_common.mcp_client import kourai_project_root_var

if TYPE_CHECKING:
    from pathlib import Path

# ── Pure helpers ─────────────────────────────────────────────────────────────


def test_mcp_tool_to_openai_schema_full_roundtrip():
    """An MCP ``Tool`` with name + description + inputSchema should land as
    a ``{"type": "function", "function": {...}}`` dict that LiteLLM can
    consume directly.
    """
    tool = Tool(
        name="write_file",
        description="Create or overwrite a file at the project-relative path.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    )
    schema = mcp_tool_to_openai_schema(tool)
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "write_file"
    assert "Create or overwrite" in schema["function"]["description"]
    assert schema["function"]["parameters"]["properties"]["path"]["type"] == "string"


def test_mcp_tool_to_openai_schema_handles_missing_description():
    """Tool without a description should produce ``description=""`` rather
    than ``None`` — LiteLLM rejects ``None`` for that field.
    """
    tool = Tool(name="bare", description=None, inputSchema={"type": "object"})
    schema = mcp_tool_to_openai_schema(tool)
    assert schema["function"]["description"] == ""


def test_extract_text_concatenates_text_content_items():
    content = [
        TextContent(type="text", text="hello "),
        TextContent(type="text", text="world"),
    ]
    assert _extract_text(content) == "hello \nworld"


def test_extract_text_returns_empty_for_no_text_items():
    """Non-text MCP content (image, embedded resource) should be silently
    skipped at the bridge layer — the ``-> str`` handler shape can't surface
    them, and forge tools don't emit them today.
    """
    item = MagicMock()
    del item.text  # ensure getattr(item, "text", None) returns None
    assert _extract_text([item]) == ""


# ── Handler factory ──────────────────────────────────────────────────────────


class TestMakeMcpToolHandler:
    @pytest.mark.asyncio
    async def test_handler_proxies_kwargs_to_call_tool(self):
        session = MagicMock()
        session.call_tool = AsyncMock(
            return_value=CallToolResult(
                content=[TextContent(type="text", text="Wrote foo.py (5 chars).")],
                isError=False,
            )
        )
        handler = _make_mcp_tool_handler(session, "write_file")

        result = await handler(path="foo.py", content="x = 1")

        session.call_tool.assert_awaited_once_with(
            "write_file", {"path": "foo.py", "content": "x = 1"}
        )
        assert result == "Wrote foo.py (5 chars)."

    @pytest.mark.asyncio
    async def test_handler_returns_error_string_when_is_error_true(self):
        """The forge server prefixes its error returns with ``ERROR:`` so
        the existing tool-loop error path (which inspects that prefix)
        keeps working — verify the bridge passes that through verbatim.
        """
        session = MagicMock()
        session.call_tool = AsyncMock(
            return_value=CallToolResult(
                content=[TextContent(type="text", text="ERROR: file not found: foo.py")],
                isError=True,
            )
        )
        handler = _make_mcp_tool_handler(session, "read_file")

        result = await handler(path="foo.py")

        assert result == "ERROR: file not found: foo.py"

    @pytest.mark.asyncio
    async def test_handler_wraps_unprefixed_error_text(self):
        """If a server returns ``isError=True`` without the ``ERROR:``
        prefix, the bridge adds one so downstream tool-loop logic stays
        consistent.
        """
        session = MagicMock()
        session.call_tool = AsyncMock(
            return_value=CallToolResult(
                content=[TextContent(type="text", text="something broke")],
                isError=True,
            )
        )
        handler = _make_mcp_tool_handler(session, "write_file")

        result = await handler(path="foo.py", content="x = 1")

        assert result == "ERROR: something broke"

    @pytest.mark.asyncio
    async def test_handler_returns_generic_error_when_no_text(self):
        session = MagicMock()
        session.call_tool = AsyncMock(return_value=CallToolResult(content=[], isError=True))
        handler = _make_mcp_tool_handler(session, "write_file")

        result = await handler(path="foo.py", content="x = 1")

        assert result == "ERROR: tool call failed"


# ── Live integration: forge subprocess roundtrip ─────────────────────────────


class TestForgeBridgeLive:
    """End-to-end: launches the actual ``kourai-mcp-forge`` stdio subprocess
    via ``uv run`` and exercises the full Change 1 + 2 + 3a stack — kourai
    declares ``roots``, server asks ``roots/list``, kourai responds with
    ``kourai_project_root_var``, tool call validates the path, response
    surfaces back through the bridge to a string the tool loop consumes.
    """

    @pytest.mark.asyncio
    async def test_forge_bridge_lists_four_tools(self):
        async with forge_tool_bridge() as bridge:
            assert isinstance(bridge, MCPToolBridge)
            tool_names = {t["function"]["name"] for t in bridge.tools}
            assert tool_names == {"read_file", "write_file", "edit_file", "delete_file"}
            assert set(bridge.tool_handlers.keys()) == tool_names

    @pytest.mark.asyncio
    async def test_forge_bridge_write_then_read_roundtrip(self, tmp_path: Path):
        """Set the contextvar, launch the bridge, write a file via the
        ``write_file`` MCP tool, then read it back via the ``read_file``
        MCP tool — same project_root scope flows through the entire stack.
        """
        token = kourai_project_root_var.set(tmp_path)
        try:
            async with forge_tool_bridge() as bridge:
                write_result = await bridge.tool_handlers["write_file"](
                    path="hello.py", content="x = 1"
                )
                assert "Wrote hello.py" in write_result

                # Verify the file actually landed in tmp_path (not somewhere
                # the contextvar didn't cover).
                target = tmp_path / "hello.py"
                assert target.exists()
                assert target.read_text() == "x = 1\n"

                read_result = await bridge.tool_handlers["read_file"](path="hello.py")
                assert "x = 1" in read_result
        finally:
            kourai_project_root_var.reset(token)

    @pytest.mark.asyncio
    async def test_forge_bridge_rejects_path_escape(self, tmp_path: Path):
        """The forge server's ``validate_file_path`` guard should reject
        any path that escapes the declared root, and the bridge should
        surface the ERROR string verbatim.
        """
        token = kourai_project_root_var.set(tmp_path)
        try:
            async with forge_tool_bridge() as bridge:
                result = await bridge.tool_handlers["write_file"](
                    path="../escape.py", content="evil = True"
                )
                assert result.startswith("ERROR:")
        finally:
            kourai_project_root_var.reset(token)
