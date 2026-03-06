"""A2A bridge for Kallos — translates between A2A protocol and style agent logic."""

from __future__ import annotations

import logging

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.tracing import create_span

log = logging.getLogger(__name__)


class KallosAgentExecutor(BaseAgentExecutor):
    """A2A executor for the Kallos stylist agent."""

    def get_input_required_message(self) -> str:
        return (
            "I need a target path or file contents to analyze. "
            "Please provide a directory path or code to check."
        )

    @executor_error_handler(agent_name="kallos")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        """Kallos-specific: run linting and auto-fix issues."""
        with create_span("kallos.execute", {"a2a.method": "execute"}):
            from agents.kallos.agent import fix_lint_issues, run_make_lint
            from kourai_common.fix_loop import KALLOS_MESSAGES, run_fix_loop
            from kourai_common.subprocess import extract_files_from_output, parse_and_apply_fixes

            # Run iterative lint-fix loop with personality messages
            all_clean, final_output, result = await run_fix_loop(
                tool_name="make lint",
                run_tool=run_make_lint,
                extract_files=extract_files_from_output,
                fix_issues=fix_lint_issues,
                apply_fixes=parse_and_apply_fixes,
                updater=updater,
                task=task,
                emoji="✨",
                messages=KALLOS_MESSAGES,
            )

            # Format final output
            if all_clean:
                final_output = "✨ All linting checks passed!\n\n" + final_output
            else:
                final_output = f"✨ Linting completed with issues.\n\n{final_output}"

            # Emit both human-readable text and machine-readable structured data
            await updater.add_artifact(
                [
                    Part(root=TextPart(text=final_output)),
                    Part(root=DataPart(data=result.to_dict())),
                ],
                name="style_report",
            )

            status = "all clean" if all_clean else "issues remain"
            await updater.complete()
            log.info("Kallos completed — %s", status)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
