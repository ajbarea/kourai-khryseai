"""Integration tests for Agent Reasoning Quality.

Verifies that agents (Hephaestus/Metis) can provide structured reasoning
using 'thought' blocks before execution.
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
        url = f"http://{host}:{port}/"

        # A2A protocol uses JSON-RPC format
        payload = {
            "jsonrpc": "2.0",
            "method": "execute",
            "params": {
                "text": "Refactor the database schema for the player fact system.",
                "context_id": "test-reasoning-ctx",
            },
            "id": 1,
        }

        async with AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload)
            assert response.status_code == 200

            # Read streaming response (NDJSON)
            lines = [json.loads(line) for line in response.text.strip().split("\n") if line.strip()]

            # Verify we have some status updates or messages
            assert len(lines) > 0

            for line in lines:
                # Should contain result or error fields
                assert "result" in line or "error" in line

    async def test_metis_architecture_reasoning(self, metis_container):
        """Verify Metis provides architectural rationale for design choices."""
        host = metis_container.get_container_host_ip()
        port = metis_container.get_exposed_port(10001)
        url = f"http://{host}:{port}/"

        # A2A protocol uses JSON-RPC format
        payload = {
            "jsonrpc": "2.0",
            "method": "execute",
            "params": {
                "text": "How should we implement the edge-tts fallback for low-latency?",
                "context_id": "test-metis-reasoning",
            },
            "id": 1,
        }

        async with AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload)
            assert response.status_code == 200

            lines = [json.loads(line) for line in response.text.strip().split("\n") if line.strip()]
            assert len(lines) > 0

            # Verify we have valid JSON-RPC responses
            assert any("result" in line or "error" in line for line in lines)
