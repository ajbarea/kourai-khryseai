"""Dokimasia A2A server — entry point.

Start with: python -m agents.dokimasia
"""

from __future__ import annotations

import os

import uvicorn
from a2a.types import AgentCard, AgentSkill

from agents.dokimasia.agent_executor import DokimasiaAgentExecutor
from kourai_common.agent_cards import build_card
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT
from kourai_common.log import setup_logging
from kourai_common.server import build_a2a_app
from kourai_common.tracing import setup_tracing

AGENT_NAME = "dokimasia"
log = setup_logging(AGENT_NAME)
PORT = int(os.getenv("PORT", str(AGENT_PORTS[AGENT_NAME])))
HOST = os.getenv("HOST", "0.0.0.0")  # noqa: S104


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
    return build_card(
        agent_name=AGENT_NAME,
        display_name="Dokimasia — Tester",
        description=(
            "Testing specialist. Writes pytest test suites and runs them. "
            "Priority: unit > integration > performance. Targets 80%+ coverage. "
            "Reports results in structured tables."
        ),
        skills=[write_skill, run_skill],
        input_modes=["text", "image"],
    )


def main() -> None:
    """Start the Dokimasia A2A server."""
    setup_tracing(AGENT_NAME, OTEL_ENDPOINT)
    app = build_a2a_app(agent_card=build_agent_card(), executor=DokimasiaAgentExecutor())
    log.info("\U0001f9ea Dokimasia starting on %s:%d", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
