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

                from agents.kallos.agent import (
                    extract_files_from_lint,
                    fix_lint_issues,
                    parse_and_apply_fixes,
                    run_make_lint,
                )

                max_iterations = 3
                iteration = 0
                all_clean = False
                final_output = ""

                while iteration < max_iterations:
                    iteration += 1

                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            f"✨ Running make lint (iteration {iteration}/{max_iterations})...",
                            task.context_id,
                            task.id,
                        ),
                    )

                    with create_span("kallos.make_lint", {"iteration": str(iteration)}):
                        passed, output = await run_make_lint()

                    if passed:
                        all_clean = True
                        final_output = "✨ All linting checks passed!\n\n" + output
                        await updater.update_status(
                            TaskState.working,
                            new_agent_text_message(
                                "✨ Linting passed!",
                                task.context_id,
                                task.id,
                            ),
                        )
                        break

                    # If failed, extract files and ask LLM to fix
                    files_with_issues = extract_files_from_lint(output)
                    if not files_with_issues:
                        final_output = (
                            f"✨ Linting failed, but could not extract file paths.\n\n{output}"
                        )
                        break

                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            f"✨ Found issues in {len(files_with_issues)} files. Fixing...",
                            task.context_id,
                            task.id,
                        ),
                    )

                    with create_span("kallos.fix_issues", {"iteration": str(iteration)}):
                        llm_fixes = await fix_lint_issues(
                            output, files_with_issues, task.context_id
                        )
                        fixes_applied = parse_and_apply_fixes(llm_fixes)

                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            f"✨ Applied {fixes_applied} fixes. Re-running lint...",
                            task.context_id,
                            task.id,
                        ),
                    )
                    final_output = output

                # Format and emit final artifact
                await updater.add_artifact(
                    [Part(root=TextPart(text=final_output))],
                    name="style_report",
                )

                if all_clean:
                    await updater.complete()
                    log.info("Kallos completed — all clean")
                else:
                    await updater.complete()
                    log.info("Kallos completed — issues remain")
            except Exception as e:
                log.error("Kallos execution failed: %s", e)
                raise ServerError(error=InternalError()) from e

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        raise ServerError(error=UnsupportedOperationError())
