"""Integration tests for Hephaestus orchestrator and Mneme specialist.

Verifies the full cycle: Orchestrator -> Specialist -> Mocked LLM.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from testcontainers.core.container import DockerContainer


@pytest.fixture(scope="module")
def agent_urls(
    mneme_container: DockerContainer, hephaestus_container: DockerContainer
) -> dict[str, str]:
    """Provide dynamic URLs for the started agent containers (mapped to host)."""
    m_host = mneme_container.get_container_host_ip()
    m_port = mneme_container.get_exposed_port(10005)

    h_host = hephaestus_container.get_container_host_ip()
    h_port = hephaestus_container.get_exposed_port(10000)

    return {
        "mneme": f"http://{m_host}:{m_port}/",
        "hephaestus": f"http://{h_host}:{h_port}/",
    }


@pytest.mark.asyncio
@pytest.mark.integration
class TestHephaestusMnemeIntegration:
    """Tests the interaction between Hephaestus and Mneme with mocked LLM."""

    async def test_full_cycle_hephaestus_to_mneme_with_mock_llm(self, agent_urls: dict[str, str]):
        """Verify Hephaestus -> Mneme -> Mock LLM pipeline works.

        1. Hephaestus calls Mneme.
        2. Mneme calls the LiteLLM Proxy (mock).
        3. Mneme returns the mock response to Hephaestus.
        """
        from agents.hephaestus.agent import execute_pipeline

        def mocked_get_url(agent_name: str) -> str:
            if agent_name in agent_urls:
                return agent_urls[agent_name]
            return f"http://{agent_name}:10000/"

        pipeline = ["mneme"]
        user_request = "Generate commit messages"

        with patch("agents.hephaestus.agent.get_agent_url", side_effect=mocked_get_url):
            results = []
            async for _agent, _status, output in execute_pipeline(pipeline, user_request):
                if output:
                    results.append(output)

            # Some A2A/LiteLLM stream shapes deliver text, others only structured artifacts.
            # Accept either the mock text response or the serialized metadata artifact.
            assert results, "Expected at least one non-empty result payload from Mneme"
            assert any(
                ("MOCK RESPONSE" in res)
                or ("specialist maiden" in res)
                or ('"commit_count"' in res and '"commit_types"' in res)
                for res in results
            ), f"Expected text or artifact metadata in results, got: {results}"
