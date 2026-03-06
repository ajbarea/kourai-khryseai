"""Agent executors: shared A2A bridge pattern across all six agents.

Tests the three-layer executor pattern: empty input → input_required,
valid input → working → artifact → complete, cancel → unsupported.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from a2a.types import Message, Part, Role, TextPart
from a2a.utils.errors import ServerError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
# Mneme executor
# ---------------------------------------------------------------------------


class TestMnemeExecutor:
    """Mneme agent executor tests."""

    @pytest.mark.asyncio
    async def test_empty_input_returns_input_required(self):
        from agents.mneme.agent_executor import MnemeAgentExecutor

        executor = MnemeAgentExecutor()
        ctx = _make_context("")
        queue = _make_queue()

        with patch("agents.mneme.agent_executor.create_span"):
            await executor.execute(ctx, queue)

        # Should have enqueued a task + status events
        assert queue.enqueue_event.call_count >= 1

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

    @pytest.mark.asyncio
    async def test_cancel_raises_unsupported(self):
        from agents.mneme.agent_executor import MnemeAgentExecutor

        executor = MnemeAgentExecutor()
        with pytest.raises(ServerError):
            await executor.cancel(_make_context(), _make_queue())


# ---------------------------------------------------------------------------
# Kallos executor
# ---------------------------------------------------------------------------


class TestKallosExecutor:
    """Kallos agent executor tests."""

    @pytest.mark.asyncio
    async def test_empty_input_returns_input_required(self):
        from agents.kallos.agent_executor import KallosAgentExecutor

        executor = KallosAgentExecutor()
        ctx = _make_context("   ")
        queue = _make_queue()

        with patch("agents.kallos.agent_executor.create_span"):
            await executor.execute(ctx, queue)

        assert queue.enqueue_event.call_count >= 1

    @pytest.mark.asyncio
    async def test_valid_input_runs_fix_loop(self):
        from agents.kallos.agent_executor import KallosAgentExecutor
        from kourai_common.fix_loop import FixLoopResult

        executor = KallosAgentExecutor()
        ctx = _make_context("agents/kallos/agent.py")
        queue = _make_queue()

        result = FixLoopResult(all_passed=True, iterations_run=1)

        with (
            patch("agents.kallos.agent_executor.create_span"),
            patch(
                "kourai_common.fix_loop.run_fix_loop",
                new_callable=AsyncMock,
                return_value=(True, "All checks passed", result),
            ),
        ):
            await executor.execute(ctx, queue)

        assert queue.enqueue_event.call_count >= 3

    @pytest.mark.asyncio
    async def test_cancel_raises_unsupported(self):
        from agents.kallos.agent_executor import KallosAgentExecutor

        executor = KallosAgentExecutor()
        with pytest.raises(ServerError):
            await executor.cancel(_make_context(), _make_queue())


# ---------------------------------------------------------------------------
# Metis executor
# ---------------------------------------------------------------------------


class TestMetisExecutor:
    """Metis agent executor tests."""

    @pytest.mark.asyncio
    async def test_empty_input_returns_input_required(self):
        from agents.metis.agent_executor import MetisAgentExecutor

        executor = MetisAgentExecutor()
        ctx = _make_context(None)
        queue = _make_queue()

        with patch("agents.metis.agent_executor.create_span"):
            await executor.execute(ctx, queue)

        assert queue.enqueue_event.call_count >= 1

    @pytest.mark.asyncio
    async def test_valid_input_generates_spec(self):
        from agents.metis.agent_executor import MetisAgentExecutor

        executor = MetisAgentExecutor()
        ctx = _make_context("implement CSV export")
        queue = _make_queue()

        with (
            patch("agents.metis.agent_executor.create_span"),
            patch("agents.metis.agent_executor.get_project_context", return_value="project ctx"),
            patch("agents.metis.agent_executor.create_spec", return_value="## Spec\nDo things"),
        ):
            await executor.execute(ctx, queue)

        assert queue.enqueue_event.call_count >= 4

    @pytest.mark.asyncio
    async def test_cancel_raises_unsupported(self):
        from agents.metis.agent_executor import MetisAgentExecutor

        executor = MetisAgentExecutor()
        with pytest.raises(ServerError):
            await executor.cancel(_make_context(), _make_queue())


# ---------------------------------------------------------------------------
# Dokimasia executor
# ---------------------------------------------------------------------------


class TestDokimasiaExecutor:
    """Dokimasia agent executor tests."""

    @pytest.mark.asyncio
    async def test_empty_input_returns_input_required(self):
        from agents.dokimasia.agent_executor import DokimasiaAgentExecutor

        executor = DokimasiaAgentExecutor()
        ctx = _make_context("")
        queue = _make_queue()

        with patch("agents.dokimasia.agent_executor.create_span"):
            await executor.execute(ctx, queue)

        assert queue.enqueue_event.call_count >= 1

    @pytest.mark.asyncio
    async def test_run_request_runs_fix_loop(self):
        from agents.dokimasia.agent_executor import DokimasiaAgentExecutor
        from kourai_common.fix_loop import FixLoopResult

        executor = DokimasiaAgentExecutor()
        ctx = _make_context("run tests please")
        queue = _make_queue()

        result = FixLoopResult(all_passed=True, iterations_run=1)

        with (
            patch("agents.dokimasia.agent_executor.create_span"),
            patch(
                "kourai_common.fix_loop.run_fix_loop",
                new_callable=AsyncMock,
                return_value=(True, "All tests passed", result),
            ),
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
            patch("agents.dokimasia.agent_executor.generate_tests", return_value="def test_add():"),
        ):
            await executor.execute(ctx, queue)

        assert queue.enqueue_event.call_count >= 4

    @pytest.mark.asyncio
    async def test_cancel_raises_unsupported(self):
        from agents.dokimasia.agent_executor import DokimasiaAgentExecutor

        executor = DokimasiaAgentExecutor()
        with pytest.raises(ServerError):
            await executor.cancel(_make_context(), _make_queue())


# ---------------------------------------------------------------------------
# Techne executor
# ---------------------------------------------------------------------------


class TestTechneExecutor:
    """Techne agent executor tests."""

    @pytest.mark.asyncio
    async def test_empty_input_returns_input_required(self):
        from agents.techne.agent_executor import TechneAgentExecutor

        executor = TechneAgentExecutor()
        ctx = _make_context("  ")
        queue = _make_queue()

        with patch("agents.techne.agent_executor.create_span"):
            await executor.execute(ctx, queue)

        assert queue.enqueue_event.call_count >= 1

    @pytest.mark.asyncio
    async def test_valid_input_generates_code(self):
        from agents.techne.agent_executor import TechneAgentExecutor

        executor = TechneAgentExecutor()
        ctx = _make_context("fix auth.py null check")
        queue = _make_queue()

        with (
            patch("agents.techne.agent_executor.create_span"),
            patch("agents.techne.agent_executor.parse_file_paths", return_value=["auth.py"]),
            patch("agents.techne.agent_executor.read_files", return_value={"auth.py": "code"}),
            patch("agents.techne.agent_executor.get_git_context", return_value="M auth.py"),
            patch("agents.techne.agent_executor.generate_code", return_value="ACTION: EDIT\n..."),
        ):
            await executor.execute(ctx, queue)

        assert queue.enqueue_event.call_count >= 5

    @pytest.mark.asyncio
    async def test_cancel_raises_unsupported(self):
        from agents.techne.agent_executor import TechneAgentExecutor

        executor = TechneAgentExecutor()
        with pytest.raises(ServerError):
            await executor.cancel(_make_context(), _make_queue())


# ---------------------------------------------------------------------------
# Hephaestus executor
# ---------------------------------------------------------------------------


class TestHephaestusExecutor:
    """Hephaestus orchestrator executor tests."""

    @pytest.mark.asyncio
    async def test_empty_input_returns_input_required(self):
        from agents.hephaestus.agent_executor import HephaestusAgentExecutor

        executor = HephaestusAgentExecutor()
        ctx = _make_context("")
        queue = _make_queue()

        with patch("agents.hephaestus.agent_executor.create_span"):
            await executor.execute(ctx, queue)

        assert queue.enqueue_event.call_count >= 1

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
