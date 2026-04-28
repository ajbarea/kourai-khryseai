"""Agent executors: shared A2A bridge pattern across all six agents.

Tests the three-layer executor pattern: empty input → input_required,
valid input → working → artifact → complete, cancel → unsupported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from a2a.types import Message, Part, Role, TextPart
from a2a.utils.errors import ServerError

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _async_gen(items: list[str]):
    """Yield items as an async generator (for mocking streaming functions)."""
    for item in items:
        yield item


def _make_context(user_input: str | None = "test input") -> MagicMock:
    ctx = MagicMock()
    ctx.get_user_input.return_value = user_input
    ctx.current_task = None
    # A2A SDK requires non-empty TextPart, so always use a valid message
    ctx.message = Message(
        role=Role.user,
        parts=[Part(root=TextPart(text=user_input or "placeholder"))],
        message_id=str(uuid4()),
        context_id=uuid4().hex,
    )
    return ctx


def _make_queue() -> AsyncMock:
    return AsyncMock()


def _collect_events(queue: AsyncMock) -> list:
    return [call.args[0] for call in queue.enqueue_event.call_args_list]


# ---------------------------------------------------------------------------
# Parametrized common tests for all executors
# ---------------------------------------------------------------------------

AGENT_EXECUTORS = [
    ("mneme", "agents.mneme.agent_executor", "MnemeAgentExecutor"),
    ("kallos", "agents.kallos.agent_executor", "KallosAgentExecutor"),
    ("metis", "agents.metis.agent_executor", "MetisAgentExecutor"),
    ("dokimasia", "agents.dokimasia.agent_executor", "DokimasiaAgentExecutor"),
    ("techne", "agents.techne.agent_executor", "TechneAgentExecutor"),
    ("hephaestus", "agents.hephaestus.agent_executor", "HephaestusAgentExecutor"),
]


class TestExecutorCommonBehavior:
    """Common tests parametrized across all 6 agent executors."""

    @pytest.mark.parametrize("agent_name,module_path,class_name", AGENT_EXECUTORS)
    @pytest.mark.asyncio
    async def test_empty_input_returns_input_required(
        self, agent_name: str, module_path: str, class_name: str
    ):
        """All executors should return input_required status for empty input."""
        executor_module = __import__(module_path, fromlist=[class_name])
        executor_class = getattr(executor_module, class_name)

        executor = executor_class()
        ctx = _make_context("")
        queue = _make_queue()

        with patch(f"{module_path}.create_span"):
            await executor.execute(ctx, queue)

        # Should have enqueued at least a task creation event
        assert queue.enqueue_event.call_count >= 1

    @pytest.mark.parametrize("agent_name,module_path,class_name", AGENT_EXECUTORS)
    @pytest.mark.asyncio
    async def test_cancel_raises_unsupported(
        self, agent_name: str, module_path: str, class_name: str
    ):
        """All executors should raise ServerError on cancel (unsupported operation)."""
        executor_module = __import__(module_path, fromlist=[class_name])
        executor_class = getattr(executor_module, class_name)

        executor = executor_class()
        with pytest.raises(ServerError):
            await executor.cancel(_make_context(), _make_queue())


# ---------------------------------------------------------------------------
# Agent-specific tests (different logic per executor)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Agent-specific tests (different logic per executor)
# ---------------------------------------------------------------------------


class TestMnemeExecutor:
    """Mneme-specific tests (streaming, commit messages)."""

    @pytest.mark.asyncio
    async def test_valid_input_streams_and_completes(self):
        from agents.mneme.agent_executor import MnemeAgentExecutor

        executor = MnemeAgentExecutor()
        ctx = _make_context("git diff output here")
        queue = _make_queue()

        async def mock_stream(git_output):
            for chunk in ["feat: ", "add feature"]:
                yield chunk

        with (
            patch("agents.mneme.agent_executor.create_span"),
            patch(
                "agents.mneme.agent_executor.generate_commit_messages_stream",
                side_effect=mock_stream,
            ),
        ):
            await executor.execute(ctx, queue)

        assert queue.enqueue_event.call_count >= 2


class TestKallosExecutor:
    """Kallos-specific tests (linting, style checks)."""

    @pytest.mark.asyncio
    async def test_valid_input_runs_style_check(self):
        from agents.kallos.agent_executor import KallosAgentExecutor

        executor = KallosAgentExecutor()
        ctx = _make_context("agents/kallos/agent.py")
        queue = _make_queue()

        # Mock the run_make_lint function to return success
        async def mock_run_make_lint(**kwargs):
            return (True, "All checks passed")

        with (
            patch("agents.kallos.agent_executor.create_span"),
            patch("agents.kallos.agent.run_make_lint", side_effect=mock_run_make_lint),
            patch("kourai_common.subprocess.extract_files_from_output", return_value=[]),
        ):
            await executor.execute(ctx, queue)

        assert queue.enqueue_event.call_count >= 3


class TestMetisExecutor:
    """Metis-specific tests (planning, specs)."""

    @pytest.mark.asyncio
    async def test_valid_input_generates_spec(self):
        from agents.metis.agent_executor import MetisAgentExecutor

        executor = MetisAgentExecutor()
        ctx = _make_context("implement CSV export")
        queue = _make_queue()

        # Return 5+ chunks to trigger inner-loop status updates (every 5th chunk)
        spec_chunks = [
            "## Spec\nDo things",
            "## Spec\nDo things",
            "## Spec\nDo things",
            "## Spec\nDo things",
            "## Spec\nDo things",
            "## Spec\nDo things",
            "## Spec\nDo things",
            "## Spec\nDo things",
            "## Spec\nDo things",
            "## Spec\nDo things",
        ]
        with (
            patch("agents.metis.agent_executor.create_span"),
            patch(
                "agents.metis.agent_executor.get_project_context",
                return_value="project ctx",
            ),
            patch(
                "agents.metis.agent_executor.create_spec_stream",
                return_value=_async_gen(spec_chunks),
            ),
            patch("agents.metis.agent_executor.send_working_status"),
        ):
            await executor.execute(ctx, queue)

        # Enqueue events: task creation + add_artifact + complete (send_working_status is mocked)
        assert queue.enqueue_event.call_count >= 3

    @pytest.mark.asyncio
    async def test_get_project_context_called_with_project_root(self):
        """Round 6 caught `git status --short` exiting 128 from the
        Metis container because the default cwd (`/app`) isn't the
        worktree. The executor now parses [project_root: ...] and
        threads it through to get_project_context."""
        from agents.metis.agent_executor import MetisAgentExecutor

        executor = MetisAgentExecutor()
        ctx = _make_context("[project_root: /tmp/forge/abc123]\nimplement CSV export")
        queue = _make_queue()

        get_ctx_mock = AsyncMock(return_value="project ctx")

        with (
            patch("agents.metis.agent_executor.create_span"),
            patch("agents.metis.agent_executor.get_project_context", get_ctx_mock),
            patch(
                "agents.metis.agent_executor.create_spec_stream",
                return_value=_async_gen(["spec"]),
            ),
            patch("agents.metis.agent_executor.send_working_status"),
        ):
            await executor.execute(ctx, queue)

        get_ctx_mock.assert_called_once()
        call_kwargs = get_ctx_mock.call_args.kwargs
        assert "project_root" in call_kwargs
        assert call_kwargs["project_root"] is not None


class TestDokimasiaExecutor:
    """Dokimasia-specific tests (testing, pytest runs)."""

    @pytest.mark.asyncio
    async def test_run_request_runs_pytest(self):
        from agents.dokimasia.agent_executor import DokimasiaAgentExecutor

        executor = DokimasiaAgentExecutor()
        ctx = _make_context("run tests please")
        queue = _make_queue()

        # Mock run_pytest to return an object with success and output
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "8/8 tests passed"

        with (
            patch("agents.dokimasia.agent_executor.create_span"),
            patch("agents.dokimasia.agent.run_pytest", return_value=mock_result),
            patch("kourai_common.subprocess.extract_files_from_output", return_value=[]),
        ):
            await executor.execute(ctx, queue)

        assert queue.enqueue_event.call_count >= 3

    @pytest.mark.asyncio
    async def test_generate_request_writes_tests(self):
        from agents.dokimasia.agent_executor import DokimasiaAgentExecutor

        executor = DokimasiaAgentExecutor()
        ctx = _make_context("def add(a, b): return a + b")
        queue = _make_queue()

        with (
            patch("agents.dokimasia.agent_executor.create_span"),
            patch(
                "agents.dokimasia.agent_executor.generate_tests_stream",
                return_value=_async_gen(["def test_add():"]),
            ),
            patch("agents.dokimasia.agent_executor.send_working_status"),
        ):
            await executor.execute(ctx, queue)

        # Enqueue events: task creation + add_artifact + complete (send_working_status is mocked)
        assert queue.enqueue_event.call_count >= 3


class TestTechneExecutor:
    """Techne-specific tests (code generation via tool-use loop)."""

    @pytest.mark.asyncio
    async def test_valid_input_drives_tool_loop_and_emits_artifact(self):
        from agents.techne.agent_executor import TechneAgentExecutor

        executor = TechneAgentExecutor()
        ctx = _make_context("fix auth.py null check")
        queue = _make_queue()

        tool_log = [
            {
                "name": "write_file",
                "args": {"path": "auth.py", "content": "x = 1\n"},
                "result": "Wrote auth.py (6 chars).",
            },
            {
                "name": "read_file",
                "args": {"path": "auth.py"},
                "result": "1: x = 1",
            },
        ]

        with (
            patch("agents.techne.agent_executor.create_span"),
            patch(
                "agents.techne.agent_executor.parse_file_paths",
                return_value=["auth.py"],
            ),
            patch(
                "agents.techne.agent_executor.read_files",
                return_value={"auth.py": "code"},
            ),
            patch("agents.techne.agent_executor.get_git_context", return_value="M auth.py"),
            patch(
                "agents.techne.agent_executor.apply_code_changes",
                new_callable=AsyncMock,
                return_value=("Updated auth.py.", tool_log),
            ),
            patch("agents.techne.agent_executor.send_working_status"),
        ):
            await executor.execute(ctx, queue)

        # Enqueue events: task creation + add_artifact + complete
        assert queue.enqueue_event.call_count >= 3

    @pytest.mark.asyncio
    async def test_get_git_context_called_with_project_root_cwd(self):
        """Round 6 caught `git status --short` exiting 128 because the
        Techne container's default cwd (`/app`) isn't the worktree.
        Ensure get_git_context now receives the parsed project_root as
        cwd so the call lands in the right repo."""
        from agents.techne.agent_executor import TechneAgentExecutor

        executor = TechneAgentExecutor()
        ctx = _make_context("[project_root: /tmp/forge/abc123]\nfix auth.py null check")
        queue = _make_queue()

        git_context_mock = AsyncMock(return_value="M auth.py")

        with (
            patch("agents.techne.agent_executor.create_span"),
            patch(
                "agents.techne.agent_executor.parse_file_paths",
                return_value=["auth.py"],
            ),
            patch(
                "agents.techne.agent_executor.read_files",
                return_value={"auth.py": "code"},
            ),
            patch("agents.techne.agent_executor.get_git_context", git_context_mock),
            patch(
                "agents.techne.agent_executor.apply_code_changes",
                new_callable=AsyncMock,
                return_value=("Updated auth.py.", []),
            ),
            patch("agents.techne.agent_executor.send_working_status"),
        ):
            await executor.execute(ctx, queue)

        # parse_project_root falls back to cwd if the path doesn't exist
        # on disk, so we just assert cwd was passed (not None) — the
        # original bug was no cwd at all.
        git_context_mock.assert_called_once()
        call_kwargs = git_context_mock.call_args.kwargs
        assert "cwd" in call_kwargs
        assert call_kwargs["cwd"] is not None


class TestHephaestusExecutor:
    """Hephaestus-specific tests (orchestration, routing)."""

    @pytest.mark.asyncio
    async def test_pipeline_routes_and_completes(self):
        from agents.hephaestus.agent_executor import HephaestusAgentExecutor

        executor = HephaestusAgentExecutor()
        ctx = _make_context("implement CSV export")
        queue = _make_queue()

        async def mock_pipeline(agents, user_input, context_id=None, image_parts=None):
            yield ("metis", "Spec generated", "spec text")
            yield ("techne", "Code written", "code text")
            yield ("hephaestus", "Pipeline complete", "")

        with (
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                return_value=["metis", "techne"],
            ),
            patch(
                "agents.hephaestus.agent_executor.execute_pipeline",
                side_effect=mock_pipeline,
            ),
        ):
            await executor.execute(ctx, queue)

        assert queue.enqueue_event.call_count >= 5

    @pytest.mark.asyncio
    async def test_ask_user_returns_input_required(self):
        from agents.hephaestus.agent_executor import HephaestusAgentExecutor

        executor = HephaestusAgentExecutor()
        ctx = _make_context("do something vague")
        queue = _make_queue()

        with (
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                return_value="ASK_USER: What exactly do you want?",
            ),
        ):
            await executor.execute(ctx, queue)

        assert queue.enqueue_event.call_count >= 2

    @pytest.mark.asyncio
    async def test_input_required_from_specialist(self):
        from agents.hephaestus.agent_executor import HephaestusAgentExecutor

        executor = HephaestusAgentExecutor()
        ctx = _make_context("plan something")
        queue = _make_queue()

        async def mock_pipeline(agents, user_input, context_id=None, image_parts=None):
            yield ("metis", "INPUT_REQUIRED:Which module?", "")

        with (
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                return_value=["metis"],
            ),
            patch(
                "agents.hephaestus.agent_executor.execute_pipeline",
                side_effect=mock_pipeline,
            ),
        ):
            await executor.execute(ctx, queue)

        assert queue.enqueue_event.call_count >= 3

    @pytest.mark.asyncio
    async def test_cancel_raises_unsupported(self):
        from agents.hephaestus.agent_executor import HephaestusAgentExecutor

        executor = HephaestusAgentExecutor()
        with pytest.raises(ServerError):
            await executor.cancel(_make_context(), _make_queue())


# ── kourai_project_root_var wiring across executors ──────────────────────────


class TestExecutorsSetKouraiProjectRootVar:
    """Each specialist executor populates ``kourai_project_root_var``
    immediately after parsing ``[project_root: ...]`` from the user
    message, so an MCP server asking ``roots/list`` during the session
    receives the parsed project root via ``build_client_session``'s
    ``_kourai_list_roots`` callback.

    Strategy: replace the first downstream async call after the
    contextvar set with one that captures ``kourai_project_root_var.get()``,
    then assert the capture equals the parsed root.
    """

    @pytest.mark.asyncio
    async def test_metis_sets_var_before_get_project_context(self, tmp_path):

        from agents.metis.agent_executor import MetisAgentExecutor
        from kourai_common.mcp_client import kourai_project_root_var

        captured: list[Path | None] = []

        async def capture_var(*args: object, **kwargs: object) -> str:
            captured.append(kourai_project_root_var.get())
            return "project ctx"

        executor = MetisAgentExecutor()
        ctx = _make_context(f"[project_root: {tmp_path}]\nimplement CSV export")
        queue = _make_queue()

        token = kourai_project_root_var.set(None)
        try:
            with (
                patch("agents.metis.agent_executor.create_span"),
                patch("agents.metis.agent_executor.get_project_context", capture_var),
                patch(
                    "agents.metis.agent_executor.create_spec_stream",
                    return_value=_async_gen(["spec"]),
                ),
                patch("agents.metis.agent_executor.send_working_status"),
            ):
                await executor.execute(ctx, queue)
        finally:
            kourai_project_root_var.reset(token)

        assert captured[0] == tmp_path

    @pytest.mark.asyncio
    async def test_techne_sets_var_before_get_git_context(self, tmp_path):

        from agents.techne.agent_executor import TechneAgentExecutor
        from kourai_common.mcp_client import kourai_project_root_var

        captured: list[Path | None] = []

        async def capture_var(*args: object, **kwargs: object) -> str:
            captured.append(kourai_project_root_var.get())
            return "M auth.py"

        executor = TechneAgentExecutor()
        ctx = _make_context(f"[project_root: {tmp_path}]\nfix auth.py null check")
        queue = _make_queue()

        token = kourai_project_root_var.set(None)
        try:
            with (
                patch("agents.techne.agent_executor.create_span"),
                patch(
                    "agents.techne.agent_executor.parse_file_paths",
                    return_value=["auth.py"],
                ),
                patch(
                    "agents.techne.agent_executor.read_files",
                    return_value={"auth.py": "code"},
                ),
                patch("agents.techne.agent_executor.get_git_context", capture_var),
                patch(
                    "agents.techne.agent_executor.apply_code_changes",
                    new_callable=AsyncMock,
                    return_value=("Updated auth.py.", []),
                ),
                patch("agents.techne.agent_executor.send_working_status"),
            ):
                await executor.execute(ctx, queue)
        finally:
            kourai_project_root_var.reset(token)

        assert captured[0] == tmp_path

    @pytest.mark.asyncio
    async def test_kallos_sets_var_before_run_make_lint(self, tmp_path):

        from agents.kallos.agent_executor import KallosAgentExecutor
        from kourai_common.mcp_client import kourai_project_root_var

        captured: list[Path | None] = []

        async def capture_var(**kwargs: object) -> tuple[bool, str]:
            captured.append(kourai_project_root_var.get())
            return (True, "All checks passed")

        executor = KallosAgentExecutor()
        ctx = _make_context(f"[project_root: {tmp_path}]\nagents/kallos/agent.py")
        queue = _make_queue()

        token = kourai_project_root_var.set(None)
        try:
            with (
                patch("agents.kallos.agent_executor.create_span"),
                patch("agents.kallos.agent.run_make_lint", side_effect=capture_var),
                patch("kourai_common.subprocess.extract_files_from_output", return_value=[]),
            ):
                await executor.execute(ctx, queue)
        finally:
            kourai_project_root_var.reset(token)

        assert captured[0] == tmp_path

    @pytest.mark.asyncio
    async def test_dokimasia_sets_var_before_run_pytest(self, tmp_path):

        from agents.dokimasia.agent_executor import DokimasiaAgentExecutor
        from kourai_common.mcp_client import kourai_project_root_var

        captured: list[Path | None] = []

        def capture_var(*args: object, **kwargs: object) -> MagicMock:
            captured.append(kourai_project_root_var.get())
            result = MagicMock()
            result.success = True
            result.output = "8/8 tests passed"
            return result

        executor = DokimasiaAgentExecutor()
        ctx = _make_context(f"[project_root: {tmp_path}]\nrun tests please")
        queue = _make_queue()

        token = kourai_project_root_var.set(None)
        try:
            with (
                patch("agents.dokimasia.agent_executor.create_span"),
                patch("agents.dokimasia.agent.run_pytest", side_effect=capture_var),
                patch("kourai_common.subprocess.extract_files_from_output", return_value=[]),
            ):
                await executor.execute(ctx, queue)
        finally:
            kourai_project_root_var.reset(token)

        assert captured[0] == tmp_path
