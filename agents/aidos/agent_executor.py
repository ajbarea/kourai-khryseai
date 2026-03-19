"""A2A executor for Aidos — anti-slop language enforcer."""

from __future__ import annotations

import logging

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.aidos.agent import analyze_slop, flag_slop_words
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.messaging import send_working_status

log = logging.getLogger(__name__)


class AidosAgentExecutor(BaseAgentExecutor):
    """A2A executor for Aidos."""

    def get_input_required_message(self) -> str:
        return "Give me the text to review for slop."

    @executor_error_handler(agent_name="aidos")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        user_input = context.get_user_input()

        # Fast pre-screen
        slop_words = flag_slop_words(user_input)
        if slop_words:
            await send_working_status(
                updater,
                task,
                f"Found {len(slop_words)} slop word(s): {', '.join(slop_words[:5])}",
                emoji="🚫",
            )
        else:
            await send_working_status(updater, task, "Scanning for slop...", emoji="🔍")

        result = await analyze_slop(user_input, context_id=task.context_id)

        await updater.add_artifact(
            [
                Part(root=TextPart(text=result)),
                Part(
                    root=DataPart(data={"slop_words_found": slop_words, "clean": result == "CLEAN"})
                ),
            ],
            name="aidos_analysis",
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
