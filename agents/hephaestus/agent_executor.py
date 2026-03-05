"""A2A bridge for Hephaestus — orchestrator executor with streaming progress."""

from __future__ import annotations

import logging

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.hephaestus.routing_agent import determine_pipeline, execute_pipeline
from kourai_common.a2a_utils import extract_file_attachments
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.messaging import send_input_required, send_working_status
from kourai_common.tracing import create_span

log = logging.getLogger(__name__)


# Emoji map for status messages
AGENT_EMOJI = {
    "hephaestus": "\U0001f525",  # fire
    "metis": "\U0001f4d0",  # triangular ruler
    "techne": "\u2699\ufe0f",  # gear
    "dokimasia": "\U0001f9ea",  # test tube
    "kallos": "\u2728",  # sparkles
    "mneme": "\U0001f4dc",  # scroll
}


class HephaestusAgentExecutor(BaseAgentExecutor):
    """A2A executor for the Hephaestus orchestrator."""

    def get_input_required_message(self) -> str:
        return (
            "What would you like me to help with? "
            "I can route your request to the right specialist agents."
        )

    @executor_error_handler(agent_name="hephaestus")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        log.info("Hephaestus execute triggered")
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        """Hephaestus-specific: determine pipeline and orchestrate specialist agents."""
        with create_span("hephaestus.execute", {"a2a.method": "execute"}):
            user_input = context.get_user_input()

            # Step 1: Determine the pipeline
            await send_working_status(
                updater,
                task,
                "Analyzing request...",
                emoji=AGENT_EMOJI["hephaestus"],
            )

            pipeline = await determine_pipeline(user_input)

            # Handle clarification request
            if isinstance(pipeline, str):
                clarification = pipeline.replace("ASK_USER:", "").strip()
                await send_input_required(
                    updater,
                    task,
                    clarification,
                )
                return

            # Step 2: Report the pipeline
            pipeline_display = " -> ".join(pipeline)
            await send_working_status(
                updater,
                task,
                f"Pipeline: {pipeline_display}",
                emoji=AGENT_EMOJI["hephaestus"],
            )

            # Step 3: Execute pipeline with real-time status updates
            image_attachments = extract_file_attachments(context)
            last_agent_output = ""
            input_required = False
            async for agent_name, status, agent_output in execute_pipeline(
                pipeline, user_input, task.context_id, image_attachments or None
            ):
                # Detect INPUT_REQUIRED from specialist agents
                if status.startswith("INPUT_REQUIRED:"):
                    question = status.removeprefix("INPUT_REQUIRED:")
                    emoji = AGENT_EMOJI.get(agent_name, "")
                    await send_input_required(
                        updater,
                        task,
                        f"{emoji} {agent_name} needs your input: {question}",
                    )
                    input_required = True
                    break

                emoji = AGENT_EMOJI.get(agent_name, "")
                await send_working_status(
                    updater,
                    task,
                    status,
                    emoji=emoji,
                )
                # Track the last real agent output for the final artifact
                if agent_output:
                    last_agent_output = agent_output

            if input_required:
                return

            # Step 4: Emit final artifact with the last agent's actual output
            await updater.add_artifact(
                [Part(root=TextPart(text=last_agent_output or "Pipeline complete"))],
                name="pipeline_result",
            )
            await updater.complete()
            log.info("Hephaestus pipeline completed: %s", pipeline_display)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
