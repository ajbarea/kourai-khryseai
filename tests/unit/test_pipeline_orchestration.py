"""Integration: full pipeline orchestration through Hephaestus.

Tests the complete request → routing → multi-agent pipeline → result cycle
with mocked RemoteAgentConnections. No live servers, no LLM calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.hephaestus.remote_connections import AgentInputRequired

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_card(name: str = "TestAgent") -> MagicMock:
    card = MagicMock()
    card.name = name
    return card


def _status_texts(statuses: list[tuple[str, str]]) -> list[str]:
    """Extract just the status strings for easier assertions."""
    return [s for _, s in statuses]


# ---------------------------------------------------------------------------
# Full pipeline: metis → techne → dokimasia → kallos → mneme
# ---------------------------------------------------------------------------


class TestFullPipelineOrchestration:
    """End-to-end pipeline with all five specialists completing successfully."""

    @pytest.mark.asyncio
    async def test_all_agents_execute_in_order(self):
        """Pipeline calls every agent in sequence, accumulates context."""
        call_order: list[str] = []
        accumulated_inputs: dict[str, str] = {}

        async def agent_send(text: str, ctx_id: str, *, _name: str) -> str:
            call_order.append(_name)
            accumulated_inputs[_name] = text
            return f"{_name} output: done"

        def make_conn(agent_name: str, url: str) -> AsyncMock:
            conn = AsyncMock()
            conn.card = _make_card(agent_name)
            conn.connect = AsyncMock()
            conn.close = AsyncMock()

            async def send_fn(text: str, ctx_id: str) -> str:
                return await agent_send(text, ctx_id, _name=agent_name)

            conn.send = AsyncMock(side_effect=send_fn)
            return conn

        pipeline = ["metis", "techne", "dokimasia", "kallos", "mneme"]

        with patch(
            "agents.hephaestus.agent.RemoteAgentConnection",
            side_effect=make_conn,
        ):
            from agents.hephaestus.agent import execute_pipeline

            statuses: list[tuple[str, str]] = []
            async for agent, status, _output in execute_pipeline(pipeline, "implement CSV export"):
                statuses.append((agent, status))

        # All five agents executed
        assert call_order == ["metis", "techne", "dokimasia", "kallos", "mneme"]

        # Pipeline completed
        texts = _status_texts(statuses)
        assert "Pipeline complete" in texts

        # Context accumulates: later agents receive earlier agents' output
        assert "metis output" in accumulated_inputs["techne"]
        assert "techne output" in accumulated_inputs["dokimasia"]
        assert "dokimasia output" in accumulated_inputs["kallos"]
        assert "kallos output" in accumulated_inputs["mneme"]

    @pytest.mark.asyncio
    async def test_pipeline_yields_progress_for_each_step(self):
        """Each agent produces at least a 'Sending' and 'completed' status."""

        def make_conn(agent_name: str, url: str) -> AsyncMock:
            conn = AsyncMock()
            conn.card = _make_card(agent_name)
            conn.connect = AsyncMock()
            conn.close = AsyncMock()
            conn.send = AsyncMock(return_value=f"{agent_name} result")
            return conn

        pipeline = ["metis", "techne", "dokimasia", "kallos", "mneme"]

        with patch(
            "agents.hephaestus.agent.RemoteAgentConnection",
            side_effect=make_conn,
        ):
            from agents.hephaestus.agent import execute_pipeline

            statuses: list[tuple[str, str]] = []
            async for agent, status, _output in execute_pipeline(pipeline, "implement feature"):
                statuses.append((agent, status))

        texts = _status_texts(statuses)

        # Each agent should have a Hephaestus narration and "completed" message
        for agent_name in pipeline:
            narration = [t for t in texts if "\U0001f525" in t]
            completed = [t for t in texts if "completed" in t.lower() and agent_name in t.lower()]
            assert len(narration) > 0, f"No Hephaestus narration for {agent_name}"
            assert len(completed) > 0, f"No 'completed' status for {agent_name}"


# ---------------------------------------------------------------------------
# Kallos-Techne iterative loop: converge in 2 iterations
# ---------------------------------------------------------------------------


class TestIterativeLoopConvergence:
    """Full pipeline where Kallos finds issues, Techne fixes, Kallos re-checks."""

    @pytest.mark.asyncio
    async def test_loop_converges_then_pipeline_continues(self):
        """Kallos fails once, Techne fixes, Kallos passes, Mneme still runs."""
        kallos_call_count = 0
        agents_that_ran: list[str] = []

        async def kallos_send(text: str, ctx_id: str) -> str:
            nonlocal kallos_call_count
            kallos_call_count += 1
            agents_that_ran.append("kallos")
            if kallos_call_count <= 1:
                return "### ruff check: FAIL\nE501 line too long on line 42"
            return "ALL CLEAN\n### ruff check: PASS\n### ruff format: PASS"

        async def techne_send(text: str, ctx_id: str) -> str:
            agents_that_ran.append("techne")
            return "Fixed: shortened line 42"

        async def mneme_send(text: str, ctx_id: str) -> str:
            agents_that_ran.append("mneme")
            return "style: shorten line 42 for ruff compliance"

        def make_conn(agent_name: str, url: str) -> AsyncMock:
            conn = AsyncMock()
            conn.card = _make_card(agent_name)
            conn.connect = AsyncMock()
            conn.close = AsyncMock()
            if agent_name == "kallos":
                conn.send = AsyncMock(side_effect=kallos_send)
            elif agent_name == "techne":
                conn.send = AsyncMock(side_effect=techne_send)
            else:
                conn.send = AsyncMock(side_effect=mneme_send)
            return conn

        with (
            patch(
                "agents.hephaestus.agent.RemoteAgentConnection",
                side_effect=make_conn,
            ),
            patch("agents.hephaestus.agent.MAX_ITERATIONS", 3),
        ):
            from agents.hephaestus.agent import execute_pipeline

            statuses: list[tuple[str, str]] = []
            async for agent, status, _output in execute_pipeline(
                ["techne", "kallos", "mneme"], "fix style issues"
            ):
                statuses.append((agent, status))

        texts = _status_texts(statuses)

        # Kallos was called twice: initial fail + re-check pass
        assert kallos_call_count == 2

        # Fix loop messages appeared
        assert any("auto-fix" in t.lower() or "[fix" in t.lower() for t in texts)

        # Converged to clean
        assert any("All clean" in t for t in texts)

        # Mneme still executed after the loop
        assert "mneme" in agents_that_ran

        # Pipeline completed
        assert "Pipeline complete" in texts


# ---------------------------------------------------------------------------
# Mid-pipeline failure: one agent down, others still run
# ---------------------------------------------------------------------------


class TestMidPipelineDegradation:
    """One specialist unreachable mid-pipeline; others complete."""

    @pytest.mark.asyncio
    async def test_skipped_agent_doesnt_block_pipeline(self):
        """Dokimasia is down, but metis → techne → kallos → mneme still run."""
        call_order: list[str] = []

        def make_conn(agent_name: str, url: str) -> AsyncMock:
            conn = AsyncMock()
            conn.card = _make_card(agent_name)
            conn.close = AsyncMock()
            if agent_name == "dokimasia":
                conn.connect = AsyncMock(side_effect=ConnectionError("refused"))
            else:
                conn.connect = AsyncMock()

                async def send_fn(text: str, ctx_id: str, _name: str = agent_name) -> str:
                    call_order.append(_name)
                    return f"{_name} result"

                conn.send = AsyncMock(side_effect=send_fn)
            return conn

        pipeline = ["metis", "techne", "dokimasia", "kallos", "mneme"]

        with patch(
            "agents.hephaestus.agent.RemoteAgentConnection",
            side_effect=make_conn,
        ):
            from agents.hephaestus.agent import execute_pipeline

            statuses: list[tuple[str, str]] = []
            async for agent, status, _output in execute_pipeline(pipeline, "implement feature"):
                statuses.append((agent, status))

        texts = _status_texts(statuses)

        # Dokimasia was skipped
        assert any("Skipped" in t for t in texts)

        # Other four agents ran
        assert call_order == ["metis", "techne", "kallos", "mneme"]

        # Pipeline still completed
        assert "Pipeline complete" in texts

    @pytest.mark.asyncio
    async def test_input_required_halts_pipeline_early(self):
        """INPUT_REQUIRED from Metis stops the pipeline before Techne runs."""
        techne_called = False

        def make_conn(agent_name: str, url: str) -> AsyncMock:
            nonlocal techne_called
            conn = AsyncMock()
            conn.card = _make_card(agent_name)
            conn.connect = AsyncMock()
            conn.close = AsyncMock()
            if agent_name == "metis":
                conn.send = AsyncMock(
                    side_effect=AgentInputRequired("metis", "Which module to plan?"),
                )
            else:

                async def send_fn(text: str, ctx_id: str) -> str:
                    nonlocal techne_called
                    techne_called = True
                    return "code"

                conn.send = AsyncMock(side_effect=send_fn)
            return conn

        with patch(
            "agents.hephaestus.agent.RemoteAgentConnection",
            side_effect=make_conn,
        ):
            from agents.hephaestus.agent import execute_pipeline

            statuses: list[tuple[str, str]] = []
            async for agent, status, _output in execute_pipeline(
                ["metis", "techne", "mneme"], "plan something"
            ):
                statuses.append((agent, status))

        texts = _status_texts(statuses)

        # INPUT_REQUIRED propagated
        input_msgs = [t for t in texts if "INPUT_REQUIRED:" in t]
        assert len(input_msgs) == 1
        assert "Which module" in input_msgs[0]

        # Techne never executed
        assert techne_called is False

        # Pipeline did NOT complete
        assert "Pipeline complete" not in texts
