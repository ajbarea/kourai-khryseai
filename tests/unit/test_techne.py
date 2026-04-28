"""Techne: file path parsing, file I/O, code generation via LLM."""

from __future__ import annotations

import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from anyio import Path as AnyioPath

from agents.techne.agent import (
    SYSTEM_PROMPT,
    CodeResult,
    FileChange,
    parse_file_paths,
    read_file,
    read_files,
    write_file,
)


class TestTechneSystemPrompt:
    """Verify the system prompt contains required standards."""

    def test_includes_python_standards(self):
        assert "100 char lines" in SYSTEM_PROMPT
        assert "X | None" in SYSTEM_PROMPT
        assert "Google-style docstrings" in SYSTEM_PROMPT

    def test_includes_frontend_standards(self):
        assert "React 19+" in SYSTEM_PROMPT
        assert "TypeScript strict" in SYSTEM_PROMPT
        assert "Named exports only" in SYSTEM_PROMPT

    def test_edit_over_create(self):
        assert "EDIT existing files" in SYSTEM_PROMPT

    def test_forbids_git_commit(self):
        assert "NEVER run git commit" in SYSTEM_PROMPT

    def test_documents_tool_use(self):
        # ACTION/FILE/CONTENT prose format was retired in M1 — Techne now
        # drives changes through the `write_file`/`edit_file`/`delete_file`
        # tools. The system prompt should advertise that.
        assert "write_file" in SYSTEM_PROMPT
        assert "edit_file" in SYSTEM_PROMPT
        assert "PROJECT-RELATIVE" in SYSTEM_PROMPT
        # The legacy keywords MUST be gone, otherwise the LLM will output
        # them as prose and we'll silently lose writes.
        assert "ACTION: CREATE" not in SYSTEM_PROMPT
        assert "ACTION: DELETE" not in SYSTEM_PROMPT

    def test_no_marketing_language(self):
        assert "No marketing language" in SYSTEM_PROMPT


class TestParseFilePaths:
    """Test file path extraction from user input."""

    def test_single_python_file(self):
        paths = parse_file_paths("fix the bug in src/utils/parser.py")
        assert "src/utils/parser.py" in paths

    def test_multiple_files(self):
        paths = parse_file_paths("update auth.py and tests/test_auth.py")
        assert "auth.py" in paths
        assert "tests/test_auth.py" in paths

    def test_typescript_file(self):
        paths = parse_file_paths("fix src/components/Button.tsx")
        assert "src/components/Button.tsx" in paths

    def test_json_file(self):
        paths = parse_file_paths("update package.json")
        assert "package.json" in paths

    def test_no_files(self):
        paths = parse_file_paths("implement a new feature")
        assert paths == []

    def test_deduplication(self):
        paths = parse_file_paths("read auth.py and then fix auth.py")
        assert paths.count("auth.py") == 1

    def test_toml_file(self):
        paths = parse_file_paths("edit pyproject.toml")
        assert "pyproject.toml" in paths


class TestFileOperations:
    """Test file read/write operations."""

    @pytest.mark.asyncio
    async def test_read_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test_read.py")
            await AnyioPath(path).write_text("x = 1\n")
            content = await read_file(path)
            assert content == "x = 1\n"

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        content = await read_file("/nonexistent/path/file.py")
        assert content is None

    @pytest.mark.asyncio
    async def test_write_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.py")
            success = await write_file(path, "x = 42\n")
            assert success
            assert await AnyioPath(path).exists()
            assert await AnyioPath(path).read_text() == "x = 42\n"

    @pytest.mark.asyncio
    async def test_write_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "sub" / "dir" / "test.py")
            success = await write_file(path, "y = 1\n")
            assert success
            assert await AnyioPath(path).exists()

    @pytest.mark.asyncio
    async def test_read_files_multiple(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = str(Path(tmpdir) / "a.py")
            p2 = str(Path(tmpdir) / "b.py")
            await AnyioPath(p1).write_text("a = 1")
            await AnyioPath(p2).write_text("b = 2")

            result = await read_files([p1, p2, "/nonexistent.py"])
            assert len(result) == 2
            assert result[p1] == "a = 1"
            assert result[p2] == "b = 2"


@asynccontextmanager
async def _fake_forge_bridge(*_args, **_kwargs):
    """Stub `forge_tool_bridge` for tests so they don't launch the
    `kourai-mcp-forge` subprocess. Yields a bridge with empty tools +
    handlers — the `chat_with_tools` mock under each test inspects
    those references separately if the test cares.
    """
    from kourai_common.mcp_bridge import MCPToolBridge

    yield MCPToolBridge(tools=[], tool_handlers={})


class TestApplyCodeChanges:
    """Test the tool-loop driver behind Techne's apply_code_changes.

    Each test patches ``forge_tool_bridge`` with a stub yielding an
    empty ``MCPToolBridge`` so the real ``kourai-mcp-forge`` subprocess
    never launches inside the unit suite.
    """

    @pytest.mark.asyncio
    async def test_drives_chat_with_tools_through_forge_bridge(self):
        from kourai_common.mcp_bridge import MCPToolBridge

        captured_kwargs: dict = {}

        async def _fake_chat(*args, **kwargs):
            captured_kwargs.update(kwargs)
            captured_kwargs["agent_arg"] = args[0]
            return ("done", [])

        bridge_marker_tools = [{"type": "function", "function": {"name": "marker"}}]

        async def _marker_handler(_args: dict) -> str:
            return ""

        bridge_marker_handlers = {"marker": _marker_handler}

        @asynccontextmanager
        async def _bridge(*_a, **_kw):
            yield MCPToolBridge(tools=bridge_marker_tools, tool_handlers=bridge_marker_handlers)

        with (
            patch("agents.techne.agent.forge_tool_bridge", _bridge),
            patch("agents.techne.agent.chat_with_tools", side_effect=_fake_chat),
            patch(
                "kourai_common.doc_lookup.lookup_documentation",
                new_callable=AsyncMock,
                return_value="",
            ),
        ):
            from agents.techne.agent import apply_code_changes

            text, log = await apply_code_changes("fix auth.py", project_root="/work")

        assert text == "done"
        assert log == []
        assert captured_kwargs["agent_arg"] == "techne"
        # Bridge tools/handlers flow through to chat_with_tools — single-source.
        assert captured_kwargs["tools"] is bridge_marker_tools
        assert captured_kwargs["tool_handlers"] is bridge_marker_handlers
        # No more handler_context: project_root reaches the forge server via
        # roots/list (the bridge's _kourai_list_roots reads the contextvar
        # set by apply_code_changes itself).
        assert "handler_context" not in captured_kwargs

    @pytest.mark.asyncio
    async def test_sets_kourai_project_root_var_for_forge_subprocess(self):
        """The forge MCP server reads project_root from the host's
        roots/list response, which `_kourai_list_roots` sources from
        ``kourai_project_root_var``. Verify ``apply_code_changes`` sets
        it during the bridge call so a standalone caller (not via an
        executor) still gets correct scoping.
        """
        from kourai_common.mcp_client import kourai_project_root_var

        captured: list[Path | None] = []

        async def _fake_chat(*_args, **_kwargs):
            captured.append(kourai_project_root_var.get())
            return ("done", [])

        with (
            patch("agents.techne.agent.forge_tool_bridge", _fake_forge_bridge),
            patch("agents.techne.agent.chat_with_tools", side_effect=_fake_chat),
            patch(
                "kourai_common.doc_lookup.lookup_documentation",
                new_callable=AsyncMock,
                return_value="",
            ),
        ):
            from agents.techne.agent import apply_code_changes

            await apply_code_changes("fix auth.py", project_root="/work")

        assert captured[0] == Path("/work")

    @pytest.mark.asyncio
    async def test_includes_file_context_in_user_message(self):
        captured: dict = {}

        async def _fake(*args, **kwargs):
            captured["messages"] = args[1]
            return ("done", [])

        with (
            patch("agents.techne.agent.forge_tool_bridge", _fake_forge_bridge),
            patch("agents.techne.agent.chat_with_tools", side_effect=_fake),
            patch(
                "kourai_common.doc_lookup.lookup_documentation",
                new_callable=AsyncMock,
                return_value="",
            ),
        ):
            from agents.techne.agent import apply_code_changes

            await apply_code_changes(
                "fix auth.py",
                project_root="/work",
                file_contents={"auth.py": "def login(): pass"},
                git_context="M auth.py",
            )

        user_msg = captured["messages"][-1]["content"]
        assert isinstance(user_msg, str)
        assert "auth.py" in user_msg
        assert "def login(): pass" in user_msg
        assert "M auth.py" in user_msg

    @pytest.mark.asyncio
    async def test_image_parts_are_attached(self):
        captured: dict = {}

        async def _fake(*args, **kwargs):
            captured["messages"] = args[1]
            return ("done", [])

        img = {"type": "image_url", "image_url": {"url": "data:image/png;base64,xyz"}}
        with (
            patch("agents.techne.agent.forge_tool_bridge", _fake_forge_bridge),
            patch("agents.techne.agent.chat_with_tools", side_effect=_fake),
            patch(
                "kourai_common.doc_lookup.lookup_documentation",
                new_callable=AsyncMock,
                return_value="",
            ),
        ):
            from agents.techne.agent import apply_code_changes

            await apply_code_changes("look at this", project_root="/work", image_parts=[img])

        user_content = captured["messages"][-1]["content"]
        assert isinstance(user_content, list)
        assert user_content[0]["type"] == "text"
        assert user_content[1] is img

    @pytest.mark.asyncio
    async def test_forwards_on_tool_call_callback(self):
        captured: dict = {}

        async def _fake(*args, **kwargs):
            captured["on_tool_call"] = kwargs.get("on_tool_call")
            return ("done", [])

        async def _hook(name, args, result):
            pass

        with (
            patch("agents.techne.agent.forge_tool_bridge", _fake_forge_bridge),
            patch("agents.techne.agent.chat_with_tools", side_effect=_fake),
            patch(
                "kourai_common.doc_lookup.lookup_documentation",
                new_callable=AsyncMock,
                return_value="",
            ),
        ):
            from agents.techne.agent import apply_code_changes

            await apply_code_changes("x", project_root="/work", on_tool_call=_hook)
        assert captured["on_tool_call"] is _hook


class TestRunCommand:
    """Test shell command execution."""

    @pytest.mark.asyncio
    async def test_run_returns_stdout(self):
        from agents.techne.agent import run_command

        code, stdout, stderr = await run_command(["python", "-c", "print('hello')"])
        assert code == 0
        assert "hello" in stdout

    @pytest.mark.asyncio
    async def test_run_captures_stderr(self):
        from agents.techne.agent import run_command

        code, stdout, stderr = await run_command(
            ["python", "-c", "import sys; sys.stderr.write('err')"]
        )
        assert "err" in stderr


class TestGetGitContext:
    """Test git context gathering."""

    @pytest.mark.asyncio
    async def test_returns_string(self):
        from agents.techne.agent import get_git_context

        result = await get_git_context()
        assert isinstance(result, str)


class TestDataclasses:
    """Test code result data structures."""

    def test_file_change_defaults(self):
        fc = FileChange(action="CREATE", file_path="new.py")
        assert fc.content == ""
        assert fc.original == ""

    def test_code_result_defaults(self):
        cr = CodeResult()
        assert cr.changes == []
        assert cr.success is False


class TestTechneAgentCard:
    """Test the agent card configuration."""

    def test_card_has_required_fields(self):
        from agents.techne.__main__ import build_agent_card

        card = build_agent_card()
        assert card.name
        assert card.version == "0.1.0"
        assert card.capabilities.streaming is True
        assert len(card.skills) == 1
        assert card.skills[0].id == "implement_code"

    def test_card_skill_tags(self):
        from agents.techne.__main__ import build_agent_card

        card = build_agent_card()
        tags = card.skills[0].tags
        assert "coding" in tags
        assert "python" in tags
