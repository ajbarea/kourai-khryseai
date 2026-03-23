"""Hephaestus: LLM routing, pipeline determination, agent card config."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agents.hephaestus.agent import (
    AVAILABLE_AGENTS,
    ROUTING_PROMPT,
    PipelineResult,
    PipelineStep,
    determine_pipeline,
)
from kourai_common.player import PlayerProfile


class TestRoutingPrompt:
    """Verify the routing prompt contains required agent info."""

    def test_includes_all_agents(self):
        for agent in AVAILABLE_AGENTS:
            assert agent in ROUTING_PROMPT

    def test_includes_pipeline_templates(self):
        assert "implement X" in ROUTING_PROMPT
        assert "fix bug X" in ROUTING_PROMPT
        assert "commit prep" in ROUTING_PROMPT

    def test_includes_ask_user_instruction(self):
        assert "ASK_USER:" in ROUTING_PROMPT


class TestDeterminePipeline:
    """Test LLM-based routing decisions."""

    @pytest.mark.asyncio
    async def test_implement_routes_full_pipeline(self):
        with patch("agents.hephaestus.agent.chat", new_callable=AsyncMock) as mock:
            mock.return_value = "metis, techne, dokimasia, kallos, mneme"
            result = await determine_pipeline("implement a CSV export feature")
            assert result == ["metis", "techne", "dokimasia", "kallos", "mneme"]

    @pytest.mark.asyncio
    async def test_commit_prep_routes_to_mneme_only(self):
        with patch("agents.hephaestus.agent.chat", new_callable=AsyncMock) as mock:
            mock.return_value = "mneme"
            result = await determine_pipeline("commit prep")
            assert result == ["mneme"]

    @pytest.mark.asyncio
    async def test_cleanup_routes_to_kallos_mneme(self):
        with patch("agents.hephaestus.agent.chat", new_callable=AsyncMock) as mock:
            mock.return_value = "kallos, mneme"
            result = await determine_pipeline("clean up comments in src/")
            assert result == ["kallos", "mneme"]

    @pytest.mark.asyncio
    async def test_ask_user_returns_string(self):
        with patch("agents.hephaestus.agent.chat", new_callable=AsyncMock) as mock:
            mock.return_value = "ASK_USER: What file do you want to fix?"
            result = await determine_pipeline("fix it")
            assert isinstance(result, str)
            assert "ASK_USER:" in result

    @pytest.mark.asyncio
    async def test_invalid_agents_filtered_out(self):
        with patch("agents.hephaestus.agent.chat", new_callable=AsyncMock) as mock:
            mock.return_value = "metis, nonexistent_agent, techne"
            result = await determine_pipeline("implement X")
            assert result == ["metis", "techne"]

    @pytest.mark.asyncio
    async def test_empty_response_defaults_to_mneme(self):
        with patch("agents.hephaestus.agent.chat", new_callable=AsyncMock) as mock:
            mock.return_value = "  "
            result = await determine_pipeline("do something")
            assert result == ["mneme"]

    @pytest.mark.asyncio
    async def test_uses_hephaestus_model(self):
        with patch("agents.hephaestus.agent.chat", new_callable=AsyncMock) as mock:
            mock.return_value = "mneme"
            await determine_pipeline("test")
            assert mock.call_args[0][0] == "hephaestus"

    @pytest.mark.asyncio
    async def test_injects_player_context_when_profile_exists(self):
        """Player context is appended to system prompt when a profile exists."""
        profile = PlayerProfile(display_name="AJ", title="The Architect", role="divine")
        with (
            patch("agents.hephaestus.agent.chat", new_callable=AsyncMock) as mock,
            patch("agents.hephaestus.agent.PlayerProfile") as mock_cls,
            patch("agents.hephaestus.agent.build_player_context") as mock_ctx,
        ):
            mock.return_value = "mneme"
            mock_cls.load.return_value = profile
            mock_ctx.return_value = "=== PLAYER IDENTITY ===\nName: AJ"

            await determine_pipeline("commit prep")

            # System prompt should contain the player context
            system_msg = mock.call_args[0][1][0]["content"]
            assert "PLAYER IDENTITY" in system_msg


class TestPipelineDataclasses:
    """Test pipeline data structures."""

    def test_pipeline_step_defaults(self):
        step = PipelineStep(agent_name="mneme")
        assert step.status == "pending"
        assert step.input_text == ""
        assert step.output_text == ""

    def test_pipeline_result_defaults(self):
        result = PipelineResult()
        assert result.steps == []
        assert result.final_output == ""
        assert result.success is False


class TestHephaestusAgentCard:
    """Test the agent card configuration."""

    def test_card_has_three_skills(self):
        from agents.hephaestus.__main__ import build_agent_card

        card = build_agent_card()
        assert len(card.skills) == 3
        skill_ids = {s.id for s in card.skills}
        assert "route_request" in skill_ids
        assert "pipeline_execution" in skill_ids
        assert "chat" in skill_ids

    def test_card_has_streaming(self):
        from agents.hephaestus.__main__ import build_agent_card

        card = build_agent_card()
        assert card.capabilities.streaming is True

    def test_card_version(self):
        from agents.hephaestus.__main__ import build_agent_card

        card = build_agent_card()
        assert card.version == "0.1.0"
