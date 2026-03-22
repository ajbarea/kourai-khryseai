"""A2A executor for Aletheia — research validator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from a2a.types import DataPart, Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.aletheia.agent import find_unsupported_claims, validate_research
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.messaging import send_working_status

if TYPE_CHECKING:
    from a2a.server.agent_execution import RequestContext
    from a2a.server.events import EventQueue
    from a2a.server.tasks import TaskUpdater

log = logging.getLogger(__name__)


class AletheiaAgentExecutor(BaseAgentExecutor):
    """A2A executor for Aletheia."""

    def get_input_required_message(self) -> str:
        return "Provide the text to validate for research citations."

    @executor_error_handler(agent_name="aletheia")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        user_input = context.get_user_input()

        claims = find_unsupported_claims(user_input)
        if claims:
            await send_working_status(
                updater,
                task,
                f"Found {len(claims)} algorithmic claim(s) to verify",
                emoji="🔬",
            )
        else:
            await send_working_status(
                updater, task, "Scanning for unverified claims...", emoji="🔍"
            )

        result = await validate_research(user_input, context_id=task.context_id)

        await updater.add_artifact(
            [
                Part(root=TextPart(text=result)),
                Part(
                    root=DataPart(
                        data={
                            "claims_found": len(claims),
                            "verified": result == "VERIFIED",
                        }
                    )
                ),
            ],
            name="aletheia_validation",
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
