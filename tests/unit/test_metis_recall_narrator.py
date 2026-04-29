"""Metis visible-recall narrator (M17 Phase 2).

When project-scoped preference facts exist for the active project,
Metis emits a status line announcing the recall so the player sees that
her stored answer is being used instead of re-asked. Free-form
``<FACT>`` observations and globals don't narrate.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from a2a.types import Message, Part, Role, TextPart

from agents.metis.agent_executor import _format_recall_narration


async def _async_gen(items: list[str]):
    for item in items:
        yield item


def _make_context(user_input: str, context_id: str | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.get_user_input.return_value = user_input
    ctx.current_task = None
    ctx.message = Message(
        role=Role.user,
        parts=[Part(root=TextPart(text=user_input or "placeholder"))],
        message_id=str(uuid4()),
        context_id=context_id or uuid4().hex,
    )
    return ctx


def _make_queue() -> AsyncMock:
    return AsyncMock()


# ── Pure helper ──────────────────────────────────────────────────────────


class TestFormatRecallNarration:
    def test_returns_none_without_player_id(self):
        assert _format_recall_narration(None, "abc123def4567890") is None

    def test_returns_none_without_project_id(self):
        assert _format_recall_narration("player-uuid", None) is None

    def test_returns_none_when_no_facts(self):
        with patch(
            "agents.metis.agent_executor.get_relevant_facts_for_enrichment",
            return_value=[],
        ):
            assert _format_recall_narration("player-uuid", "abc123def4567890") is None

    def test_returns_none_when_only_global_facts(self):
        with patch(
            "agents.metis.agent_executor.get_relevant_facts_for_enrichment",
            return_value=[
                {"body": "coverage_target: 80%", "project_id": None},
            ],
        ):
            assert _format_recall_narration("player-uuid", "abc123def4567890") is None

    def test_returns_none_when_only_off_vocab_facts(self):
        with patch(
            "agents.metis.agent_executor.get_relevant_facts_for_enrichment",
            return_value=[
                {"body": "favourite_colour: blue", "project_id": "abc123def4567890"},
            ],
        ):
            assert _format_recall_narration("player-uuid", "abc123def4567890") is None

    def test_skips_freeform_fact_bodies(self):
        with patch(
            "agents.metis.agent_executor.get_relevant_facts_for_enrichment",
            return_value=[
                # ``<FACT category="skill">Knows React well</FACT>`` shape — no kind:value
                {"body": "Knows React well", "project_id": "abc123def4567890"},
            ],
        ):
            assert _format_recall_narration("player-uuid", "abc123def4567890") is None

    def test_single_fact_renders_dedicated_phrasing(self):
        with patch(
            "agents.metis.agent_executor.get_relevant_facts_for_enrichment",
            return_value=[
                {"body": "coverage_target: 80%", "project_id": "abc123def4567890"},
            ],
        ):
            line = _format_recall_narration("player-uuid", "abc123def4567890")
        assert line == "Using your stored coverage_target (80%)."

    def test_many_facts_render_summary(self):
        with patch(
            "agents.metis.agent_executor.get_relevant_facts_for_enrichment",
            return_value=[
                {"body": "coverage_target: 80%", "project_id": "abc123def4567890"},
                {"body": "python_version: 3.13", "project_id": "abc123def4567890"},
            ],
        ):
            line = _format_recall_narration("player-uuid", "abc123def4567890")
        assert line is not None
        assert line.startswith("Using your stored project preferences:")
        assert "coverage_target (80%)" in line
        assert "python_version (3.13)" in line

    def test_skips_empty_value(self):
        with patch(
            "agents.metis.agent_executor.get_relevant_facts_for_enrichment",
            return_value=[
                {"body": "coverage_target: ", "project_id": "abc123def4567890"},
            ],
        ):
            assert _format_recall_narration("player-uuid", "abc123def4567890") is None


# ── Executor integration ─────────────────────────────────────────────────


class TestExecutorEmitsRecallNarration:
    @pytest.mark.asyncio
    async def test_emits_status_when_recall_present(self):
        from agents.metis.agent_executor import MetisAgentExecutor

        ctx = _make_context("[project_root: /var/forge/proj-a]\nplan a CSV exporter")
        queue = _make_queue()
        executor = MetisAgentExecutor()

        # derive_project_id is patched to a known value so the
        # narrator's project_id == fact's project_id check passes
        # regardless of where the test runs.
        pinned_pid = "deadbeefdeadbeef"

        send_working_status = AsyncMock()
        with (
            patch("agents.metis.agent_executor.create_span"),
            patch(
                "agents.metis.agent_executor.get_project_context",
                return_value="project ctx",
            ),
            patch(
                "agents.metis.agent_executor.create_spec_stream",
                return_value=_async_gen(["spec"]),
            ),
            patch(
                "agents.metis.agent_executor.send_working_status",
                send_working_status,
            ),
            patch(
                "agents.metis.agent_executor._player_id_or_none",
                return_value="player-uuid",
            ),
            patch(
                "agents.metis.agent_executor.derive_project_id",
                return_value=pinned_pid,
            ),
            patch(
                "agents.metis.agent_executor.get_relevant_facts_for_enrichment",
                return_value=[
                    {"body": "coverage_target: 80%", "project_id": pinned_pid},
                ],
            ),
        ):
            await executor.execute(ctx, queue)

        recall_calls = [
            call
            for call in send_working_status.await_args_list
            if "Using your stored coverage_target" in call.args[2]
        ]
        assert len(recall_calls) == 1, "expected exactly one recall narration"

    @pytest.mark.asyncio
    async def test_no_status_when_no_facts(self):
        from agents.metis.agent_executor import MetisAgentExecutor

        ctx = _make_context("[project_root: /var/forge/proj-a]\nplan a CSV exporter")
        queue = _make_queue()
        executor = MetisAgentExecutor()

        send_working_status = AsyncMock()
        with (
            patch("agents.metis.agent_executor.create_span"),
            patch(
                "agents.metis.agent_executor.get_project_context",
                return_value="project ctx",
            ),
            patch(
                "agents.metis.agent_executor.create_spec_stream",
                return_value=_async_gen(["spec"]),
            ),
            patch(
                "agents.metis.agent_executor.send_working_status",
                send_working_status,
            ),
            patch(
                "agents.metis.agent_executor._player_id_or_none",
                return_value="player-uuid",
            ),
            patch(
                "agents.metis.agent_executor.get_relevant_facts_for_enrichment",
                return_value=[],
            ),
        ):
            await executor.execute(ctx, queue)

        recall_calls = [
            call
            for call in send_working_status.await_args_list
            if "Using your stored" in call.args[2]
        ]
        assert recall_calls == []

    @pytest.mark.asyncio
    async def test_no_status_when_no_project_tag(self):
        from agents.metis.agent_executor import MetisAgentExecutor

        # No [project_root: ...] tag → project_id_for_facts is None → narration skipped.
        ctx = _make_context("plan a CSV exporter")
        queue = _make_queue()
        executor = MetisAgentExecutor()

        send_working_status = AsyncMock()
        with (
            patch("agents.metis.agent_executor.create_span"),
            patch(
                "agents.metis.agent_executor.get_project_context",
                return_value="project ctx",
            ),
            patch(
                "agents.metis.agent_executor.create_spec_stream",
                return_value=_async_gen(["spec"]),
            ),
            patch(
                "agents.metis.agent_executor.send_working_status",
                send_working_status,
            ),
            patch(
                "agents.metis.agent_executor._player_id_or_none",
                return_value="player-uuid",
            ),
            patch(
                "agents.metis.agent_executor.get_relevant_facts_for_enrichment",
                return_value=[
                    {"body": "coverage_target: 80%", "project_id": "abc123def4567890"},
                ],
            ),
        ):
            await executor.execute(ctx, queue)

        recall_calls = [
            call
            for call in send_working_status.await_args_list
            if "Using your stored" in call.args[2]
        ]
        assert recall_calls == []
