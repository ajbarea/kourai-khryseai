"""Shared A2A server builder for Kourai Khryseai specialists.

Every agent's ``__main__.py`` calls :func:`build_a2a_app` to construct
its Starlette ASGI app. The 1.0 SDK retired ``A2AStarletteApplication``
in favour of ``create_agent_card_routes`` + ``create_jsonrpc_routes``;
this helper wraps those route factories. M7 Phase 6 retired the
``enable_v0_3_compat`` shim — every kourai client now speaks 1.0
natively.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from starlette.applications import Starlette

if TYPE_CHECKING:
    from a2a.server.agent_execution import AgentExecutor
    from a2a.server.tasks import TaskStore
    from a2a.types import AgentCard


def build_a2a_app(
    *,
    agent_card: AgentCard,
    executor: AgentExecutor,
    task_store: TaskStore | None = None,
) -> Starlette:
    """Build the Starlette ASGI app every Kourai specialist serves.

    Args:
        agent_card: The agent's published AgentCard. Mounted at the
            v1.0 well-known agent-card path for discovery.
        executor: The agent's :class:`AgentExecutor` implementation.
        task_store: Optional TaskStore. Defaults to ``InMemoryTaskStore``.
    """
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=task_store or InMemoryTaskStore(),
        agent_card=agent_card,
    )
    routes = []
    routes.extend(create_agent_card_routes(agent_card))
    routes.extend(create_jsonrpc_routes(request_handler, rpc_url="/"))

    @asynccontextmanager
    async def lifespan(app: Starlette):
        # Startup (nothing needed)
        yield
        # Shutdown: close aiohttp session to prevent resource leaks
        from kourai_common.llm_aiohttp_config import close_aiohttp_session
        await close_aiohttp_session()

    app = Starlette(routes=routes, lifespan=lifespan)

    return app
