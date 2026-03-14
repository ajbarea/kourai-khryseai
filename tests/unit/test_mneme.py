"""Mneme: commit message generation, streaming, prompt constraints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agents.mneme.agent import SYSTEM_PROMPT


class TestMnemeSystemPrompt:
    """Verify the system prompt contains required constraints."""

    def test_includes_commit_types(self):
        for commit_type in ["test", "docs", "fix", "feat", "chore", "refactor"]:
            assert f"- {commit_type}(" in SYSTEM_PROMPT

    def test_forbids_git_commit(self):
        assert "NEVER run git commit" in SYSTEM_PROMPT

    def test_ignores_claude_dir(self):
        assert ".claude/" in SYSTEM_PROMPT

    def test_present_tense_headlines(self):
        assert "Present tense headlines" in SYSTEM_PROMPT

    def test_past_tense_bullets(self):
        assert "Past tense bullet points" in SYSTEM_PROMPT

    def test_no_marketing_language(self):
        assert "NO marketing language" in SYSTEM_PROMPT


class TestMnemeGenerate:
    """Test the generate functions with mocked LLM calls."""

    @pytest.mark.asyncio
    async def test_generate_calls_llm_with_git_output(self):
        mock_response = "feat(auth): add login endpoint\n\n- Added POST /login\n\nFiles: auth.py"
        with patch("agents.mneme.agent.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_response
            from agents.mneme.agent import generate_commit_messages

            result = await generate_commit_messages("M auth.py")
            assert result == mock_response
            mock_chat.assert_called_once()
            # Verify it used the "mneme" agent name
            assert mock_chat.call_args[0][0] == "mneme"

    @pytest.mark.asyncio
    async def test_generate_stream_yields_chunks(self):
        async def mock_stream(*args, **kwargs):
            for chunk in ["feat(auth)", ": add login", " endpoint\n"]:
                yield chunk

        with patch("agents.mneme.agent.chat_stream", side_effect=mock_stream):
            from agents.mneme.agent import generate_commit_messages_stream

            chunks = []
            async for chunk in generate_commit_messages_stream("M auth.py"):
                chunks.append(chunk)
            assert "".join(chunks) == "feat(auth): add login endpoint\n"


class TestMnemeAgentCard:
    """Test the agent card configuration."""

    def test_card_has_required_fields(self):
        from agents.mneme.__main__ import build_agent_card

        card = build_agent_card()
        assert card.name
        assert card.description
        assert card.url
        assert card.version == "0.1.0"
        assert card.capabilities.streaming is True
        assert len(card.skills) == 1
        assert card.skills[0].id == "generate_commits"

    def test_card_skill_has_examples(self):
        from agents.mneme.__main__ import build_agent_card

        card = build_agent_card()
        skill = card.skills[0]
        assert skill.examples is not None and len(skill.examples) >= 1
        assert "git" in skill.tags


class TestCollectGitChanges:
    """Test git change collection for Mneme input enrichment."""

    def test_collects_status_and_diffs(self):
        with patch("scripts.git_changes._run_git") as mock_git:
            mock_git.side_effect = lambda *args, **kw: {
                (
                    "status",
                    "--porcelain",
                ): "M agents/mneme/agent.py\nM scripts/status.py\n",
                ("diff",): (
                    "diff --git a/agents/mneme/agent.py b/agents/mneme/agent.py\n"
                    "--- a/agents/mneme/agent.py\n"
                    "+++ b/agents/mneme/agent.py\n"
                    "@@ -1 +1 @@\n"
                    "-old\n"
                    "+new\n"
                ),
                ("diff", "--staged"): "",
            }.get(args, "")

            from scripts.git_changes import collect_git_changes

            result = collect_git_changes()
            assert "=== git status ===" in result
            assert "M agents/mneme/agent.py" in result
            assert "Unstaged changes" in result

    def test_clean_working_tree(self):
        with patch("scripts.git_changes._run_git", return_value=""):
            from scripts.git_changes import collect_git_changes

            result = collect_git_changes()
            assert "working tree clean" in result

    def test_truncates_large_file_diffs(self):
        big_diff = "diff --git a/big.py b/big.py\n" + "+" * 5000

        with patch("scripts.git_changes._run_git") as mock_git:
            mock_git.side_effect = lambda *args, **kw: {
                ("status", "--porcelain"): "M big.py\n",
                ("diff",): big_diff,
                ("diff", "--staged"): "",
            }.get(args, "")

            from scripts.git_changes import collect_git_changes

            result = collect_git_changes()
            assert "truncated" in result
