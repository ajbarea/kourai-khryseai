"""Hephaestus pipeline: Kallos-Techne fix loop, INPUT_REQUIRED, CLI helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.hephaestus.agent import _kallos_found_issues
from agents.hephaestus.remote_connections import AgentInputRequired


class TestKallosFoundIssues:
    """Test the lint failure detection helper.

    Kallos's artifact starts with one of two deterministic headers; the helper
    keys off those, not incidental substrings, so noisy tool output like
    ``Failed to initialize cache`` doesn't trigger spurious retry loops.
    """

    def test_detects_issues_header(self):
        assert (
            _kallos_found_issues("✨ Linting completed with issues.\n\nE123 unused import") is True
        )

    def test_detects_clean_header(self):
        assert (
            _kallos_found_issues("✨ All linting checks passed!\n\nruff format: no changes")
            is False
        )

    def test_clean_header_beats_tool_noise(self):
        """Ruff warnings ('Failed to initialize cache') must not be read as a fail."""
        output = (
            "✨ All linting checks passed!\nwarning: Failed to initialize cache at /tmp/.ruff_cache"
        )
        assert _kallos_found_issues(output) is False

    def test_case_insensitive(self):
        assert _kallos_found_issues("ALL LINTING CHECKS PASSED") is False
        assert _kallos_found_issues("linting completed with issues") is True

    def test_unknown_shape_defaults_to_clean(self):
        """Conservative default: if neither header is present, don't loop."""
        assert _kallos_found_issues("some other tool output") is False

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
                return "✨ Linting completed with issues.\nE123 error on line 5"
            return "✨ All linting checks passed!"

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
                "agents.hephaestus.agent.RemoteAgentConnection",
                side_effect=make_conn,
            ),
            patch("agents.hephaestus.agent.MAX_ITERATIONS", 3),
        ):
            from agents.hephaestus.agent import execute_pipeline

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
                conn.send = AsyncMock(
                    return_value="✨ Linting completed with issues.\nE123 unfixable"
                )
            elif agent_name == "techne":
                conn.send = AsyncMock(return_value="Attempted fix")
            else:
                conn.send = AsyncMock(return_value="commit msg")
            return conn

        with (
            patch(
                "agents.hephaestus.agent.RemoteAgentConnection",
                side_effect=make_conn,
            ),
            patch("agents.hephaestus.agent.MAX_ITERATIONS", 2),
        ):
            from agents.hephaestus.agent import execute_pipeline

            statuses = []
            async for agent, status, _output in execute_pipeline(
                ["techne", "kallos", "mneme"], "implement feature X"
            ):
                statuses.append((agent, status))

            max_msgs = [s for s in statuses if "Enough!" in s[1] and "proceeding" in s[1]]
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
            conn.send = AsyncMock(return_value="✨ Linting completed with issues.\nE123")
            return conn

        with patch(
            "agents.hephaestus.agent.RemoteAgentConnection",
            side_effect=make_conn,
        ):
            from agents.hephaestus.agent import execute_pipeline

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
            "agents.hephaestus.agent.RemoteAgentConnection",
            side_effect=make_conn,
        ):
            from agents.hephaestus.agent import execute_pipeline

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
    """Test CLI output formatting helpers.

    These tests skip gracefully when asyncclick is not installed (e.g., running
    outside Docker). asyncclick is a Docker-only host dependency.
    """

    def test_extract_status_text(self):
        pytest.importorskip("asyncclick")
        from hosts.cli.events import _extract_status_text

        event = MagicMock()
        part = MagicMock()
        part.text = "Working on it..."
        event.status.message.parts = [part]
        assert _extract_status_text(event) == "Working on it..."

    def test_extract_status_text_no_message(self):
        pytest.importorskip("asyncclick")
        from hosts.cli.events import _extract_status_text

        event = MagicMock()
        event.status.message = None
        assert _extract_status_text(event) == ""

    def test_extract_artifact_text(self):
        pytest.importorskip("asyncclick")
        from hosts.cli.events import _extract_artifact_text

        event = MagicMock()
        part = MagicMock()
        part.text = "Final result"
        event.artifact.parts = [part]
        assert _extract_artifact_text(event) == "Final result"

    def test_extract_artifact_text_empty(self):
        pytest.importorskip("asyncclick")
        from hosts.cli.events import _extract_artifact_text

        event = MagicMock()
        event.artifact = None
        assert _extract_artifact_text(event) == ""
