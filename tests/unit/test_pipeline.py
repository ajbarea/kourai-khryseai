"""Hephaestus pipeline: Kallos-Techne fix loop, INPUT_REQUIRED, CLI helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.hephaestus.remote_connections import AgentInputRequired
from agents.hephaestus.routing_agent import _kallos_found_issues


class TestKallosFoundIssues:
    """Test the lint failure detection helper."""

    def test_detects_fail(self):
        assert _kallos_found_issues("### ruff check: FAIL\nE123 error") is True

    def test_ignores_all_clean(self):
        assert _kallos_found_issues("ALL CLEAN\nruff check: PASS") is False

    def test_all_clean_overrides_fail(self):
        # "all clean" takes priority even if "fail" appears elsewhere
        assert _kallos_found_issues("Previously FAIL but now ALL CLEAN") is False

    def test_pass_only(self):
        assert _kallos_found_issues("### ruff check: PASS\n### ruff format: PASS") is False

    def test_case_insensitive(self):
        assert _kallos_found_issues("Ruff Check: Fail") is True

    def test_empty_string(self):
        assert _kallos_found_issues("") is False


class TestAgentInputRequired:
    """Test the INPUT_REQUIRED exception."""

    def test_exception_fields(self):
        exc = AgentInputRequired("metis", "What module?")
        assert exc.agent_name == "metis"
        assert exc.question == "What module?"
        assert "metis" in str(exc)

    def test_exception_inherits(self):
        exc = AgentInputRequired("techne", "Which file?")
        assert isinstance(exc, Exception)


class TestExecutePipelineIterativeLoop:
    """Test Kallos-Techne iterative fix loop in execute_pipeline."""

    @pytest.mark.asyncio
    async def test_loop_triggers_on_kallos_fail(self):
        """When kallos reports failures and techne is in pipeline, loop runs."""
        mock_card = MagicMock()
        mock_card.name = "TestAgent"

        # Use separate connection instances per agent so we can give each different behavior
        kallos_send_count = 0

        async def kallos_send(text, ctx_id):
            nonlocal kallos_send_count
            kallos_send_count += 1
            if kallos_send_count <= 1:
                return "### ruff check: FAIL\nE123 error on line 5"
            return "ALL CLEAN\n### ruff check: PASS"

        async def techne_send(text, ctx_id):
            return "Fixed code output"

        async def mneme_send(text, ctx_id):
            return "feat: add feature X"

        conn_map = {}

        def make_conn(agent_name, url):
            conn = AsyncMock()
            conn.card = mock_card
            conn.connect = AsyncMock()
            conn.close = AsyncMock()
            if agent_name == "kallos":
                conn.send = AsyncMock(side_effect=kallos_send)
            elif agent_name == "techne":
                conn.send = AsyncMock(side_effect=techne_send)
            else:
                conn.send = AsyncMock(side_effect=mneme_send)
            conn_map[agent_name] = conn
            return conn

        with (
            patch(
                "agents.hephaestus.routing_agent.RemoteAgentConnection",
                side_effect=make_conn,
            ),
            patch("agents.hephaestus.routing_agent.MAX_ITERATIONS", 3),
        ):
            from agents.hephaestus.routing_agent import execute_pipeline

            statuses = []
            async for agent, status, _output in execute_pipeline(
                ["techne", "kallos", "mneme"], "implement feature X"
            ):
                statuses.append((agent, status))

            # Should see fix loop messages
            fix_messages = [
                s for s in statuses if "auto-fix" in s[1].lower() or "[fix" in s[1].lower()
            ]
            assert len(fix_messages) > 0, f"No fix messages found in: {statuses}"

            # Should see "All clean" at end of loop
            clean_msgs = [s for s in statuses if "All clean" in s[1]]
            assert len(clean_msgs) > 0

    @pytest.mark.asyncio
    async def test_loop_respects_max_iterations(self):
        """Loop exits after MAX_ITERATIONS even if kallos still reports failures."""
        mock_card = MagicMock()
        mock_card.name = "TestAgent"

        def make_conn(agent_name, url):
            conn = AsyncMock()
            conn.card = mock_card
            conn.connect = AsyncMock()
            conn.close = AsyncMock()
            if agent_name == "kallos":
                conn.send = AsyncMock(return_value="### ruff check: FAIL\nE123 unfixable")
            elif agent_name == "techne":
                conn.send = AsyncMock(return_value="Attempted fix")
            else:
                conn.send = AsyncMock(return_value="commit msg")
            return conn

        with (
            patch(
                "agents.hephaestus.routing_agent.RemoteAgentConnection",
                side_effect=make_conn,
            ),
            patch("agents.hephaestus.routing_agent.MAX_ITERATIONS", 2),
        ):
            from agents.hephaestus.routing_agent import execute_pipeline

            statuses = []
            async for agent, status, _output in execute_pipeline(
                ["techne", "kallos", "mneme"], "implement feature X"
            ):
                statuses.append((agent, status))

            max_msgs = [s for s in statuses if "Max fix iterations" in s[1]]
            assert len(max_msgs) == 1

    @pytest.mark.asyncio
    async def test_no_loop_without_techne(self):
        """Kallos-only pipeline doesn't trigger iterative loop."""
        mock_card = MagicMock()
        mock_card.name = "TestAgent"

        def make_conn(agent_name, url):
            conn = AsyncMock()
            conn.card = mock_card
            conn.connect = AsyncMock()
            conn.close = AsyncMock()
            conn.send = AsyncMock(return_value="### ruff check: FAIL\nE123")
            return conn

        with patch(
            "agents.hephaestus.routing_agent.RemoteAgentConnection",
            side_effect=make_conn,
        ):
            from agents.hephaestus.routing_agent import execute_pipeline

            statuses = []
            async for agent, status, _output in execute_pipeline(
                ["kallos", "mneme"], "clean up code"
            ):
                statuses.append((agent, status))

            fix_messages = [s for s in statuses if "auto-fix" in s[1].lower()]
            assert len(fix_messages) == 0


class TestExecutePipelineInputRequired:
    """Test INPUT_REQUIRED flow in execute_pipeline."""

    @pytest.mark.asyncio
    async def test_input_required_propagates(self):
        """AgentInputRequired from a specialist yields INPUT_REQUIRED status."""
        mock_card = MagicMock()
        mock_card.name = "TestAgent"

        def make_conn(agent_name, url):
            conn = AsyncMock()
            conn.card = mock_card
            conn.connect = AsyncMock()
            conn.close = AsyncMock()
            if agent_name == "metis":
                conn.send = AsyncMock(
                    side_effect=AgentInputRequired("metis", "Which module should I plan?")
                )
            else:
                conn.send = AsyncMock(return_value="code output")
            return conn

        with patch(
            "agents.hephaestus.routing_agent.RemoteAgentConnection",
            side_effect=make_conn,
        ):
            from agents.hephaestus.routing_agent import execute_pipeline

            statuses = []
            async for agent, status, _output in execute_pipeline(
                ["metis", "techne"], "plan something"
            ):
                statuses.append((agent, status))

            input_msgs = [s for s in statuses if "INPUT_REQUIRED:" in s[1]]
            assert len(input_msgs) == 1
            assert "Which module" in input_msgs[0][1]

            complete_msgs = [s for s in statuses if s[1] == "Pipeline complete"]
            assert len(complete_msgs) == 0


class TestCLIHelpers:
    """Test CLI output formatting helpers."""

    def test_extract_status_text(self):
        from hosts.cli.__main__ import _extract_status_text

        event = MagicMock()
        part = MagicMock()
        part.root.text = "Working on it..."
        event.status.message.parts = [part]
        assert _extract_status_text(event) == "Working on it..."

    def test_extract_status_text_no_message(self):
        from hosts.cli.__main__ import _extract_status_text

        event = MagicMock()
        event.status.message = None
        assert _extract_status_text(event) == ""

    def test_extract_artifact_text(self):
        from hosts.cli.__main__ import _extract_artifact_text

        event = MagicMock()
        part = MagicMock()
        part.root.text = "Final result"
        event.artifact.parts = [part]
        assert _extract_artifact_text(event) == "Final result"

    def test_extract_artifact_text_empty(self):
        from hosts.cli.__main__ import _extract_artifact_text

        event = MagicMock()
        event.artifact = None
        assert _extract_artifact_text(event) == ""
