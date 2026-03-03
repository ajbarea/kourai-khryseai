"""Metis A2A server — entry point.

Start with: python -m agents.metis
"""

from __future__ import annotations

import logging
import os

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agents.metis.agent_executor import MetisAgentExecutor
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT, get_agent_url
from kourai_common.tracing import setup_tracing

logging.basicConfig(
    level=os.getenv("KOURAI_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

AGENT_NAME = "metis"
PORT = int(os.getenv("PORT", str(AGENT_PORTS[AGENT_NAME])))
HOST = os.getenv("HOST", "0.0.0.0")


def build_agent_card() -> AgentCard:
    """Construct the Metis agent card."""
    skill = AgentSkill(
        id="create_spec",
        name="Create Implementation Specification",
        description=(
            "Transform rough ideas into detailed requirements with file lists, "
            "acceptance criteria, and implementation steps"
        ),
        tags=["planning", "requirements", "specification"],
        examples=[
            "I want a CSV export button on the dashboard",
            "add authentication to the API",
            "refactor the config loader to use pydantic",
        ],
    )
    return AgentCard(
        name="Metis — Planner",
        description=(
            "Planning specialist. Transforms rough ideas into detailed, "
            "implementable specifications with file lists, steps, "
            "acceptance criteria, and edge cases."
        ),
        url=get_agent_url(AGENT_NAME),
        version="0.1.0",
        default_input_modes=["text", "image"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )


def main() -> None:
    """Start the Metis A2A server."""
    setup_tracing(AGENT_NAME, OTEL_ENDPOINT)

    agent_card = build_agent_card()
    request_handler = DefaultRequestHandler(
        agent_executor=MetisAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    log.info("\U0001f4d0 Metis starting on %s:%d", HOST, PORT)
    uvicorn.run(server.build(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
