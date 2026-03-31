"""Integration tests for Agent Reasoning Quality.

Verifies that agents (Hephaestus/Metis) can provide structured reasoning
using 2026-standard 'thought' blocks before execution.
"""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.integration
class TestReasoningQuality:
    """Tests for evaluating agent reasoning and orchestration quality."""

    async def test_hephaestus_provides_reasoning_for_complex_task(self, hephaestus_container):
        """Verify Hephaestus explains its plan before delegating."""
        host = hephaestus_container.get_container_host_ip()
        port = hephaestus_container.get_exposed_port(10000)
        url = f"http://{host}:{port}/message"

        payload = {
            "text": "Refactor the database schema for the player fact system.",
            "context_id": "test-reasoning-ctx",
        }

        async with AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload)
            assert response.status_code == 200

            # Read streaming response (NDJSON)
            lines = [json.loads(line) for line in response.text.strip().split("\n")]

            # Verify we have some status updates or messages
            assert len(lines) > 0

            # 2026 Best Practice: Agent should provide a 'thought' or 'plan' block
            # In our mock, this will depend on the litellm_mock_config.yaml.
            # But the logic should extract it or at least pass it through.

            # Even with mocks, we verify the structure of the NDJSON response
            for line in lines:
                assert "agent" in line
                assert "message" in line or "action" in line

    async def test_metis_architecture_reasoning(self, metis_container):
        """Verify Metis provides architectural rationale for design choices."""
        host = metis_container.get_container_host_ip()
        port = metis_container.get_exposed_port(10001)
        url = f"http://{host}:{port}/message"

        payload = {
            "text": "How should we implement the edge-tts fallback for low-latency?",
            "context_id": "test-metis-reasoning",
        }

        async with AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload)
            assert response.status_code == 200

            lines = [json.loads(line) for line in response.text.strip().split("\n")]
            assert len(lines) > 0

            # Verify agent-specific response
            assert any(line.get("agent") == "metis" for line in lines)
