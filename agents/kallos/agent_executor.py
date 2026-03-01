"""A2A bridge for Kallos — translates between A2A protocol and style agent logic."""

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

from agents.kallos.agent import format_report, run_style_check
from kourai_common.tracing import create_span

log = logging.getLogger(__name__)


class KallosAgentExecutor(AgentExecutor):
    """A2A executor for the Kallos stylist agent."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        with create_span("kallos.execute", {"a2a.method": "execute"}):
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
                        "I need a target path or file contents to analyze. "
                        "Please provide a directory path or code to check.",
                        task.context_id,
                        task.id,
                    ),
                    final=True,
                )
                return

            try:
                # Status: starting lint checks
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        "✨ Running ruff check + ruff format...",
                        task.context_id,
                        task.id,
                    ),
                )

                # Extract target path from input (first line or the whole input)
                target_path = user_input.strip().splitlines()[0].strip()

                with create_span("kallos.ruff", {"target": target_path}):
                    report = await run_style_check(target_path)

                # Status: lint complete, reporting results
                lint_summary = ", ".join(
                    f"{r.tool}: {'PASS' if r.passed else 'FAIL'}" for r in report.lint_results
                )
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        f"✨ Lint results: {lint_summary}",
                        task.context_id,
                        task.id,
                    ),
                )

                # Format and emit final artifact
                result_text = format_report(report)
                await updater.add_artifact(
                    [Part(root=TextPart(text=result_text))],
                    name="style_report",
                )

                if report.all_clean:
                    await updater.complete()
                    log.info("Kallos completed — all clean")
                else:
                    # Report issues but still complete (Hephaestus decides next steps)
                    await updater.complete()
                    log.info("Kallos completed — issues found")

            except Exception as e:
                log.error("Kallos execution failed: %s", e)
                raise ServerError(error=InternalError()) from e

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        raise ServerError(error=UnsupportedOperationError())
