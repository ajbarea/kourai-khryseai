"""Unit tests for Kallos agent — style checking."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agents.kallos.agent import (
    SYSTEM_PROMPT,
    LintResult,
    StyleReport,
    format_report,
)


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


class TestLintResult:
    """Test LintResult dataclass."""

    def test_defaults(self):
        r = LintResult(tool="ruff", passed=True, output="")
        assert r.fixed_count == 0

    def test_with_issues(self):
        r = LintResult(tool="ruff check", passed=False, output="E501 line too long", fixed_count=0)
        assert not r.passed


class TestFormatReport:
    """Test the format_report function."""

    def test_all_clean_report(self):
        report = StyleReport(
            lint_results=[
                LintResult(tool="ruff check", passed=True, output=""),
                LintResult(tool="ruff format", passed=True, output=""),
            ],
            comment_analysis="ALL CLEAN",
            all_clean=True,
        )
        text = format_report(report)
        assert "ALL CLEAN" in text
        assert "PASS" in text

    def test_issues_report(self):
        report = StyleReport(
            lint_results=[
                LintResult(tool="ruff check", passed=False, output="E501 line too long"),
                LintResult(tool="ruff format", passed=True, output=""),
            ],
            all_clean=False,
        )
        text = format_report(report)
        assert "FAIL" in text
        assert "E501" in text

    def test_empty_report(self):
        report = StyleReport()
        text = format_report(report)
        assert isinstance(text, str)


class TestRunCommand:
    """Test the subprocess runner."""

    @pytest.mark.asyncio
    async def test_run_command_success(self):
        from agents.kallos.agent import run_command

        code, stdout, stderr = await run_command(["python", "--version"])
        assert code == 0
        assert "Python" in stdout or "Python" in stderr


class TestAnalyzeComments:
    """Test comment analysis with mocked LLM."""

    @pytest.mark.asyncio
    async def test_analyze_calls_llm(self):
        with patch("agents.kallos.agent.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "ALL CLEAN"
            from agents.kallos.agent import analyze_comments

            result = await analyze_comments({"test.py": "x = 1\n"})
            assert result == "ALL CLEAN"
            assert mock_chat.call_args[0][0] == "kallos"

    @pytest.mark.asyncio
    async def test_analyze_empty_files(self):
        from agents.kallos.agent import analyze_comments

        result = await analyze_comments({})
        assert "No files" in result


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

    def test_card_skill_tags(self):
        from agents.kallos.__main__ import build_agent_card

        card = build_agent_card()
        tags = card.skills[0].tags
        assert "linting" in tags
        assert "formatting" in tags
