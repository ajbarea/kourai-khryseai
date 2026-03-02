"""Dokimasia A2A server — entry point.

Start with: python -m agents.dokimasia
"""

from __future__ import annotations

import logging
import os

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agents.dokimasia.agent_executor import DokimasiaAgentExecutor
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT, get_agent_url
from kourai_common.tracing import setup_tracing

logging.basicConfig(
    level=os.getenv("KOURAI_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

AGENT_NAME = "dokimasia"
PORT = int(os.getenv("PORT", str(AGENT_PORTS[AGENT_NAME])))
HOST = os.getenv("HOST", "0.0.0.0")


def build_agent_card() -> AgentCard:
    """Construct the Dokimasia agent card."""
    write_skill = AgentSkill(
        id="write_tests",
        name="Write Test Suites",
        description=(
            "Create pytest tests: unit first, then integration, then "
            "performance. Target 80%+ coverage."
        ),
        tags=["testing", "pytest", "unit-tests", "integration-tests"],
        examples=[
            "write unit tests for src/utils/parser.py",
            "add integration tests for the API endpoints",
            "test the new CSV export feature",
        ],
    )
    run_skill = AgentSkill(
        id="run_tests",
        name="Run Test Suite",
        description="Execute make test and report structured results",
        tags=["testing", "ci", "quality"],
        examples=[
            "run all tests",
            "run tests for the payment module",
            "check coverage",
        ],
    )
    return AgentCard(
        name="Dokimasia — Tester",
        description=(
            "Testing specialist. Writes pytest test suites and runs them. "
            "Priority: unit > integration > performance. Targets 80%+ coverage. "
            "Reports results in structured tables."
        ),
        url=get_agent_url(AGENT_NAME),
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[write_skill, run_skill],
    )


def main() -> None:
    """Start the Dokimasia A2A server."""
    setup_tracing(AGENT_NAME, OTEL_ENDPOINT)

    agent_card = build_agent_card()
    request_handler = DefaultRequestHandler(
        agent_executor=DokimasiaAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    log.info("\U0001f9ea Dokimasia starting on %s:%d", HOST, PORT)
    uvicorn.run(server.build(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
