"""A2A bridge for Metis — translates between A2A protocol and planner logic."""

from __future__ import annotations

import logging

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.metis.agent import create_spec_stream, get_project_context
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

            # Step 2: Stream spec generation with inner-thought updates
            await send_working_status(
                updater,
                task,
                "Drafting implementation spec...",
                emoji="📐",
            )

            with create_span("metis.spec", {"idea": user_input[:100]}):
                spec = ""
                chunk_count = 0
                async for chunk in create_spec_stream(
                    idea=user_input,
                    project_context=project_context,
                    image_parts=extract_image_parts(context) or None,
                    context_id=task.context_id,
                ):
                    spec += chunk
                    chunk_count += 1
                    if chunk_count % 5 == 0:
                        lines = spec.strip().split("\n")
                        latest = lines[-1] if lines else ""
                        if len(latest) > 60:
                            latest = latest[:57] + "..."
                        if latest.strip():
                            await send_working_status(
                                updater, task, f"Planning: {latest}", emoji="📐"
                            )

            await send_working_status(
                updater,
                task,
                "Spec complete",
                emoji="📐",
            )

            # Step 3: Emit both human-readable text and machine-readable structured data
            # Parse spec sections for downstream routing
            sections = [
                s.strip()
                for s in spec.split("\n")
                if s.strip().startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7."))
            ]
            await updater.add_artifact(
                [
                    Part(root=TextPart(text=spec)),
                    Part(
                        root=DataPart(
                            data={
                                "step_count": len(sections),
                                "has_file_list": "files to modify" in spec.lower()
                                or "files to create" in spec.lower(),
                                "has_tests": "testing" in spec.lower(),
                            }
                        )
                    ),
                ],
                name="implementation_spec",
            )
            await updater.complete()
            log.info("Metis completed — spec generated (%d steps)", len(sections))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
