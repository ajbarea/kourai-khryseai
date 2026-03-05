"""Error handling decorator for agent executors — consistent error logging."""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps

from a2a.types import InternalError
from a2a.utils.errors import ServerError

log = logging.getLogger(__name__)


def executor_error_handler(agent_name: str) -> Callable:
    """Decorator for consistent error handling in agent executors.

    Wraps async execute() methods to catch all exceptions, log them with
    the agent name, and raise proper A2A ServerError with InternalError.

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
        async def wrapper(self, context, event_queue):
            try:
                return await func(self, context, event_queue)
            except Exception as e:
                log.error("%s execution failed: %s", agent_name, e)
                raise ServerError(error=InternalError()) from e

        return wrapper

    return decorator
