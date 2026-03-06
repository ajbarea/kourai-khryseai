"""Kallos: system prompt, lint runner, fix generation, executor flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.kallos.agent import SYSTEM_PROMPT


class TestKallosSystemPrompt:
    """Verify the system prompt contains required constraints."""

    def test_includes_comment_rules(self):
        assert "WHAT comments" in SYSTEM_PROMPT
        assert "WHY comments" in SYSTEM_PROMPT

    def test_includes_research_citation_format(self):
        assert "Research:" in SYSTEM_PROMPT
        assert "Author et al." in SYSTEM_PROMPT

    def test_forbids_git_commit(self):
        assert "NEVER" in SYSTEM_PROMPT
        assert "git commit" in SYSTEM_PROMPT

    def test_includes_type_hint_rules(self):
        assert "X | None" in SYSTEM_PROMPT

    def test_no_marketing_language(self):
        assert "robust" in SYSTEM_PROMPT
        assert "comprehensive" in SYSTEM_PROMPT

    def test_has_personality_baseline_layer(self):
        """Verify the new layered prompt architecture includes the baseline."""
        assert "PERSONALITY BASELINE" in SYSTEM_PROMPT
        assert "relationship context" in SYSTEM_PROMPT


class TestRunMakeLint:
    """Test the make lint runner."""

    @pytest.mark.asyncio
    async def test_returns_success_on_zero_exit(self):
        with patch("agents.kallos.agent.run_command", new_callable=AsyncMock) as mock:
            mock.return_value = (0, "All checks passed\n", "")
            from agents.kallos.agent import run_make_lint

            passed, output = await run_make_lint()
            assert passed is True
            assert "All checks passed" in output

    @pytest.mark.asyncio
    async def test_returns_failure_on_nonzero_exit(self):
        with patch("agents.kallos.agent.run_command", new_callable=AsyncMock) as mock:
            mock.return_value = (1, "", "E501 line too long\n")
            from agents.kallos.agent import run_make_lint

            passed, output = await run_make_lint()
            assert passed is False
            assert "E501" in output


class TestFixLintIssues:
    """Test LLM-based lint fix generation."""

    @pytest.mark.asyncio
    async def test_calls_llm_with_file_contents(self, tmp_path):
        test_file = tmp_path / "example.py"
        test_file.write_text("x=1\n", encoding="utf-8")

        with patch("agents.kallos.agent.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "ALL CLEAN"
            from agents.kallos.agent import fix_lint_issues

            result = await fix_lint_issues(
                "E501 line too long", {str(test_file)}, context_id="ctx-1"
            )
            assert result == "ALL CLEAN"
            assert mock_chat.call_args[0][0] == "kallos"

    @pytest.mark.asyncio
    async def test_skips_missing_files(self):
        with patch("agents.kallos.agent.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "ALL CLEAN"
            from agents.kallos.agent import fix_lint_issues

            await fix_lint_issues("errors", {"/nonexistent/file.py"}, "ctx-1")
            # Should still call LLM but without the missing file's content block
            user_msg = mock_chat.call_args[0][1][-1]["content"]
            assert "--- /nonexistent/file.py ---" not in user_msg

    @pytest.mark.asyncio
    async def test_uses_context_windowing_for_large_files(self, tmp_path):
        """Verify that large files get windowed to relevant lines."""
        import json

        test_file = tmp_path / "big.py"
        # 300 lines — triggers windowing (>200 threshold)
        lines = [f"line_{i} = {i}" for i in range(300)]
        test_file.write_text("\n".join(lines), encoding="utf-8")

        # Build ruff JSON via json.dumps to properly escape Windows paths
        ruff_diag = [
            {
                "filename": str(test_file),
                "location": {"row": 150, "column": 1},
                "code": "E501",
                "message": "line too long",
                "fix": None,
            }
        ]
        ruff_json = json.dumps(ruff_diag)

        with patch("agents.kallos.agent.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "ALL CLEAN"
            from agents.kallos.agent import fix_lint_issues

            await fix_lint_issues(ruff_json, {str(test_file)}, "ctx-1")
            user_msg = mock_chat.call_args[0][1][-1]["content"]
            # Should contain line 150 context but NOT the very first line (windowed away)
            assert "150:" in user_msg
            # Line 1 should be excluded — it's 140+ lines away from the diagnostic
            assert "\n1: line_0" not in user_msg


class TestKallosExecutorFlow:
    """Test the executor's integration with run_fix_loop."""

    @pytest.mark.asyncio
    async def test_executor_calls_fix_loop_and_completes(self):
        """Verify executor wires up run_fix_loop and calls complete()."""
        from a2a.types import Task

        from agents.kallos.agent_executor import KallosAgentExecutor
        from kourai_common.fix_loop import FixLoopResult

        executor = KallosAgentExecutor()

        mock_updater = MagicMock()
        mock_updater.add_artifact = AsyncMock()
        mock_updater.complete = AsyncMock()

        mock_task = MagicMock(spec=Task)
        mock_task.context_id = "ctx-test"
        mock_task.id = "task-1"

        mock_context = MagicMock()

        result = FixLoopResult(all_passed=True, iterations_run=1, final_output="All checks passed")

        with patch("kourai_common.fix_loop.run_fix_loop", new_callable=AsyncMock) as mock_loop:
            mock_loop.return_value = (True, "All checks passed", result)

            await executor.execute_agent_logic(mock_context, mock_task, mock_updater)

            mock_loop.assert_awaited_once()
            mock_updater.add_artifact.assert_awaited_once()
            mock_updater.complete.assert_awaited_once()

            # Verify artifact has both TextPart and DataPart
            artifact_parts = mock_updater.add_artifact.call_args[0][0]
            assert len(artifact_parts) == 2
            assert "passed" in artifact_parts[0].root.text
            assert artifact_parts[1].root.data["all_passed"] is True

    @pytest.mark.asyncio
    async def test_executor_reports_issues_remain(self):
        """Verify executor handles failing lint gracefully."""
        from a2a.types import Task

        from agents.kallos.agent_executor import KallosAgentExecutor
        from kourai_common.fix_loop import FixLoopResult

        executor = KallosAgentExecutor()

        mock_updater = MagicMock()
        mock_updater.add_artifact = AsyncMock()
        mock_updater.complete = AsyncMock()

        mock_task = MagicMock(spec=Task)
        mock_task.context_id = "ctx-test"
        mock_task.id = "task-2"

        mock_context = MagicMock()

        result = FixLoopResult(
            all_passed=False,
            iterations_run=3,
            files_with_issues=["foo.py"],
            total_fixes_applied=2,
        )

        with patch("kourai_common.fix_loop.run_fix_loop", new_callable=AsyncMock) as mock_loop:
            mock_loop.return_value = (False, "E501 line too long", result)

            await executor.execute_agent_logic(mock_context, mock_task, mock_updater)

            mock_updater.complete.assert_awaited_once()
            artifact_parts = mock_updater.add_artifact.call_args[0][0]
            assert "issues" in artifact_parts[0].root.text
            assert artifact_parts[1].root.data["total_fixes_applied"] == 2

    @pytest.mark.asyncio
    async def test_executor_passes_kallos_personality_messages(self):
        """Verify executor uses KALLOS_MESSAGES, not generic defaults."""
        from a2a.types import Task

        from agents.kallos.agent_executor import KallosAgentExecutor
        from kourai_common.fix_loop import KALLOS_MESSAGES, FixLoopResult

        executor = KallosAgentExecutor()

        mock_updater = MagicMock()
        mock_updater.add_artifact = AsyncMock()
        mock_updater.complete = AsyncMock()

        mock_task = MagicMock(spec=Task)
        mock_task.context_id = "ctx-test"
        mock_task.id = "task-3"

        mock_context = MagicMock()

        result = FixLoopResult(all_passed=True)

        with patch("kourai_common.fix_loop.run_fix_loop", new_callable=AsyncMock) as mock_loop:
            mock_loop.return_value = (True, "ok", result)

            await executor.execute_agent_logic(mock_context, mock_task, mock_updater)

            call_kwargs = mock_loop.call_args[1]
            assert call_kwargs["messages"] is KALLOS_MESSAGES


class TestKallosAgentCard:
    """Test the agent card configuration."""

    def test_card_has_required_fields(self):
        from agents.kallos.__main__ import build_agent_card

        card = build_agent_card()
        assert card.name
        assert card.description
        assert card.version == "0.1.0"
        assert card.capabilities.streaming is True
        assert len(card.skills) == 1
        assert card.skills[0].id == "style_check"

    def test_card_description_mentions_auto_fix(self):
        from agents.kallos.__main__ import build_agent_card

        card = build_agent_card()
        assert "Auto-fixes" in card.description

    def test_card_skill_tags(self):
        from agents.kallos.__main__ import build_agent_card

        card = build_agent_card()
        tags = card.skills[0].tags
        assert "linting" in tags
        assert "formatting" in tags


class TestKallosInputRequired:
    """Test the input_required message."""

    def test_message_mentions_path_or_contents(self):
        from agents.kallos.agent_executor import KallosAgentExecutor

        executor = KallosAgentExecutor()
        msg = executor.get_input_required_message()
        assert "path" in msg.lower() or "contents" in msg.lower()


class TestFixLoopMessages:
    """Test the personality status message system."""

    def test_kallos_messages_have_personality(self):
        from kourai_common.fix_loop import KALLOS_MESSAGES

        assert "imperfections" in KALLOS_MESSAGES.running
        assert "gorgeous" in KALLOS_MESSAGES.passed
        assert "my touch" in KALLOS_MESSAGES.found_issues

    def test_dokimasia_messages_have_personality(self):
        from kourai_common.fix_loop import DOKIMASIA_MESSAGES

        assert "gauntlet" in DOKIMASIA_MESSAGES.running
        assert "crucible" in DOKIMASIA_MESSAGES.passed

    def test_message_formatting(self):
        from kourai_common.fix_loop import StatusMessages

        msgs = StatusMessages()
        assert "lint (iteration 1/3)" in msgs.format_running("lint", 1, 3)
        assert "lint passed" in msgs.format_passed("lint")
        assert "5 files" in msgs.format_found_issues(5)
        assert "3 fixes" in msgs.format_applied_fixes("lint", 3)


class TestRuffJsonParsing:
    """Test the structured ruff JSON output parser."""

    def test_parses_valid_json(self):
        from kourai_common.subprocess import parse_ruff_json

        output = '[{"filename": "foo.py", "location": {"row": 10, "column": 5}, "code": "E501", "message": "line too long", "fix": null}]'
        result = parse_ruff_json(output)
        assert len(result) == 1
        assert result[0]["filename"] == "foo.py"
        assert result[0]["row"] == 10
        assert result[0]["code"] == "E501"

    def test_falls_back_on_non_json(self):
        from kourai_common.subprocess import parse_ruff_json

        result = parse_ruff_json("not json at all")
        assert result == []

    def test_extract_files_from_ruff_json(self):
        from kourai_common.subprocess import extract_files_from_ruff_json

        output = '[{"filename": "a.py", "location": {"row": 1, "column": 1}, "code": "E501", "message": "x", "fix": null}, {"filename": "b.py", "location": {"row": 2, "column": 1}, "code": "E501", "message": "y", "fix": null}]'
        files = extract_files_from_ruff_json(output)
        assert files == {"a.py", "b.py"}


class TestContextWindowing:
    """Test the smart context windowing for LLM token efficiency."""

    def test_small_file_returns_all_lines(self, tmp_path):
        from kourai_common.subprocess import read_file_with_context

        f = tmp_path / "small.py"
        f.write_text("line1\nline2\nline3\n", encoding="utf-8")
        result = read_file_with_context(str(f), {2})
        assert "1: line1" in result
        assert "3: line3" in result

    def test_large_file_windows_to_diagnostics(self, tmp_path):
        from kourai_common.subprocess import read_file_with_context

        f = tmp_path / "big.py"
        lines = [f"x_{i} = {i}" for i in range(300)]
        f.write_text("\n".join(lines), encoding="utf-8")
        result = read_file_with_context(str(f), {150}, context_lines=5)
        # Should include lines around 150 but not line 1
        assert "150:" in result
        assert "1: x_0" not in result
        # Should have gap indicators
        assert "..." in result

    def test_missing_file_returns_empty(self):
        from kourai_common.subprocess import read_file_with_context

        result = read_file_with_context("/nonexistent/file.py", {10})
        assert result == ""

    def test_no_diagnostics_returns_full_file(self, tmp_path):
        from kourai_common.subprocess import read_file_with_context

        f = tmp_path / "full.py"
        f.write_text("a\nb\nc\n", encoding="utf-8")
        result = read_file_with_context(str(f))
        assert "1: a" in result
        assert "3: c" in result
