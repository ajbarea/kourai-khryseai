"""A2A bridge for Techne — translates between A2A protocol and coder agent logic."""

from __future__ import annotations

import logging

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.techne.agent import generate_code, get_git_context, parse_file_paths, read_files
from kourai_common.a2a_utils import extract_image_parts
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.messaging import send_working_status
from kourai_common.subprocess import parse_and_apply_fixes
from kourai_common.tracing import create_span

log = logging.getLogger(__name__)


class TechneAgentExecutor(BaseAgentExecutor):
    """A2A executor for the Techne coder agent."""

    def get_input_required_message(self) -> str:
        return (
            "I need a coding task. Tell me what to implement, "
            "fix, or modify — ideally with file paths."
        )

    @executor_error_handler(agent_name="techne")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Delegate to base class which calls execute_agent_logic
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        """Techne-specific: generate code changes from task description."""
        with create_span("techne.execute", {"a2a.method": "execute"}):
            user_input = context.get_user_input()

            # Step 1: Parse file paths from the request
            file_paths = parse_file_paths(user_input)

            await send_working_status(
                updater,
                task,
                "Reading existing code..." + (f" ({len(file_paths)} files)" if file_paths else ""),
            )

            # Step 2: Read existing files for context
            file_contents = {}
            if file_paths:
                with create_span("techne.read_files", {"count": str(len(file_paths))}):
                    file_contents = await read_files(file_paths)

            # Step 3: Get git context
            with create_span("techne.git_context"):
                git_context = await get_git_context()

            await send_working_status(
                updater,
                task,
                "Generating code changes...",
            )

            # Step 4: Generate code
            with create_span("techne.generate", {"task": user_input[:100]}):
                result = await generate_code(
                    task_description=user_input,
                    file_contents=file_contents,
                    git_context=git_context,
                    image_parts=extract_image_parts(context) or None,
                    context_id=task.context_id,
                )

            # Step 5: Apply code changes to disk
            # WHY: Without this, cross-agent fix loops are broken — Kallos/Dokimasia
            # would re-check unchanged files every iteration.
            with create_span("techne.apply_fixes"):
                fixes_applied = parse_and_apply_fixes(result)

            await send_working_status(
                updater,
                task,
                f"Applied {fixes_applied} code changes to disk",
            )

            # Step 6: Emit final artifact
            await updater.add_artifact(
                [Part(root=TextPart(text=result))],
                name="code_changes",
            )
            await updater.complete()
            log.info("Techne completed — applied %d fixes to disk", fixes_applied)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
