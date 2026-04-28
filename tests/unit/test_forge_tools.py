"""Tests for kourai_common.forge_tools — file-op handlers behind the LLM tool loop.

Each handler must:
- write/read/edit/delete only inside ``project_root`` (containment check)
- reject path escapes and disallowed extensions with an ``ERROR:`` string
- never raise back into the agentic loop
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kourai_common.forge_tools import (
    delete_file,
    edit_file,
    read_file,
    write_file,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Empty project root for handler tests."""
    return tmp_path


class TestWriteFile:
    @pytest.mark.asyncio
    async def test_creates_file(self, project_root: Path):
        result = await write_file("hello.py", "print('hi')", project_root=project_root)
        assert "Wrote hello.py" in result
        assert (project_root / "hello.py").read_text() == "print('hi')\n"

    @pytest.mark.asyncio
    async def test_creates_parent_dirs(self, project_root: Path):
        await write_file("src/pkg/mod.py", "x = 1", project_root=project_root)
        assert (project_root / "src/pkg/mod.py").read_text() == "x = 1\n"

    @pytest.mark.asyncio
    async def test_appends_trailing_newline(self, project_root: Path):
        await write_file("a.py", "no newline", project_root=project_root)
        assert (project_root / "a.py").read_text().endswith("\n")

    @pytest.mark.asyncio
    async def test_overwrites_existing(self, project_root: Path):
        (project_root / "a.py").write_text("old\n")
        await write_file("a.py", "new", project_root=project_root)
        assert (project_root / "a.py").read_text() == "new\n"

    @pytest.mark.asyncio
    async def test_rejects_path_escape(self, project_root: Path):
        result = await write_file("../escape.py", "evil", project_root=project_root)
        assert result.startswith("ERROR:")
        assert "escape" in result.lower()
        assert not (project_root.parent / "escape.py").exists()

    @pytest.mark.asyncio
    async def test_rejects_disallowed_extension(self, project_root: Path):
        result = await write_file("evil.sh", "#!/bin/sh\nrm -rf /", project_root=project_root)
        assert result.startswith("ERROR:")
        assert not (project_root / "evil.sh").exists()


class TestEditFile:
    @pytest.mark.asyncio
    async def test_replaces_unique_occurrence(self, project_root: Path):
        (project_root / "a.py").write_text("def foo():\n    return 1\n")
        result = await edit_file("a.py", "return 1", "return 42", project_root=project_root)
        assert "Edited a.py" in result
        assert (project_root / "a.py").read_text() == "def foo():\n    return 42\n"

    @pytest.mark.asyncio
    async def test_errors_when_not_found(self, project_root: Path):
        (project_root / "a.py").write_text("hello\n")
        result = await edit_file("a.py", "missing", "x", project_root=project_root)
        assert result.startswith("ERROR:")
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_errors_on_multiple_matches(self, project_root: Path):
        (project_root / "a.py").write_text("x\nx\nx\n")
        result = await edit_file("a.py", "x", "y", project_root=project_root)
        assert result.startswith("ERROR:")
        assert "matched 3 times" in result
        assert (project_root / "a.py").read_text() == "x\nx\nx\n"

    @pytest.mark.asyncio
    async def test_errors_when_file_missing(self, project_root: Path):
        result = await edit_file("nope.py", "old", "new", project_root=project_root)
        assert result.startswith("ERROR:")
        assert "file not found" in result

    @pytest.mark.asyncio
    async def test_rejects_path_escape(self, project_root: Path):
        result = await edit_file("../etc/passwd", "x", "y", project_root=project_root)
        assert result.startswith("ERROR:")


class TestDeleteFile:
    @pytest.mark.asyncio
    async def test_removes_file(self, project_root: Path):
        (project_root / "a.py").write_text("x\n")
        result = await delete_file("a.py", project_root=project_root)
        assert "Deleted a.py" in result
        assert not (project_root / "a.py").exists()

    @pytest.mark.asyncio
    async def test_no_op_when_absent(self, project_root: Path):
        result = await delete_file("nope.py", project_root=project_root)
        assert "already absent" in result

    @pytest.mark.asyncio
    async def test_rejects_path_escape(self, project_root: Path):
        outside = project_root.parent / "outside.py"
        outside.write_text("keep me\n")
        result = await delete_file("../outside.py", project_root=project_root)
        assert result.startswith("ERROR:")
        assert outside.exists()
        outside.unlink()


class TestReadFile:
    @pytest.mark.asyncio
    async def test_returns_line_numbered_contents(self, project_root: Path):
        (project_root / "a.py").write_text("alpha\nbeta\n")
        result = await read_file("a.py", project_root=project_root)
        assert "1: alpha" in result
        assert "2: beta" in result

    @pytest.mark.asyncio
    async def test_errors_when_file_missing(self, project_root: Path):
        result = await read_file("nope.py", project_root=project_root)
        assert result.startswith("ERROR:")
        assert "file not found" in result

    @pytest.mark.asyncio
    async def test_rejects_path_escape(self, project_root: Path):
        result = await read_file("../../etc/passwd", project_root=project_root)
        assert result.startswith("ERROR:")

    @pytest.mark.asyncio
    async def test_rejects_directory_path(self, project_root: Path):
        # Round 6 caught Techne repeatedly trying directory paths
        # through read_file. The handler's `target.exists()` check
        # used to pass for directories and read_file_with_context
        # would then return garbage. Now the handler explicitly
        # rejects directories with a clear error.
        (project_root / "src").mkdir(exist_ok=True)
        result = await read_file("src", project_root=project_root)
        assert result.startswith("ERROR:")
        assert "directory" in result.lower()
        # Hint nudges the model toward the right next move.
        assert "specific" in result or "list" in result

    # The schema-level "directory" hint contract moved to the MCP server's
    # tool description after M2 Change 3 deleted FORGE_TOOL_SCHEMAS — see
    # tests/unit/test_forge_mcp.py::test_read_file_description_warns_against_directory_paths
    # for the new contract test.
