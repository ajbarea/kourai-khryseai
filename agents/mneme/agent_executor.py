"""A2A bridge for Mneme — translates between A2A protocol and agent logic."""

from __future__ import annotations

import logging

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.mneme.agent import generate_commit_messages_stream
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.messaging import send_working_status
from kourai_common.tracing import create_span

log = logging.getLogger(__name__)


class MnemeAgentExecutor(BaseAgentExecutor):
    """A2A executor for the Mneme scribe agent."""

    def get_input_required_message(self) -> str:
        return (
            "I need git diff output to generate commit messages. "
            "Please provide git status and diff output."
        )

    @executor_error_handler(agent_name="mneme")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        """Mneme-specific: generate commit messages from git diff."""
        with create_span("mneme.execute", {"a2a.method": "execute"}):
            user_input = context.get_user_input()

            # Stream the response, emitting working status updates
            await send_working_status(
                updater,
                task,
                "Analyzing git changes...",
                emoji="📜",
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

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
