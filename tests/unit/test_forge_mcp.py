"""Tests for the kourai-mcp-forge MCP server.

The forge server exposes the M1 forge file ops (``read_file``,
``write_file``, ``edit_file``, ``delete_file``) over MCP, scoping each
call to the host's declared roots. These tests cover:

- Tool registration: the 4 tools are present with the right names.
- ``_resolve_project_root`` happy path + error paths.
- End-to-end: each tool reads/writes/edits/deletes files in a real
  ``tmp_path`` via the existing ``kourai_common.forge_tools`` handlers,
  with a mocked ``ctx.session.list_roots()`` returning ``tmp_path`` as
  the sole root.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from kourai_mcp_forge.server import (
    _NO_ROOTS_ERROR,
    _resolve_project_root,
    delete_file,
    edit_file,
    mcp,
    read_file,
    write_file,
)
from mcp.types import FileUrl, ListRootsResult, Root


def _make_ctx(roots_result: ListRootsResult | Exception) -> MagicMock:
    """Build a mock FastMCP Context whose ``session.list_roots()`` returns
    (or raises) the given ``roots_result``.
    """
    ctx = MagicMock()
    if isinstance(roots_result, Exception):
        ctx.session = AsyncMock()
        ctx.session.list_roots = AsyncMock(side_effect=roots_result)
    else:
        ctx.session = AsyncMock()
        ctx.session.list_roots = AsyncMock(return_value=roots_result)
    return ctx


def _ctx_for_root(root: Path) -> MagicMock:
    """Shorthand: a mock Context advertising a single root at ``root``."""
    return _make_ctx(ListRootsResult(roots=[Root(uri=FileUrl(root.as_uri()), name="project_root")]))


# ── Tool registration ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_server_registers_four_forge_tools():
    """The forge server must expose exactly the M1 forge ops; nothing else
    rides along here (``run_command`` lives in the shell MCP server).
    """
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == {"read_file", "write_file", "edit_file", "delete_file"}


# ── _resolve_project_root ────────────────────────────────────────────────────


class TestResolveProjectRoot:
    @pytest.mark.asyncio
    async def test_returns_path_for_single_root(self, tmp_path: Path):
        ctx = _ctx_for_root(tmp_path)
        result = await _resolve_project_root(ctx)
        assert isinstance(result, Path)
        assert result == tmp_path

    @pytest.mark.asyncio
    async def test_returns_error_string_when_roots_empty(self):
        """Honest "no roots scoped" rather than crashing — server returns
        an ERROR string the client surfaces verbatim, pointing at
        ``kourai_project_root_var`` so a contributor can debug.
        """
        ctx = _make_ctx(ListRootsResult(roots=[]))
        result = await _resolve_project_root(ctx)
        assert isinstance(result, str)
        assert result == _NO_ROOTS_ERROR

    @pytest.mark.asyncio
    async def test_returns_error_string_when_list_roots_raises(self):
        """A client without a ``list_roots_callback`` (which would happen
        if a non-kourai host connected without declaring ``roots``) leads
        to ``ErrorData(INVALID_REQUEST)``; the SDK surfaces that as an
        exception. Tool returns ERROR rather than crashing.
        """
        ctx = _make_ctx(RuntimeError("List roots not supported"))
        result = await _resolve_project_root(ctx)
        assert isinstance(result, str)
        assert result.startswith("ERROR:")
        assert "roots" in result

    @pytest.mark.asyncio
    async def test_uses_first_when_multiple_roots(self, tmp_path: Path):
        """Multiple roots is unusual but the spec allows it. Pick the first
        and let the warning log capture the multi-root case for triage.
        """
        other = tmp_path / "other"
        other.mkdir()
        ctx = _make_ctx(
            ListRootsResult(
                roots=[
                    Root(uri=FileUrl(tmp_path.as_uri()), name="primary"),
                    Root(uri=FileUrl(other.as_uri()), name="secondary"),
                ]
            )
        )
        result = await _resolve_project_root(ctx)
        assert result == tmp_path


# ── End-to-end tool execution ────────────────────────────────────────────────


class TestReadFileTool:
    @pytest.mark.asyncio
    async def test_returns_line_numbered_contents(self, tmp_path: Path):
        target = tmp_path / "hello.py"
        target.write_text("x = 1\ny = 2\n")
        result = await read_file("hello.py", _ctx_for_root(tmp_path))
        assert "x = 1" in result
        assert "y = 2" in result

    @pytest.mark.asyncio
    async def test_returns_no_roots_error_when_unscoped(self, tmp_path: Path):
        """No roots → tool short-circuits with the declared-but-unset
        diagnostic; never reaches the underlying handler.
        """
        result = await read_file("hello.py", _make_ctx(ListRootsResult(roots=[])))
        assert result == _NO_ROOTS_ERROR


class TestWriteFileTool:
    @pytest.mark.asyncio
    async def test_creates_file_inside_root(self, tmp_path: Path):
        result = await write_file("foo.py", "x = 1", _ctx_for_root(tmp_path))
        target = tmp_path / "foo.py"
        assert target.exists()
        # forge_tools.write_file appends a trailing newline if missing.
        assert target.read_text() == "x = 1\n"
        assert "Wrote foo.py" in result

    @pytest.mark.asyncio
    async def test_rejects_path_outside_root(self, tmp_path: Path):
        """The underlying ``validate_file_path`` guard catches escape
        attempts; the MCP layer should surface the ERROR string verbatim.
        """
        result = await write_file("../escape.py", "evil = True", _ctx_for_root(tmp_path))
        assert result.startswith("ERROR:")


class TestEditFileTool:
    @pytest.mark.asyncio
    async def test_replaces_unique_match(self, tmp_path: Path):
        target = tmp_path / "module.py"
        target.write_text("placeholder = None\n")
        result = await edit_file(
            "module.py", "placeholder = None", "value = 42", _ctx_for_root(tmp_path)
        )
        assert target.read_text() == "value = 42\n"
        assert "Edited module.py" in result

    @pytest.mark.asyncio
    async def test_rejects_ambiguous_match(self, tmp_path: Path):
        target = tmp_path / "dup.py"
        target.write_text("dup = 1\ndup = 1\n")
        result = await edit_file("dup.py", "dup = 1", "x = 2", _ctx_for_root(tmp_path))
        assert result.startswith("ERROR:")
        assert "matched 2 times" in result


class TestDeleteFileTool:
    @pytest.mark.asyncio
    async def test_deletes_existing_file(self, tmp_path: Path):
        target = tmp_path / "doomed.py"
        target.write_text("# bye\n")
        result = await delete_file("doomed.py", _ctx_for_root(tmp_path))
        assert not target.exists()
        assert "Deleted doomed.py" in result

    @pytest.mark.asyncio
    async def test_no_op_when_absent(self, tmp_path: Path):
        result = await delete_file("nonexistent.py", _ctx_for_root(tmp_path))
        assert "already absent" in result


class TestForgeSpans:
    """Each forge tool wraps the underlying handler in a `create_span` so
    the tool latency lands in Jaeger when the bridge migration (Change 3b+)
    routes specialist tool calls through the subprocess. Without this, the
    in-process trace ends at the bridge handler and the dev sees
    ``forge.write_file`` time as one undifferentiated subprocess span.
    """

    @pytest.mark.asyncio
    async def test_write_file_emits_span(self, tmp_path: Path):
        from contextlib import contextmanager
        from unittest.mock import patch

        captured: list[tuple[str, dict]] = []

        @contextmanager
        def capturing_span(name: str, attributes: dict | None = None):
            captured.append((name, attributes or {}))
            yield MagicMock()

        with patch("kourai_mcp_forge.server.create_span", capturing_span):
            await write_file("traced.py", "x = 1", _ctx_for_root(tmp_path))

        assert "forge.write_file" in [n for n, _ in captured]
        attrs = next(a for n, a in captured if n == "forge.write_file")
        assert attrs.get("forge.path") == "traced.py"
        assert attrs.get("forge.content_chars") == "5"

    @pytest.mark.asyncio
    async def test_no_span_emitted_when_roots_unscoped(self, tmp_path: Path):
        """Short-circuit at the roots-resolution stage should NOT emit a
        span — the underlying handler never runs, so a span would imply
        work that didn't happen.
        """
        from contextlib import contextmanager
        from unittest.mock import patch

        captured: list[str] = []

        @contextmanager
        def capturing_span(name: str, attributes: dict | None = None):
            captured.append(name)
            yield MagicMock()

        with patch("kourai_mcp_forge.server.create_span", capturing_span):
            await write_file(
                "x.py", "y = 1", _make_ctx(__import__("mcp").types.ListRootsResult(roots=[]))
            )

        assert captured == []
