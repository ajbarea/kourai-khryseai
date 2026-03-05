"""A2A bridge for Dokimasia — translates between A2A protocol and tester logic."""

from __future__ import annotations

import logging

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.dokimasia.agent import generate_tests
from kourai_common.a2a_utils import extract_image_parts
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.messaging import send_working_status
from kourai_common.tracing import create_span

log = logging.getLogger(__name__)


class DokimasiaAgentExecutor(BaseAgentExecutor):
    """A2A executor for the Dokimasia tester agent."""

    def get_input_required_message(self) -> str:
        return (
            "I need source code or a module name to write tests for, "
            "or a test path to run. What should I test?"
        )

    @executor_error_handler(agent_name="dokimasia")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        """Dokimasia-specific: run tests or generate new tests."""
        with create_span("dokimasia.execute", {"a2a.method": "execute"}):
            user_input = context.get_user_input()

            input_lower = user_input.lower()
            is_run_request = any(
                kw in input_lower for kw in ["run test", "make test", "pytest", "run all"]
            )

            if is_run_request:
                from agents.dokimasia.agent import (
                    fix_test_issues,
                    run_pytest,
                )
                from kourai_common.fix_loop import run_fix_loop
                from kourai_common.subprocess import (
                    extract_files_from_output,
                    parse_and_apply_fixes,
                )

                # Wrapper to adapt run_pytest to fix_loop interface
                async def _run_pytest_wrapper():
                    result = await run_pytest()
                    return result.success, result.output

                # Run iterative test-fix loop
                all_passed, test_output = await run_fix_loop(
                    tool_name="pytest",
                    run_tool=_run_pytest_wrapper,
                    extract_files=extract_files_from_output,
                    fix_issues=fix_test_issues,
                    apply_fixes=parse_and_apply_fixes,
                    updater=updater,
                    task=task,
                    emoji="🧪",
                )

                # Format final report - need to parse output into result-like object
                # For simplicity, just use the raw output
                final_report = test_output

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
                await send_working_status(
                    updater,
                    task,
                    "Analyzing code and writing tests...",
                    emoji="🧪",
                )

                with create_span("dokimasia.generate"):
                    tests = await generate_tests(
                        source_code=user_input,
                        module_name="provided_code",
                        image_parts=extract_image_parts(context) or None,
                    )

                await send_working_status(
                    updater,
                    task,
                    "Tests generated",
                    emoji="🧪",
                )

                await updater.add_artifact(
                    [Part(root=TextPart(text=tests))],
                    name="generated_tests",
                )
                await updater.complete()
                log.info("Dokimasia completed — generated tests")

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
