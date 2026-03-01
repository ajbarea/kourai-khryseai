"""A2A bridge for Techne — translates between A2A protocol and coder agent logic."""

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

from agents.techne.agent import (
    generate_code,
    get_git_context,
    parse_file_paths,
    read_files,
)
from kourai_common.tracing import create_span

log = logging.getLogger(__name__)


class TechneAgentExecutor(AgentExecutor):
    """A2A executor for the Techne coder agent."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        with create_span("techne.execute", {"a2a.method": "execute"}):
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
                        "I need a coding task. Tell me what to implement, "
                        "fix, or modify — ideally with file paths.",
                        task.context_id,
                        task.id,
                    ),
                    final=True,
                )
                return

            try:
                # Step 1: Parse file paths from the request
                file_paths = parse_file_paths(user_input)

                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        "\u2699\ufe0f Reading existing code..."
                        + (f" ({len(file_paths)} files)" if file_paths else ""),
                        task.context_id,
                        task.id,
                    ),
                )

                # Step 2: Read existing files for context
                file_contents = {}
                if file_paths:
                    with create_span("techne.read_files", {"count": str(len(file_paths))}):
                        file_contents = await read_files(file_paths)

                # Step 3: Get git context
                with create_span("techne.git_context"):
                    git_context = await get_git_context()

                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        "\u2699\ufe0f Generating code changes...",
                        task.context_id,
                        task.id,
                    ),
                )

                # Step 4: Generate code
                with create_span("techne.generate", {"task": user_input[:100]}):
                    result = await generate_code(
                        task_description=user_input,
                        file_contents=file_contents,
                        git_context=git_context,
                    )

                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        "\u2699\ufe0f Code generation complete",
                        task.context_id,
                        task.id,
                    ),
                )

                # Step 5: Emit final artifact
                await updater.add_artifact(
                    [Part(root=TextPart(text=result))],
                    name="code_changes",
                )
                await updater.complete()
                log.info("Techne completed code generation")

            except Exception as e:
                log.error("Techne execution failed: %s", e)
                raise ServerError(error=InternalError()) from e

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        raise ServerError(error=UnsupportedOperationError())
