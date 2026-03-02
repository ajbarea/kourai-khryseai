"""A2A bridge for Hephaestus — orchestrator executor with streaming progress."""

from __future__ import annotations

import logging
import traceback

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

from agents.hephaestus.routing_agent import determine_pipeline, execute_pipeline
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


class HephaestusAgentExecutor(AgentExecutor):
    """A2A executor for the Hephaestus orchestrator."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        log.info("Hephaestus execute triggered")
        try:
            with create_span("hephaestus.execute", {"a2a.method": "execute"}):
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
                            "What would you like me to help with? "
                            "I can route your request to the right specialist agents.",
                            task.context_id,
                            task.id,
                        ),
                        final=True,
                    )
                    return

                # Step 1: Determine the pipeline
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        f"{AGENT_EMOJI['hephaestus']} Analyzing request...",
                        task.context_id,
                        task.id,
                    ),
                )

                pipeline = await determine_pipeline(user_input)

                # Handle clarification request
                if isinstance(pipeline, str):
                    clarification = pipeline.replace("ASK_USER:", "").strip()
                    await updater.update_status(
                        TaskState.input_required,
                        new_agent_text_message(clarification, task.context_id, task.id),
                        final=True,
                    )
                    return

                # Step 2: Report the pipeline
                pipeline_display = " -> ".join(pipeline)
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        f"{AGENT_EMOJI['hephaestus']} Pipeline: {pipeline_display}",
                        task.context_id,
                        task.id,
                    ),
                )

                # Step 3: Execute pipeline with real-time status updates
                final_output = ""
                input_required = False
                async for agent_name, status in execute_pipeline(
                    pipeline, user_input, task.context_id
                ):
                    # Detect INPUT_REQUIRED from specialist agents
                    if status.startswith("INPUT_REQUIRED:"):
                        question = status.removeprefix("INPUT_REQUIRED:")
                        emoji = AGENT_EMOJI.get(agent_name, "")
                        await updater.update_status(
                            TaskState.input_required,
                            new_agent_text_message(
                                f"{emoji} {agent_name} needs your input: {question}",
                                task.context_id,
                                task.id,
                            ),
                            final=True,
                        )
                        input_required = True
                        break

                    emoji = AGENT_EMOJI.get(agent_name, "")
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            f"{emoji} {status}",
                            task.context_id,
                            task.id,
                        ),
                    )
                    final_output = status

                if input_required:
                    return

                # Step 4: Emit final artifact with accumulated results
                await updater.add_artifact(
                    [Part(root=TextPart(text=final_output))],
                    name="pipeline_result",
                )
                await updater.complete()
                log.info("Hephaestus pipeline completed: %s", pipeline_display)

        except Exception as e:
            log.error("Hephaestus execution failed: %s", e)
            log.error(traceback.format_exc())
            # Don't let the server crash, return a proper JSON-RPC error
            raise ServerError(error=InternalError()) from e

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        raise ServerError(error=UnsupportedOperationError())
