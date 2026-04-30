"""Metis visible-recall narrator + Phase 2 telemetry attributes.

When project-scoped preference facts exist for the active project,
Metis emits a status line announcing the recall so the player sees that
her stored answer is being used instead of re-asked, AND tags the outer
``metis.execute`` OTel span with ``kourai.fact.recalled`` (bool) and
``kourai.fact.kinds`` (list[str]) for researcher-side grep. Both views
derive from the same parsed list so they can't disagree.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from agents.metis.agent_executor import _format_recall_narration
from kourai_common.messaging import user_message


async def _async_gen(items: list[str]):
    for item in items:
        yield item


def _make_context(
    user_input: str,
    context_id: str | None = None,
    *,
    metadata: dict | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.get_user_input.return_value = user_input
    ctx.current_task = None
    ctx.message = user_message(
        user_input or "placeholder",
        context_id=context_id or uuid4().hex,
        metadata=metadata,
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

        ctx = _make_context("plan a CSV exporter", metadata={"project_root": "/var/forge/proj-a"})
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

        ctx = _make_context("plan a CSV exporter", metadata={"project_root": "/var/forge/proj-a"})
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


# ── Phase 2 telemetry: span attributes on metis.execute ──────────────────


def _capture_outer_span(span_mock: MagicMock):
    """Patch helper: ``create_span("metis.execute", ...)`` yields the mock.

    Other ``create_span`` invocations inside the executor (``metis.context``,
    ``metis.spec``) yield throwaway MagicMocks so their attribute calls
    don't pollute the outer assertion.
    """
    from contextlib import contextmanager

    @contextmanager
    def _factory(name, attributes=None):
        if name == "metis.execute":
            yield span_mock
        else:
            yield MagicMock()

    return _factory


class TestExecutorSetsTelemetryAttributes:
    """``metis.execute`` carries ``kourai.fact.recalled`` + ``kourai.fact.kinds``."""

    @pytest.mark.asyncio
    async def test_recalled_true_with_kinds_when_facts_present(self):
        from agents.metis.agent_executor import MetisAgentExecutor

        outer_span = MagicMock()
        ctx = _make_context("plan a CSV exporter", metadata={"project_root": "/var/forge/proj-a"})
        queue = _make_queue()
        executor = MetisAgentExecutor()
        pinned_pid = "deadbeefdeadbeef"

        with (
            patch("agents.metis.agent_executor.create_span", _capture_outer_span(outer_span)),
            patch(
                "agents.metis.agent_executor.get_project_context",
                return_value="project ctx",
            ),
            patch(
                "agents.metis.agent_executor.create_spec_stream",
                return_value=_async_gen(["spec"]),
            ),
            patch("agents.metis.agent_executor.send_working_status", AsyncMock()),
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
                    {"body": "python_version: 3.13", "project_id": pinned_pid},
                ],
            ),
        ):
            await executor.execute(ctx, queue)

        attrs = {call.args[0]: call.args[1] for call in outer_span.set_attribute.call_args_list}
        assert attrs.get("kourai.fact.recalled") is True
        assert attrs.get("kourai.fact.kinds") == ["coverage_target", "python_version"]

    @pytest.mark.asyncio
    async def test_recalled_false_no_kinds_when_no_facts(self):
        from agents.metis.agent_executor import MetisAgentExecutor

        outer_span = MagicMock()
        ctx = _make_context("plan a CSV exporter", metadata={"project_root": "/var/forge/proj-a"})
        queue = _make_queue()
        executor = MetisAgentExecutor()

        with (
            patch("agents.metis.agent_executor.create_span", _capture_outer_span(outer_span)),
            patch(
                "agents.metis.agent_executor.get_project_context",
                return_value="project ctx",
            ),
            patch(
                "agents.metis.agent_executor.create_spec_stream",
                return_value=_async_gen(["spec"]),
            ),
            patch("agents.metis.agent_executor.send_working_status", AsyncMock()),
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

        attrs = {call.args[0]: call.args[1] for call in outer_span.set_attribute.call_args_list}
        assert attrs.get("kourai.fact.recalled") is False
        # ``kourai.fact.kinds`` should NOT be set when nothing was recalled —
        # presence of the key implies "we have a list to share."
        assert "kourai.fact.kinds" not in attrs

    @pytest.mark.asyncio
    async def test_recalled_false_when_no_project_tag(self):
        from agents.metis.agent_executor import MetisAgentExecutor

        outer_span = MagicMock()
        # No ``[project_root: ...]`` tag → project_id_for_facts is None →
        # _recalled_preferences returns []; the false attribute still fires.
        ctx = _make_context("plan a CSV exporter")
        queue = _make_queue()
        executor = MetisAgentExecutor()

        with (
            patch("agents.metis.agent_executor.create_span", _capture_outer_span(outer_span)),
            patch(
                "agents.metis.agent_executor.get_project_context",
                return_value="project ctx",
            ),
            patch(
                "agents.metis.agent_executor.create_spec_stream",
                return_value=_async_gen(["spec"]),
            ),
            patch("agents.metis.agent_executor.send_working_status", AsyncMock()),
            patch(
                "agents.metis.agent_executor._player_id_or_none",
                return_value="player-uuid",
            ),
        ):
            await executor.execute(ctx, queue)

        attrs = {call.args[0]: call.args[1] for call in outer_span.set_attribute.call_args_list}
        assert attrs.get("kourai.fact.recalled") is False
        assert "kourai.fact.kinds" not in attrs
