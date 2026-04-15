"""Metis: spec generation, project context, planning prompt structure."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.metis.agent import SYSTEM_PROMPT


class TestMetisSystemPrompt:
    """Verify the system prompt contains required planning structure."""

    def test_includes_output_sections(self):
        assert "Summary" in SYSTEM_PROMPT
        assert "Files to Modify" in SYSTEM_PROMPT
        assert "Files to Create" in SYSTEM_PROMPT
        assert "Implementation Steps" in SYSTEM_PROMPT
        assert "Acceptance Criteria" in SYSTEM_PROMPT
        assert "Edge Cases" in SYSTEM_PROMPT
        assert "Testing Notes" in SYSTEM_PROMPT

    def test_no_marketing_language_rule(self):
        assert "robust" in SYSTEM_PROMPT
        assert "comprehensive" in SYSTEM_PROMPT

    def test_edit_over_create(self):
        assert "Prefer editing existing files" in SYSTEM_PROMPT

    def test_minimal_scope(self):
        assert "MINIMAL scope" in SYSTEM_PROMPT

    def test_forbids_git_commit(self):
        assert "git commit" in SYSTEM_PROMPT


class TestCreateSpec:
    """Test spec generation with mocked LLM."""

    @pytest.mark.asyncio
    async def test_create_spec_calls_llm(self):
        with patch("agents.metis.agent.chat", new_callable=AsyncMock) as mock:
            mock.return_value = "## Summary\nAdd CSV export\n## Files to Modify\n- parser.py"
            from agents.metis.agent import create_spec

            result = await create_spec("add CSV export to the dashboard")
            assert "Summary" in result
            assert mock.call_args[0][0] == "metis"

    @pytest.mark.asyncio
    async def test_create_spec_includes_file_context(self):
        with patch("agents.metis.agent.chat", new_callable=AsyncMock) as mock:
            mock.return_value = "spec"
            from agents.metis.agent import create_spec

            await create_spec(
                "add CSV export",
                file_contents={"parser.py": "def parse(): pass"},
            )
            user_msg = mock.call_args[0][1][-1]["content"]
            assert "parser.py" in user_msg

    @pytest.mark.asyncio
    async def test_create_spec_includes_project_context(self):
        with patch("agents.metis.agent.chat", new_callable=AsyncMock) as mock:
            mock.return_value = "spec"
            from agents.metis.agent import create_spec

            await create_spec("add feature", project_context="Git status: M auth.py")
            user_msg = mock.call_args[0][1][-1]["content"]
            assert "PROJECT CONTEXT" in user_msg


class TestCreateSpecStream:
    """Test streaming spec generation with mocked LLM."""

    @pytest.mark.asyncio
    async def test_streams_chunks(self):
        async def _stream(*args, **kwargs):
            yield "## Summary\n"
            yield "Add feature"

        with patch("agents.metis.agent.chat_stream", new=_stream):
            from agents.metis.agent import create_spec_stream

            chunks = [c async for c in create_spec_stream("add feature")]
        assert chunks == ["## Summary\n", "Add feature"]

    @pytest.mark.asyncio
    async def test_includes_project_context(self):
        captured: dict = {}

        async def _stream(*args, **kwargs):
            captured["messages"] = args[1]
            yield "spec"

        with patch("agents.metis.agent.chat_stream", new=_stream):
            from agents.metis.agent import create_spec_stream

            async for _ in create_spec_stream("idea", project_context="Git status: M auth.py"):
                pass
        assert "PROJECT CONTEXT" in captured["messages"][-1]["content"]

    @pytest.mark.asyncio
    async def test_includes_file_contents(self):
        captured: dict = {}

        async def _stream(*args, **kwargs):
            captured["messages"] = args[1]
            yield "spec"

        with patch("agents.metis.agent.chat_stream", new=_stream):
            from agents.metis.agent import create_spec_stream

            async for _ in create_spec_stream("idea", file_contents={"app.py": "def main(): pass"}):
                pass
        assert "app.py" in captured["messages"][-1]["content"]


class TestGithubSearchIssues:
    """Test GitHub issue search with mocked API."""

    @pytest.mark.asyncio
    async def test_returns_empty_without_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        from agents.metis.agent import github_search_issues

        results = await github_search_issues("database migration")
        assert results == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_import_error(self, monkeypatch):
        monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "test-token")
        from agents.metis.agent import github_search_issues

        with patch.dict("sys.modules", {"github": None}):
            results = await github_search_issues("migration")
        assert results == []

    @pytest.mark.asyncio
    async def test_returns_results(self, monkeypatch):
        monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "test-token")

        mock_issue = MagicMock()
        mock_issue.number = 42
        mock_issue.title = "Fix migration bug"
        mock_issue.body = "Description here"
        mock_issue.repository.full_name = "owner/repo"
        mock_issue.html_url = "https://github.com/owner/repo/issues/42"
        mock_issue.state = "open"

        mock_gh_instance = MagicMock()
        mock_gh_instance.search_issues.return_value = [mock_issue]
        mock_github_module = MagicMock()
        mock_github_module.Github.return_value = mock_gh_instance

        with patch.dict("sys.modules", {"github": mock_github_module}):
            from agents.metis.agent import github_search_issues

            results = await github_search_issues("migration bug")
        assert len(results) == 1
        assert results[0]["issue_number"] == 42
        assert results[0]["title"] == "Fix migration bug"
        assert results[0]["state"] == "open"


class TestGetProjectContext:
    """Test project context gathering."""

    @pytest.mark.asyncio
    async def test_returns_string(self):
        from agents.metis.agent import get_project_context

        ctx = await get_project_context()
        assert isinstance(ctx, str)
        # Should contain at least project root entries
        assert len(ctx) > 0


class TestMetisAgentCard:
    """Test the agent card configuration."""

    def test_card_has_required_fields(self):
        from agents.metis.__main__ import build_agent_card

        card = build_agent_card()
        assert card.name
        assert card.version == "0.1.0"
        assert card.capabilities.streaming is True
        assert len(card.skills) == 1
        assert card.skills[0].id == "create_spec"

    def test_card_skill_tags(self):
        from agents.metis.__main__ import build_agent_card

        card = build_agent_card()
        tags = card.skills[0].tags
        assert "planning" in tags
        assert "specification" in tags
