"""Error handling decorator for agent executors — consistent error logging."""

from __future__ import annotations

import logging
from functools import wraps
from typing import TYPE_CHECKING, Any

from a2a.types import InternalError

if TYPE_CHECKING:
    from collections.abc import Callable

    from a2a.server.agent_execution import RequestContext
    from a2a.server.events import EventQueue

log = logging.getLogger(__name__)


def executor_error_handler(agent_name: str) -> Callable:
    """Decorator for consistent error handling in agent executors.

    Wraps async execute() methods to catch all exceptions, log them with
    the agent name, and re-raise as a v1.0 ``InternalError`` so the
    JSON-RPC layer maps it to the right status code.

    Args:
        agent_name: Name of the agent for error logging (e.g., "techne", "kallos")

    Returns:
        Decorator function that wraps execute() methods

    Example:
        @executor_error_handler(agent_name="techne")
        async def execute(self, context, event_queue):
            # No try/except needed
            await do_work()
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self: Any, context: RequestContext, event_queue: EventQueue) -> Any:
            try:
                return await func(self, context, event_queue)
            except Exception as e:
                log.error("%s execution failed: %s", agent_name, e)
                raise InternalError() from e

        return wrapper

    return decorator
