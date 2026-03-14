"""Techne: file path parsing, file I/O, code generation via LLM."""

from __future__ import annotations

import os
import tempfile
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

    def test_includes_output_format(self):
        assert "ACTION:" in SYSTEM_PROMPT
        assert "FILE:" in SYSTEM_PROMPT
        assert "CONTENT:" in SYSTEM_PROMPT

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
            path = os.path.join(tmpdir, "test_read.py")
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
            path = os.path.join(tmpdir, "test.py")
            success = await write_file(path, "x = 42\n")
            assert success
            assert await AnyioPath(path).exists()
            assert await AnyioPath(path).read_text() == "x = 42\n"

    @pytest.mark.asyncio
    async def test_write_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sub", "dir", "test.py")
            success = await write_file(path, "y = 1\n")
            assert success
            assert await AnyioPath(path).exists()

    @pytest.mark.asyncio
    async def test_read_files_multiple(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = os.path.join(tmpdir, "a.py")
            p2 = os.path.join(tmpdir, "b.py")
            await AnyioPath(p1).write_text("a = 1")
            await AnyioPath(p2).write_text("b = 2")

            result = await read_files([p1, p2, "/nonexistent.py"])
            assert len(result) == 2
            assert result[p1] == "a = 1"
            assert result[p2] == "b = 2"


class TestGenerateCode:
    """Test code generation with mocked LLM."""

    @pytest.mark.asyncio
    async def test_generate_calls_llm(self):
        mock_response = "ACTION: EDIT\nFILE: auth.py\nCONTENT:\n```python\nx = 1\n```"
        with patch("agents.techne.agent.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_response
            from agents.techne.agent import generate_code

            result = await generate_code("fix the bug in auth.py")
            assert result == mock_response
            assert mock_chat.call_args[0][0] == "techne"

    @pytest.mark.asyncio
    async def test_generate_includes_file_context(self):
        with patch("agents.techne.agent.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "done"
            from agents.techne.agent import generate_code

            await generate_code(
                "fix auth.py",
                file_contents={"auth.py": "def login(): pass"},
            )
            # The file content should be in the prompt
            call_messages = mock_chat.call_args[0][1]
            user_msg = call_messages[-1]["content"]
            assert "auth.py" in user_msg
            assert "def login(): pass" in user_msg


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


class TestGenerateCodeStream:
    """Test streaming code generation."""

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self):
        async def mock_stream(*args, **kwargs):
            for chunk in ["ACTION:", " EDIT", "\nFILE:"]:
                yield chunk

        with patch("agents.techne.agent.chat_stream", side_effect=mock_stream):
            from agents.techne.agent import generate_code_stream

            chunks = []
            async for chunk in generate_code_stream("fix bug"):
                chunks.append(chunk)

            assert len(chunks) == 3
            assert "".join(chunks) == "ACTION: EDIT\nFILE:"

    @pytest.mark.asyncio
    async def test_stream_includes_file_context(self):
        received_messages: list[object] = []

        async def mock_stream(*args, **kwargs):
            received_messages.extend(args)
            yield "done"

        with patch("agents.techne.agent.chat_stream", side_effect=mock_stream):
            from agents.techne.agent import generate_code_stream

            async for _ in generate_code_stream(
                "fix auth",
                file_contents={"auth.py": "code"},
                git_context="M auth.py",
            ):
                pass

        # Messages should include file content and git context
        msg_str = str(received_messages)
        assert "auth.py" in msg_str


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
