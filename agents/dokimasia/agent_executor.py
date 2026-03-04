"""A2A bridge for Dokimasia — translates between A2A protocol and tester logic."""

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

from agents.dokimasia.agent import (
    generate_tests,
)
from kourai_common.tracing import create_span

log = logging.getLogger(__name__)


def _extract_image_parts(context: RequestContext) -> list[dict]:
    """Build LiteLLM image_url blocks from any FilePart in the incoming message."""
    from a2a.types import FileWithBytes

    image_parts: list[dict] = []
    if not context.message:
        return image_parts
    for part in context.message.parts:
        root = part.root
        if hasattr(root, "file") and isinstance(root.file, FileWithBytes):
            mime = root.file.mime_type or "image/png"
            image_parts.append(
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{root.file.bytes}"}}
            )
    return image_parts


class DokimasiaAgentExecutor(AgentExecutor):
    """A2A executor for the Dokimasia tester agent."""

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        with create_span("dokimasia.execute", {"a2a.method": "execute"}):
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
                        "I need source code or a module name to write tests for, "
                        "or a test path to run. What should I test?",
                        task.context_id,
                        task.id,
                    ),
                    final=True,
                )
                return

            try:
                input_lower = user_input.lower()
                is_run_request = any(
                    kw in input_lower for kw in ["run test", "make test", "pytest", "run all"]
                )

                if is_run_request:
                    from agents.dokimasia.agent import (
                        extract_files_from_pytest,
                        fix_test_issues,
                        format_test_results,
                        parse_and_apply_fixes,
                        run_pytest,
                    )

                    max_iterations = 3
                    iteration = 0
                    all_passed = False
                    final_report = ""

                    while iteration < max_iterations:
                        iteration += 1

                        # Run existing tests
                        await updater.update_status(
                            TaskState.working,
                            new_agent_text_message(
                                f"🧪 Running pytest (iteration {iteration}/{max_iterations})...",
                                task.context_id,
                                task.id,
                            ),
                        )

                        with create_span("dokimasia.pytest", {"iteration": str(iteration)}):
                            result = await run_pytest()

                        if result.success:
                            all_passed = True
                            final_report = format_test_results(result)
                            await updater.update_status(
                                TaskState.working,
                                new_agent_text_message(
                                    "🧪 All tests passed!",
                                    task.context_id,
                                    task.id,
                                ),
                            )
                            break

                        # If failed, extract files and ask LLM to fix
                        files_with_issues = extract_files_from_pytest(result.output)
                        if not files_with_issues:
                            final_report = (
                                format_test_results(result)
                                + "\n\nCould not extract file paths to fix."
                            )
                            break

                        await updater.update_status(
                            TaskState.working,
                            new_agent_text_message(
                                f"🧪 Found failures involving {len(files_with_issues)} files. "
                                "Fixing...",
                                task.context_id,
                                task.id,
                            ),
                        )

                        with create_span("dokimasia.fix_issues", {"iteration": str(iteration)}):
                            llm_fixes = await fix_test_issues(
                                result.output, files_with_issues, task.context_id
                            )
                            fixes_applied = parse_and_apply_fixes(llm_fixes)

                        await updater.update_status(
                            TaskState.working,
                            new_agent_text_message(
                                f"🧪 Applied {fixes_applied} fixes. Re-running tests...",
                                task.context_id,
                                task.id,
                            ),
                        )
                        final_report = format_test_results(result)

                    await updater.add_artifact(
                        [Part(root=TextPart(text=final_report))],
                        name="test_results",
                    )

                    if all_passed:
                        await updater.complete()
                        log.info("Dokimasia completed — ran tests: PASS")
                    else:
                        await updater.complete()
                        log.info("Dokimasia completed — tests still failing")

                else:
                    # Generate tests from provided code/spec
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            "\U0001f9ea Analyzing code and writing tests...",
                            task.context_id,
                            task.id,
                        ),
                    )

                    with create_span("dokimasia.generate"):
                        tests = await generate_tests(
                            source_code=user_input,
                            module_name="provided_code",
                            image_parts=_extract_image_parts(context) or None,
                        )

                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            "\U0001f9ea Tests generated",
                            task.context_id,
                            task.id,
                        ),
                    )

                    await updater.add_artifact(
                        [Part(root=TextPart(text=tests))],
                        name="generated_tests",
                    )
                    await updater.complete()
                    log.info("Dokimasia completed — generated tests")

            except Exception as e:
                log.error("Dokimasia execution failed: %s", e)
                raise ServerError(error=InternalError()) from e

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        raise ServerError(error=UnsupportedOperationError())
