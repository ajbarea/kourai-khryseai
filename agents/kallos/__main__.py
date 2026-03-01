"""Kallos A2A server — entry point.

Start with: python -m agents.kallos
"""

from __future__ import annotations

import logging
import os

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agents.kallos.agent_executor import KallosAgentExecutor
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT
from kourai_common.tracing import setup_tracing

logging.basicConfig(
    level=os.getenv("KOURAI_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

AGENT_NAME = "kallos"
PORT = int(os.getenv("PORT", str(AGENT_PORTS[AGENT_NAME])))
HOST = os.getenv("HOST", "0.0.0.0")


def build_agent_card() -> AgentCard:
    """Construct the Kallos agent card."""
    skill = AgentSkill(
        id="style_check",
        name="Code Style Check & Cleanup",
        description=(
            "Run linters, fix formatting, clean comments/docstrings "
            "per AJ's style guides. Reports issues and suggested fixes."
        ),
        tags=["linting", "formatting", "style", "cleanup"],
        examples=[
            "clean up comments in src/utils/",
            "run make lint and fix issues",
            "standardize docstrings in the API module",
        ],
    )
    return AgentCard(
        name="Kallos — Stylist",
        description=(
            "Code style specialist. Runs ruff linter/formatter, analyzes "
            "comments and docstrings, enforces AJ's quality standards. "
            "Reports issues — hands off to Techne for fixes if needed."
        ),
        url=f"http://{HOST}:{PORT}/",
        version="0.1.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )


def main() -> None:
    """Start the Kallos A2A server."""
    setup_tracing(AGENT_NAME, OTEL_ENDPOINT)

    agent_card = build_agent_card()
    request_handler = DefaultRequestHandler(
        agent_executor=KallosAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    log.info("✨ Kallos starting on %s:%d", HOST, PORT)
    uvicorn.run(server.build(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
