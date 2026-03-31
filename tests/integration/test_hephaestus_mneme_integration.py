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

            # The final output should contain our mock response from litellm_mock_config.yaml
            assert any("MOCK RESPONSE" in res for res in results), (
                f"Mock response not found in results: {results}"
            )
            assert any("specialist maiden" in res for res in results)
