"""M14 — Metis-First Parallel Routing (the dead-zone fix).

Hephaestus's executor spawns Metis's ``discuss_tradeoffs`` as a
parallel asyncio task before awaiting ``determine_pipeline``. Output
is buffered and only emitted to the player on tier-2 (smart) and
tier-3 (clarify) confirmations — every other route cancels her work
silently. ``[yolo:`` in the input skips Metis entirely.

These tests cover:

1. ``discuss_tradeoffs`` itself — calls Metis at the active model
   tier with the right prompt shape (1-2 paragraphs, discussion mode).
2. Parallel dispatch — Metis starts BEFORE the classifier completes
   (asyncio.gather-style timing).
3. Cancellation matrix — what happens to Metis on each route.
4. Surfacing — Metis's output appears as a 📐 status event on tier
   2/3, doesn't appear on tier 1 / yolo / CHAT / ASK_USER.

The harder "T8" — feeding Metis's partial output back into the
classifier prompt to enrich the tier-2 read-back — is deferred. See
plans/2026-04-26-forge-order-confirmation.md.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# discuss_tradeoffs — the agent.py entry point
# ---------------------------------------------------------------------------


class TestDiscussTradeoffs:
    @pytest.mark.asyncio
    async def test_returns_chat_response_text(self):
        from agents.metis.agent import discuss_tradeoffs

        with patch(
            "agents.metis.agent.chat",
            new_callable=AsyncMock,
            return_value=(
                '"Architectural concerns: zero-division on b=0; type '
                'coercion if you accept floats. Light it?"'
            ),
        ):
            result = await discuss_tradeoffs("add a divide function")

        assert "zero-division" in result
        assert result.startswith('"')  # M10 — Metis quotes player-directed speech

    @pytest.mark.asyncio
    async def test_runs_at_metis_agent_tier(self):
        # The chat call goes through agents.metis.agent (not direct
        # litellm) so MODEL_TIER + agent_name resolve to whatever Metis
        # is configured for in config.py. We don't pin "cheap" here —
        # noted in the agent.py docstring as a future optimization.
        from agents.metis.agent import discuss_tradeoffs

        captured: dict = {}

        async def capture_chat(agent_name, messages, **kwargs):
            captured["agent_name"] = agent_name
            captured["messages"] = messages
            captured["kwargs"] = kwargs
            return "ok"

        with patch("agents.metis.agent.chat", side_effect=capture_chat):
            await discuss_tradeoffs("add divide")

        assert captured["agent_name"] == "metis"

    @pytest.mark.asyncio
    async def test_system_prompt_includes_discussion_mode_marker(self):
        # The discussion-mode marker tells the LLM "1-2 paragraphs, not
        # a full spec" — without it, Metis would emit a 6-section
        # implementation spec into the gate-pause window.
        from agents.metis.agent import discuss_tradeoffs

        captured: dict = {}

        async def capture_chat(agent_name, messages, **kwargs):
            captured["messages"] = messages
            return "ok"

        with patch("agents.metis.agent.chat", side_effect=capture_chat):
            await discuss_tradeoffs("add divide")

        system_msg = next(m for m in captured["messages"] if m["role"] == "system")
        assert "DISCUSSION MODE" in system_msg["content"]

    @pytest.mark.asyncio
    async def test_max_tokens_is_modest(self):
        # 1-2 paragraphs is the contract — guard against future drift
        # toward "Metis writes the whole spec during the gate".
        from agents.metis.agent import discuss_tradeoffs

        captured: dict = {}

        async def capture_chat(agent_name, messages, **kwargs):
            captured["kwargs"] = kwargs
            return "ok"

        with patch("agents.metis.agent.chat", side_effect=capture_chat):
            await discuss_tradeoffs("add divide")

        # 400 today; cap at 800 so a future "let me give a few more
        # paragraphs" tweak stays bounded.
        assert captured["kwargs"]["max_tokens"] <= 800


# ---------------------------------------------------------------------------
# Cancellation matrix — what happens to Metis on each route
# ---------------------------------------------------------------------------


def _make_executor_ctx_task_updater():
    """Common scaffolding for executor tests."""
    from agents.hephaestus.agent_executor import HephaestusAgentExecutor

    executor = HephaestusAgentExecutor()
    ctx = MagicMock()
    task = MagicMock()
    task.context_id = "ctx-1"
    task.id = "task-1"
    updater = MagicMock()
    updater.add_artifact = AsyncMock()
    updater.complete = AsyncMock()
    updater.update_status = AsyncMock()
    return executor, ctx, task, updater


class TestParallelDispatch:
    """Metis's discuss_tradeoffs starts BEFORE the classifier completes."""

    @pytest.mark.asyncio
    async def test_metis_spawned_before_classifier_awaited(self):
        executor, ctx, task, updater = _make_executor_ctx_task_updater()
        ctx.get_user_input.return_value = "add divide"

        # Track timing — Metis's start time should precede the
        # classifier's completion.
        timeline: list[tuple[str, float]] = []

        async def slow_classifier(*args, **kwargs):
            timeline.append(("classifier_start", asyncio.get_event_loop().time()))
            await asyncio.sleep(0.05)
            timeline.append(("classifier_end", asyncio.get_event_loop().time()))
            return 'CONFIRM_ORDER: smart "tradeoffs?"'

        async def metis_discuss(*args, **kwargs):
            timeline.append(("metis_start", asyncio.get_event_loop().time()))
            await asyncio.sleep(0.03)
            timeline.append(("metis_end", asyncio.get_event_loop().time()))
            return "Metis's notes."

        with (
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                side_effect=slow_classifier,
            ),
            patch(
                "agents.hephaestus.agent_executor.discuss_tradeoffs",
                side_effect=metis_discuss,
            ),
            patch("agents.hephaestus.agent_executor.send_input_required", new_callable=AsyncMock),
            patch("agents.hephaestus.agent_executor.send_working_status", new_callable=AsyncMock),
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.PlayerProfile.load",
                return_value=None,
            ),
        ):
            await executor.execute_agent_logic(ctx, task, updater)

        # Both started, both completed
        starts = sorted(t for name, t in timeline if name.endswith("_start"))
        # Parallel: both starts within 50ms of each other (event-loop
        # tick budget). Sequential would be classifier_end before
        # metis_start.
        assert len(starts) == 2
        assert starts[1] - starts[0] < 0.05


class TestCancellationMatrix:
    """What happens to Metis's task on each routing decision.

    Each test spies on ``_cancel_metis`` rather than trying to observe
    the cancellation from inside the patched ``discuss_tradeoffs``. The
    task may be cancelled before it ever schedules (mocked classifier
    returns instantly), in which case the function body never runs and
    an inner ``try/except CancelledError`` never sees anything. The
    behavior we actually care about is "did the executor call cancel
    on the task" and that's what the spy verifies.
    """

    @pytest.mark.asyncio
    async def test_chat_route_cancels_metis(self):
        executor, ctx, task, updater = _make_executor_ctx_task_updater()
        ctx.get_user_input.return_value = "hi"

        async def slow_metis(*args, **kwargs):
            await asyncio.sleep(10)
            return "should not reach"

        cancel_calls: list = []
        original_cancel = executor._cancel_metis

        async def spy_cancel(metis_task):
            cancel_calls.append(metis_task)
            await original_cancel(metis_task)

        with (
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                new_callable=AsyncMock,
                return_value='CHAT: "hello"',
            ),
            patch(
                "agents.hephaestus.agent_executor.discuss_tradeoffs",
                side_effect=slow_metis,
            ),
            patch.object(executor, "_cancel_metis", side_effect=spy_cancel),
            patch("agents.hephaestus.agent_executor.send_working_status", new_callable=AsyncMock),
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.PlayerProfile.load",
                return_value=None,
            ),
            patch(
                "agents.hephaestus.agent_executor.update_affinity",
                return_value=0.5,
            ),
            patch("agents.hephaestus.agent_executor.get_affinity_tier", return_value=2),
        ):
            await executor.execute_agent_logic(ctx, task, updater)

        # _cancel_metis was called with a non-None task — the executor
        # took the cancel path on the CHAT route.
        assert len(cancel_calls) == 1
        assert cancel_calls[0] is not None

    @pytest.mark.asyncio
    async def test_ask_user_route_cancels_metis(self):
        executor, ctx, task, updater = _make_executor_ctx_task_updater()
        ctx.get_user_input.return_value = "do something"

        async def slow_metis(*args, **kwargs):
            await asyncio.sleep(10)

        cancel_calls: list = []
        original_cancel = executor._cancel_metis

        async def spy_cancel(metis_task):
            cancel_calls.append(metis_task)
            await original_cancel(metis_task)

        with (
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                new_callable=AsyncMock,
                return_value="ASK_USER: What exactly?",
            ),
            patch(
                "agents.hephaestus.agent_executor.discuss_tradeoffs",
                side_effect=slow_metis,
            ),
            patch.object(executor, "_cancel_metis", side_effect=spy_cancel),
            patch("agents.hephaestus.agent_executor.send_working_status", new_callable=AsyncMock),
            patch("agents.hephaestus.agent_executor.send_input_required", new_callable=AsyncMock),
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.PlayerProfile.load",
                return_value=None,
            ),
        ):
            await executor.execute_agent_logic(ctx, task, updater)

        assert len(cancel_calls) == 1
        assert cancel_calls[0] is not None

    @pytest.mark.asyncio
    async def test_confirm_order_clear_tier_cancels_metis(self):
        # On clear-tier confirmations the player just wants to ship —
        # surfacing Metis's discussion would be friction. Drop it.
        executor, ctx, task, updater = _make_executor_ctx_task_updater()
        ctx.get_user_input.return_value = "add double(n)"

        async def slow_metis(*args, **kwargs):
            await asyncio.sleep(10)

        cancel_calls: list = []
        original_cancel = executor._cancel_metis

        async def spy_cancel(metis_task):
            cancel_calls.append(metis_task)
            await original_cancel(metis_task)

        with (
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                new_callable=AsyncMock,
                return_value='CONFIRM_ORDER: clear "double(n)? Light?"',
            ),
            patch(
                "agents.hephaestus.agent_executor.discuss_tradeoffs",
                side_effect=slow_metis,
            ),
            patch.object(executor, "_cancel_metis", side_effect=spy_cancel),
            patch("agents.hephaestus.agent_executor.send_working_status", new_callable=AsyncMock),
            patch("agents.hephaestus.agent_executor.send_input_required", new_callable=AsyncMock),
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.PlayerProfile.load",
                return_value=None,
            ),
        ):
            await executor.execute_agent_logic(ctx, task, updater)

        assert len(cancel_calls) == 1
        assert cancel_calls[0] is not None

    @pytest.mark.asyncio
    async def test_yolo_skips_metis_entirely(self):
        # /yolo opt-out means the player wants the pipeline straight
        # away — Metis shouldn't even spawn.
        executor, ctx, task, updater = _make_executor_ctx_task_updater()
        ctx.get_user_input.return_value = "[yolo: on]\nadd a function"

        metis_called = False

        async def metis_discuss(*args, **kwargs):
            nonlocal metis_called
            metis_called = True
            return "should not be called"

        async def fake_pipeline(*args, **kwargs):
            yield ("metis", "spec done", "the spec")
            yield ("hephaestus", "Pipeline complete", "")

        with (
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                new_callable=AsyncMock,
                return_value=["metis"],
            ),
            patch(
                "agents.hephaestus.agent_executor.discuss_tradeoffs",
                side_effect=metis_discuss,
            ),
            patch(
                "agents.hephaestus.agent_executor.execute_pipeline",
                side_effect=fake_pipeline,
            ),
            patch(
                "agents.hephaestus.agent_executor.extract_file_attachments",
                return_value=[],
            ),
            patch("agents.hephaestus.agent_executor.send_working_status", new_callable=AsyncMock),
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.PlayerProfile.load",
                return_value=None,
            ),
        ):
            await executor.execute_agent_logic(ctx, task, updater)

        # Skip the entire spawn path on yolo — even cheap
        # tier-haiku Metis costs are wasted token spend if the player
        # already explicitly opted out of the gate.
        assert metis_called is False


# ---------------------------------------------------------------------------
# Surfacing — Metis's output appears on tier 2/3 only
# ---------------------------------------------------------------------------


class TestSurfacing:
    @pytest.mark.asyncio
    async def test_smart_tier_emits_metis_with_metis_emoji(self):
        executor, ctx, task, updater = _make_executor_ctx_task_updater()
        ctx.get_user_input.return_value = "add divide"

        metis_text = (
            '"Architectural concerns: zero-division on b=0; type coercion if you accept floats."'
        )

        send_working_calls: list = []

        async def fake_send_working_status(updater, task, message, emoji="⚙️"):
            send_working_calls.append((message, emoji))

        with (
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                new_callable=AsyncMock,
                return_value='CONFIRM_ORDER: smart "divide(a, b). Bare or works?"',
            ),
            patch(
                "agents.hephaestus.agent_executor.discuss_tradeoffs",
                new_callable=AsyncMock,
                return_value=metis_text,
            ),
            patch(
                "agents.hephaestus.agent_executor.send_working_status",
                side_effect=fake_send_working_status,
            ),
            patch("agents.hephaestus.agent_executor.send_input_required", new_callable=AsyncMock),
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.PlayerProfile.load",
                return_value=None,
            ),
        ):
            await executor.execute_agent_logic(ctx, task, updater)

        # The Metis call should be one of the working_status events,
        # tagged with the Metis emoji (📐 = \U0001f4d0) so the host's
        # _maidenify_status renders it as a Metis comms window.
        metis_calls = [(msg, emoji) for msg, emoji in send_working_calls if emoji == "\U0001f4d0"]
        assert len(metis_calls) == 1
        assert "Architectural concerns" in metis_calls[0][0]

    @pytest.mark.asyncio
    async def test_clarify_tier_also_emits_metis(self):
        executor, ctx, task, updater = _make_executor_ctx_task_updater()
        ctx.get_user_input.return_value = "make it faster"

        send_working_calls: list = []

        async def fake_send_working_status(updater, task, message, emoji="⚙️"):
            send_working_calls.append((message, emoji))

        with (
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                new_callable=AsyncMock,
                return_value='CONFIRM_ORDER: clarify "Which functions?"',
            ),
            patch(
                "agents.hephaestus.agent_executor.discuss_tradeoffs",
                new_callable=AsyncMock,
                return_value="Metis: which subsystem do you mean?",
            ),
            patch(
                "agents.hephaestus.agent_executor.send_working_status",
                side_effect=fake_send_working_status,
            ),
            patch("agents.hephaestus.agent_executor.send_input_required", new_callable=AsyncMock),
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.PlayerProfile.load",
                return_value=None,
            ),
        ):
            await executor.execute_agent_logic(ctx, task, updater)

        metis_calls = [(msg, emoji) for msg, emoji in send_working_calls if emoji == "\U0001f4d0"]
        assert len(metis_calls) == 1

    @pytest.mark.asyncio
    async def test_clear_tier_does_not_emit_metis(self):
        executor, ctx, task, updater = _make_executor_ctx_task_updater()
        ctx.get_user_input.return_value = "add x"

        send_working_calls: list = []

        async def fake_send_working_status(updater, task, message, emoji="⚙️"):
            send_working_calls.append((message, emoji))

        with (
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                new_callable=AsyncMock,
                return_value='CONFIRM_ORDER: clear "x?"',
            ),
            patch(
                "agents.hephaestus.agent_executor.discuss_tradeoffs",
                new_callable=AsyncMock,
                return_value="Metis would say something here.",
            ),
            patch(
                "agents.hephaestus.agent_executor.send_working_status",
                side_effect=fake_send_working_status,
            ),
            patch("agents.hephaestus.agent_executor.send_input_required", new_callable=AsyncMock),
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.PlayerProfile.load",
                return_value=None,
            ),
        ):
            await executor.execute_agent_logic(ctx, task, updater)

        # NO Metis-tagged call on clear tier — she stays silent.
        metis_calls = [(msg, emoji) for msg, emoji in send_working_calls if emoji == "\U0001f4d0"]
        assert metis_calls == []

    @pytest.mark.asyncio
    async def test_metis_timeout_does_not_block_confirmation(self):
        # If Metis's call drags past the deadline, drop her contribution
        # and ship the confirmation card alone. Player never waits longer
        # than the classifier required.
        executor, ctx, task, updater = _make_executor_ctx_task_updater()
        ctx.get_user_input.return_value = "add divide"

        async def slow_metis(*args, **kwargs):
            await asyncio.sleep(20)
            return "never reaches"

        send_input_calls: list = []

        async def fake_send_input_required(updater, task, message):
            send_input_calls.append(message)

        async def quick_emit(metis_task, updater, task, deadline_seconds=0.05):
            # Override deadline so the test isn't actually waiting 8 seconds.
            await executor.__class__._await_and_emit_metis(
                executor,
                metis_task,
                updater,
                task,
                deadline_seconds=0.05,
            )

        with (
            patch(
                "agents.hephaestus.agent_executor.determine_pipeline",
                new_callable=AsyncMock,
                return_value='CONFIRM_ORDER: smart "divide?"',
            ),
            patch(
                "agents.hephaestus.agent_executor.discuss_tradeoffs",
                side_effect=slow_metis,
            ),
            patch("agents.hephaestus.agent_executor.send_working_status", new_callable=AsyncMock),
            patch(
                "agents.hephaestus.agent_executor.send_input_required",
                side_effect=fake_send_input_required,
            ),
            patch("agents.hephaestus.agent_executor.create_span"),
            patch(
                "agents.hephaestus.agent_executor.PlayerProfile.load",
                return_value=None,
            ),
            patch.object(executor, "_await_and_emit_metis", side_effect=quick_emit),
        ):
            await executor.execute_agent_logic(ctx, task, updater)

        # Confirmation card still fires — Metis's drag doesn't gate
        # the player's confirmation prompt.
        assert len(send_input_calls) == 1
        assert "divide" in send_input_calls[0]
