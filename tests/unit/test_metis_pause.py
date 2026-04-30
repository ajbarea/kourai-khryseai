"""Metis HOTL PAUSE token handling (M17 Phase 1).

Covers the prompt-side instruction set, the executor's pause path that
parses ``PAUSE: <kind> "<question>"`` and stashes the classification
keyed by ``context_id``, and the negative path where the LLM omits the
token.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from agents.metis.agent import SYSTEM_PROMPT
from kourai_common.messaging import user_message
from kourai_common.pause_state import (
    clear,
    peek_preference_kind,
    pop_preference_kind,
    stash_preference_kind,
)


@pytest.fixture(autouse=True)
def _isolated_stash():
    clear()
    yield
    clear()


async def _async_gen(items: list[str]):
    for item in items:
        yield item


def _make_context(user_input: str, context_id: str | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.get_user_input.return_value = user_input
    ctx.current_task = None
    ctx.message = user_message(
        user_input or "placeholder",
        context_id=context_id or uuid4().hex,
    )
    return ctx


def _make_queue() -> AsyncMock:
    return AsyncMock()


class TestSystemPromptCarriesPauseInstructions:
    """Prompt-side audit — Metis must know the M17 token shape and vocab."""

    def test_prompt_documents_pause_token_shape(self):
        assert "PAUSE:" in SYSTEM_PROMPT
        assert "preference_kind" in SYSTEM_PROMPT

    def test_prompt_lists_phase_one_vocabulary(self):
        for kind in (
            "coverage_target",
            "python_version",
            "style_rules",
            "commit_style",
            "test_framework",
        ):
            assert kind in SYSTEM_PROMPT, (
                f"closed vocabulary kind {kind!r} missing from Metis system prompt"
            )

    def test_prompt_caps_pause_count(self):
        assert "AT MOST ONE PAUSE" in SYSTEM_PROMPT

    def test_prompt_warns_against_redundant_pause(self):
        assert "PLAYER CONTEXT" in SYSTEM_PROMPT


class TestExecutorPausePath:
    """Pause path: LLM emits PAUSE → executor stashes kind + sends input_required."""

    @pytest.mark.asyncio
    async def test_pause_tag_stashes_kind_and_sends_input_required(self):
        from agents.metis.agent_executor import MetisAgentExecutor

        ctx_id = "ctx-pause-1"
        ctx = _make_context("plan a CSV exporter", context_id=ctx_id)
        queue = _make_queue()
        executor = MetisAgentExecutor()

        spec_chunks = [
            "1. Summary — stream chunked CSV.\n",
            "2. Files to Modify — src/export.py.\n",
            'PAUSE: coverage_target "What test coverage target should I plan for?"',
        ]
        send_input_required = AsyncMock()
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
            patch(
                "agents.metis.agent_executor.send_input_required",
                send_input_required,
            ),
        ):
            await executor.execute(ctx, queue)

        send_input_required.assert_awaited_once()
        assert send_input_required.await_args is not None
        question = send_input_required.await_args.args[2]
        assert question == "What test coverage target should I plan for?"

        pending = pop_preference_kind(ctx.message.context_id)
        assert pending is not None
        assert pending.preference_kind == "coverage_target"
        assert pending.source_agent == "metis"

    @pytest.mark.asyncio
    async def test_no_pause_tag_completes_normally_without_stash(self):
        from agents.metis.agent_executor import MetisAgentExecutor

        ctx = _make_context("plan a CSV exporter")
        queue = _make_queue()
        executor = MetisAgentExecutor()

        spec_chunks = [
            "1. Summary — stream chunked CSV.\n",
            "2. Files to Modify — src/export.py.\n",
            "3. Implementation Steps — read with iterator.\n",
        ]
        send_input_required = AsyncMock()
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
            patch(
                "agents.metis.agent_executor.send_input_required",
                send_input_required,
            ),
        ):
            await executor.execute(ctx, queue)

        send_input_required.assert_not_awaited()
        assert peek_preference_kind(ctx.message.context_id) is None

    @pytest.mark.asyncio
    async def test_pause_tag_strips_token_from_artifact_text(self):
        from agents.metis.agent_executor import MetisAgentExecutor

        ctx = _make_context("plan a CSV exporter")
        queue = _make_queue()
        executor = MetisAgentExecutor()

        spec_chunks = [
            "1. Summary — stream chunked CSV.\n",
            "2. Files to Modify — src/export.py.\n",
            'PAUSE: python_version "Python 3.12 or 3.13?"',
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
            patch("agents.metis.agent_executor.send_input_required", AsyncMock()),
        ):
            await executor.execute(ctx, queue)

        [call for call in queue.enqueue_event.call_args_list if hasattr(call.args[0], "id")]
        # The TaskUpdater sends the artifact via update_status / add_artifact —
        # what we care about is that "PAUSE:" never lands in any text part.
        assert any(queue.enqueue_event.call_args_list)  # sanity — events were emitted
        # No event payload should carry the PAUSE: marker.
        for call in queue.enqueue_event.call_args_list:
            event = call.args[0]
            text = repr(event)
            assert "PAUSE:" not in text, f"PAUSE token leaked into event: {text!r}"

    @pytest.mark.asyncio
    async def test_unknown_pause_kind_falls_through_to_normal_completion(self):
        """Garbage classification is dropped — better silent ship than poisoned graph."""
        from agents.metis.agent_executor import MetisAgentExecutor

        ctx = _make_context("plan a CSV exporter")
        queue = _make_queue()
        executor = MetisAgentExecutor()

        spec_chunks = [
            "1. Summary — refactor.\n",
            'PAUSE: favourite_colour "Blue?"',
        ]
        send_input_required = AsyncMock()
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
            patch(
                "agents.metis.agent_executor.send_input_required",
                send_input_required,
            ),
        ):
            # No need to assert previously stashed state — fixture cleared it
            stash_preference_kind("unrelated-context", "coverage_target")
            await executor.execute(ctx, queue)

        send_input_required.assert_not_awaited()
        # The unrelated stash is still intact (fixture-scope only)
        assert peek_preference_kind("unrelated-context") is not None
