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

from kourai_common.tracing import create_span

from agents.dokimasia.agent import (
    format_test_results,
    generate_tests,
    run_pytest,
)

log = logging.getLogger(__name__)


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

            if not task:
                task = new_task(context.message)
                await event_queue.enqueue_event(task)

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
                    # Run existing tests
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            "\U0001f9ea Running pytest...",
                            task.context_id,
                            task.id,
                        ),
                    )

                    with create_span("dokimasia.pytest"):
                        result = await run_pytest()

                    report = format_test_results(result)
                    await updater.add_artifact(
                        [Part(root=TextPart(text=report))],
                        name="test_results",
                    )
                    await updater.complete()
                    log.info("Dokimasia completed — ran tests: %s", "PASS" if result.success else "FAIL")

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
