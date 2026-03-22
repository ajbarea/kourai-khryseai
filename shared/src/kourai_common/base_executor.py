"""Base agent executor with shared A2A protocol lifecycle.

All Kourai agent executors share 40-50 lines of identical A2A boilerplate:
task creation, input validation. This base class eliminates that duplication
and provides a template method pattern for agent logic.

Note: Error handling is done via @executor_error_handler decorator, not here.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.tasks import TaskUpdater
from a2a.types import InternalError, Task
from a2a.utils import new_task
from a2a.utils.errors import ServerError

from kourai_common.messaging import send_input_required

if TYPE_CHECKING:
    from a2a.server.events import EventQueue

log = logging.getLogger(__name__)


class BaseAgentExecutor(AgentExecutor, ABC):
    """Base class for all Kourai agent executors with shared A2A lifecycle.

    Handles common A2A protocol concerns:
    - Task creation from message
    - Empty input validation → input_required status

    Subclasses implement only agent-specific logic via execute_agent_logic().
    Use @executor_error_handler decorator on execute() for error handling.
    """

    @abstractmethod
    def get_input_required_message(self) -> str:
        """Return the message to show when user provides empty input."""

    @abstractmethod
    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        """Execute agent-specific logic.

        Called after task/updater are initialized and input is validated.
        Should emit artifacts and call updater.complete() when done.
        """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute agent with shared A2A protocol lifecycle.

        NOTE: Subclasses should apply @executor_error_handler decorator to this method.
        """
        user_input = context.get_user_input()
        task = context.current_task

        # Create task from message if needed
        if not task and context.message:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        if not task:
            log.error("No task or message in request context")
            raise ServerError(error=InternalError())

        updater = TaskUpdater(event_queue, task.id, task.context_id)

        # Validate input and return early if empty
        if not user_input or not user_input.strip():
            await send_input_required(
                updater,
                task,
                self.get_input_required_message(),
            )
            return

        # Execute agent-specific logic
        await self.execute_agent_logic(context, task, updater)
