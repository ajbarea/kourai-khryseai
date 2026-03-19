"""A2A executor for Cupid — romantic eros spirit."""

from __future__ import annotations

import logging

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.cupid.agent import translate_emotion
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.messaging import send_working_status
from kourai_common.player import PlayerProfile

log = logging.getLogger(__name__)


class CupidAgentExecutor(BaseAgentExecutor):
    """A2A executor for Cupid."""

    def get_input_required_message(self) -> str:
        return "Tell me the situation. I'm very good at these."

    @executor_error_handler(agent_name="cupid")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        user_input = context.get_user_input()

        await send_working_status(updater, task, "Reading the room...", emoji="💘")

        profile = PlayerProfile.load()
        player_id = profile.player_id if profile else ""

        response = await translate_emotion(
            user_input, player_id=player_id, context_id=task.context_id
        )

        await updater.add_artifact(
            [Part(root=TextPart(text=response))],
            name="cupid_response",
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
