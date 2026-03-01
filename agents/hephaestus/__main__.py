"""Hephaestus A2A server — orchestrator entry point.

Start with: python -m agents.hephaestus
"""

from __future__ import annotations

import logging
import os

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agents.hephaestus.agent_executor import HephaestusAgentExecutor
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT
from kourai_common.tracing import setup_tracing

logging.basicConfig(
    level=os.getenv("KOURAI_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

AGENT_NAME = "hephaestus"
PORT = int(os.getenv("PORT", str(AGENT_PORTS[AGENT_NAME])))
HOST = os.getenv("HOST", "0.0.0.0")


def build_agent_card() -> AgentCard:
    """Construct the Hephaestus agent card."""
    route_skill = AgentSkill(
        id="route_request",
        name="Route Development Request",
        description=(
            "Analyze user request and route to the right specialist agents in the correct order"
        ),
        tags=["orchestration", "routing", "pipeline"],
        examples=[
            "implement a CSV export feature",
            "fix the login bug in auth.py",
            "add tests for the payment module",
            "clean up comments in src/utils/",
        ],
    )
    pipeline_skill = AgentSkill(
        id="pipeline_execution",
        name="Execute Development Pipeline",
        description=("Run multi-step workflows: plan -> code -> test -> style -> commit"),
        tags=["pipeline", "workflow", "automation"],
        examples=[
            "full pipeline for feature X",
            "code and test this change",
            "style check and commit prep",
        ],
    )
    return AgentCard(
        name="Hephaestus — Orchestrator",
        description=(
            "Master orchestrator of Kourai Khryseai. Receives user requests, "
            "determines which specialist agents to invoke, executes the pipeline, "
            "and streams real-time progress back to the user."
        ),
        url=f"http://{HOST}:{PORT}/",
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[route_skill, pipeline_skill],
    )


def main() -> None:
    """Start the Hephaestus A2A server."""
    setup_tracing(AGENT_NAME, OTEL_ENDPOINT)

    agent_card = build_agent_card()
    request_handler = DefaultRequestHandler(
        agent_executor=HephaestusAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    log.info("\U0001f525 Hephaestus starting on %s:%d", HOST, PORT)
    uvicorn.run(server.build(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
