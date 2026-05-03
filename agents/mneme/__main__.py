"""Mneme A2A server — entry point.

Start with: python -m agents.mneme
"""

from __future__ import annotations

import os

from a2a.types import AgentCard, AgentSkill

from agents.mneme.agent_executor import MnemeAgentExecutor
from kourai_common.agent_cards import build_card
from kourai_common.config import AGENT_PORTS, OTEL_ENDPOINT
from kourai_common.log import run_uvicorn, setup_logging
from kourai_common.server import build_a2a_app
from kourai_common.tracing import setup_tracing

AGENT_NAME = "mneme"
log = setup_logging(AGENT_NAME)
PORT = int(os.getenv("PORT", str(AGENT_PORTS[AGENT_NAME])))
HOST = os.getenv("HOST", "0.0.0.0")  # noqa: S104


def build_agent_card() -> AgentCard:
    """Construct the Mneme agent card."""
    skill = AgentSkill(
        id="generate_commits",
        name="Generate Commit Message Groups",
        description=(
            "Analyze git changes and generate grouped commit messages "
            "following AJ's conventional commit format"
        ),
        tags=["git", "commits", "documentation"],
        examples=[
            "generate commit messages for current changes",
            "group these changes into logical commits",
        ],
    )
    return build_card(
        agent_name=AGENT_NAME,
        display_name="Mneme — Scribe",
        description=(
            "Commit message specialist. Analyzes git diffs and generates "
            "grouped commit messages. Emits structured metadata with "
            "commit counts and types. Never commits — generates only."
        ),
        skills=[skill],
    )


def main() -> None:
    """Start the Mneme A2A server."""
    setup_tracing(AGENT_NAME, OTEL_ENDPOINT)
    app = build_a2a_app(agent_card=build_agent_card(), executor=MnemeAgentExecutor())
    log.info("📜 Mneme starting on %s:%d", HOST, PORT)
    run_uvicorn(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
