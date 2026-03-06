"""Dokimasia: pytest output parsing, test generation, result formatting."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agents.dokimasia.agent import (
    SYSTEM_PROMPT,
    PytestRunResult,
    format_test_results,
)


class TestDokimasiaSystemPrompt:
    """Verify the system prompt contains required testing standards."""

    def test_includes_priority_order(self):
        assert "Unit tests" in SYSTEM_PROMPT
        assert "Integration tests" in SYSTEM_PROMPT
        assert "Performance tests" in SYSTEM_PROMPT

    def test_includes_coverage_target(self):
        assert "80%" in SYSTEM_PROMPT

    def test_includes_file_pattern(self):
        assert "test_{{module_name}}" in SYSTEM_PROMPT

    def test_includes_class_pattern(self):
        assert "TestClassName" in SYSTEM_PROMPT

    def test_forbids_git_commit(self):
        assert "git commit" in SYSTEM_PROMPT

    def test_includes_result_table(self):
        assert "Category" in SYSTEM_PROMPT
        assert "Passed" in SYSTEM_PROMPT
        assert "Failed" in SYSTEM_PROMPT


class TestPytestRunResult:
    """Test PytestRunResult dataclass."""

    def test_defaults(self):
        r = PytestRunResult()
        assert r.passed == 0
        assert r.failed == 0
        assert r.success is False

    def test_with_results(self):
        r = PytestRunResult(passed=10, failed=2, total=12, success=False)
        assert r.total == 12


class TestFormatTestResults:
    """Test result formatting."""

    def test_passing_results(self):
        r = PytestRunResult(passed=10, total=10, duration=1.5, success=True)
        text = format_test_results(r)
        assert "PASS" in text
        assert "10" in text
        assert "1.50s" in text

    def test_failing_results(self):
        r = PytestRunResult(
            passed=8,
            failed=2,
            total=10,
            success=False,
            output="FAILED test_foo - AssertionError",
        )
        text = format_test_results(r)
        assert "FAIL" in text
        assert "Failure Details" in text


class TestGenerateTests:
    """Test LLM-based test generation."""

    @pytest.mark.asyncio
    async def test_generate_calls_llm(self):
        with patch("agents.dokimasia.agent.chat", new_callable=AsyncMock) as mock:
            mock.return_value = "def test_foo(): assert True"
            from agents.dokimasia.agent import generate_tests

            result = await generate_tests("def foo(): return 1", "foo")
            assert "test_foo" in result
            assert mock.call_args[0][0] == "dokimasia"

    @pytest.mark.asyncio
    async def test_generate_includes_existing_tests(self):
        with patch("agents.dokimasia.agent.chat", new_callable=AsyncMock) as mock:
            mock.return_value = "new tests"
            from agents.dokimasia.agent import generate_tests

            await generate_tests("def foo(): pass", "foo", existing_tests="def test_old(): pass")
            user_msg = mock.call_args[0][1][-1]["content"]
            assert "EXISTING TESTS" in user_msg


class TestRunPytest:
    """Test pytest runner."""

    @pytest.mark.asyncio
    async def test_run_parses_passing_output(self):
        summary = "5 passed in 0.42s"
        with patch("agents.dokimasia.agent.run_command", new_callable=AsyncMock) as mock:
            mock.return_value = (0, f"collecting...\n{summary}\n", "")
            from agents.dokimasia.agent import run_pytest

            result = await run_pytest("tests/unit/test_example.py")
            assert result.success is True
            assert result.passed == 5
            assert result.duration == pytest.approx(0.42, abs=0.01)

    @pytest.mark.asyncio
    async def test_run_parses_failure_output(self):
        summary = "===== 3 passed, 2 failed in 1.10s ====="
        with patch("agents.dokimasia.agent.run_command", new_callable=AsyncMock) as mock:
            mock.return_value = (1, f"FAILURES...\n{summary}\n", "")
            from agents.dokimasia.agent import run_pytest

            result = await run_pytest("tests/unit/test_example.py")
            assert result.success is False
            assert result.passed == 3
            assert result.failed == 2


class TestDokimasiaAgentCard:
    """Test the agent card configuration."""

    def test_card_has_two_skills(self):
        from agents.dokimasia.__main__ import build_agent_card

        card = build_agent_card()
        assert len(card.skills) == 2
        ids = {s.id for s in card.skills}
        assert "write_tests" in ids
        assert "run_tests" in ids

    def test_card_streaming(self):
        from agents.dokimasia.__main__ import build_agent_card

        card = build_agent_card()
        assert card.capabilities.streaming is True
