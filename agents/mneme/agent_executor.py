"""A2A bridge for Mneme — translates between A2A protocol and agent logic."""

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

from agents.mneme.agent import generate_commit_messages_stream
from kourai_common.tracing import create_span

log = logging.getLogger(__name__)


class MnemeAgentExecutor(AgentExecutor):
    """A2A executor for the Mneme scribe agent."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        with create_span("mneme.execute", {"a2a.method": "execute"}):
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
                        "I need git diff output to generate commit messages. "
                        "Please provide git status and diff output.",
                        task.context_id,
                        task.id,
                    ),
                    final=True,
                )
                return

            try:
                # Stream the response, emitting working status updates
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        "📜 Analyzing git changes...",
                        task.context_id,
                        task.id,
                    ),
                )

                full_response = ""
                async for chunk in generate_commit_messages_stream(user_input):
                    full_response += chunk

                # Emit the final artifact with complete commit messages
                await updater.add_artifact(
                    [Part(root=TextPart(text=full_response))],
                    name="commit_messages",
                )
                await updater.complete()
                log.info("Mneme completed — generated commit messages")

            except Exception as e:
                log.error("Mneme execution failed: %s", e)
                raise ServerError(error=InternalError()) from e

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        raise ServerError(error=UnsupportedOperationError())
