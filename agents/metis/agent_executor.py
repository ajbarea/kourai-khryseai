"""A2A bridge for Metis — translates between A2A protocol and planner logic."""

from __future__ import annotations

import logging

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.metis.agent import create_spec, get_project_context
from kourai_common.a2a_utils import extract_image_parts
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.messaging import send_working_status
from kourai_common.tracing import create_span

log = logging.getLogger(__name__)


class MetisAgentExecutor(BaseAgentExecutor):
    """A2A executor for the Metis planner agent."""

    def get_input_required_message(self) -> str:
        return (
            "What feature or change do you want me to plan? "
            "Describe your idea and I'll create a detailed spec."
        )

    @executor_error_handler(agent_name="metis")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        """Metis-specific: create implementation specs."""
        with create_span("metis.execute", {"a2a.method": "execute"}):
            user_input = context.get_user_input()

            # Step 1: Gather project context
            await send_working_status(
                updater,
                task,
                "Analyzing project structure...",
                emoji="📐",
            )

            with create_span("metis.context"):
                project_context = await get_project_context()

            # Step 2: Generate spec
            await send_working_status(
                updater,
                task,
                "Drafting implementation spec...",
                emoji="📐",
            )

            with create_span("metis.spec", {"idea": user_input[:100]}):
                spec = await create_spec(
                    idea=user_input,
                    project_context=project_context,
                    image_parts=extract_image_parts(context) or None,
                    context_id=task.context_id,
                )

            await send_working_status(
                updater,
                task,
                "Spec complete",
                emoji="📐",
            )

            # Step 3: Emit artifact
            await updater.add_artifact(
                [Part(root=TextPart(text=spec))],
                name="implementation_spec",
            )
            await updater.complete()
            log.info("Metis completed — spec generated")

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
