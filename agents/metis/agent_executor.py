"""A2A bridge for Metis — translates between A2A protocol and planner logic."""

from __future__ import annotations

import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InternalError,
    Part,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError

from agents.metis.agent import create_spec, get_project_context
from kourai_common.tracing import create_span

log = logging.getLogger(__name__)


class MetisAgentExecutor(AgentExecutor):
    """A2A executor for the Metis planner agent."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        with create_span("metis.execute", {"a2a.method": "execute"}):
            user_input = context.get_user_input()
            task = context.current_task

            if not task and context.message:
                task = new_task(context.message)
                await event_queue.enqueue_event(task)

            if not task:
                log.error("No task or message in request context")
                raise ServerError(error=InternalError())

            updater = TaskUpdater(event_queue, task.id, task.context_id)

            if not user_input or not user_input.strip():
                await updater.update_status(
                    TaskState.input_required,
                    new_agent_text_message(
                        "What feature or change do you want me to plan? "
                        "Describe your idea and I'll create a detailed spec.",
                        task.context_id,
                        task.id,
                    ),
                    final=True,
                )
                return

            try:
                # Step 1: Gather project context
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        "\U0001f4d0 Analyzing project structure...",
                        task.context_id,
                        task.id,
                    ),
                )

                with create_span("metis.context"):
                    project_context = await get_project_context()

                # Step 2: Generate spec
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        "\U0001f4d0 Drafting implementation spec...",
                        task.context_id,
                        task.id,
                    ),
                )

                with create_span("metis.spec", {"idea": user_input[:100]}):
                    spec = await create_spec(
                        idea=user_input,
                        project_context=project_context,
                    )

                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        "\U0001f4d0 Spec complete",
                        task.context_id,
                        task.id,
                    ),
                )

                # Step 3: Emit artifact
                await updater.add_artifact(
                    [Part(root=TextPart(text=spec))],
                    name="implementation_spec",
                )
                await updater.complete()
                log.info("Metis completed — spec generated")

            except Exception as e:
                log.error("Metis execution failed: %s", e)
                raise ServerError(error=InternalError()) from e

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        raise ServerError(error=UnsupportedOperationError())
