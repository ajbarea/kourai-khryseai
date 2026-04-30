"""Shared A2A server builder for Kourai Khryseai specialists.

Every agent's ``__main__.py`` constructs the same ``A2AStarletteApplication``
+ ``DefaultRequestHandler`` + ``InMemoryTaskStore`` triple. The ten copies
were ~10 identical lines apiece; this helper is the single source of
truth so the M7 Phase 3 flip to ``create_agent_card_routes`` +
``create_jsonrpc_routes`` is one file change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore

if TYPE_CHECKING:
    from a2a.server.agent_execution import AgentExecutor
    from a2a.server.tasks import TaskStore
    from a2a.types import AgentCard
    from starlette.applications import Starlette


def build_a2a_app(
    *,
    agent_card: AgentCard,
    executor: AgentExecutor,
    task_store: TaskStore | None = None,
) -> Starlette:
    """Build the Starlette ASGI app every Kourai specialist serves.

    Args:
        agent_card: The agent's published AgentCard. Mounted at
            ``/.well-known/agent-card.json`` for discovery.
        executor: The agent's :class:`AgentExecutor` implementation.
        task_store: Optional TaskStore. Defaults to ``InMemoryTaskStore``
            (the existing per-agent default).
    """
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=task_store or InMemoryTaskStore(),
    )
    app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )
    return app.build()
