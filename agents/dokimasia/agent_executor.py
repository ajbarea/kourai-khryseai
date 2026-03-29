"""A2A bridge for Dokimasia — translates between A2A protocol and tester logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from a2a.types import DataPart, Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.dokimasia.agent import (
    generate_playwright_tests,
    generate_tests_stream,
    run_playwright,
)
from kourai_common.a2a_utils import extract_image_parts, parse_project_root
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.messaging import send_working_status
from kourai_common.player import PlayerProfile
from kourai_common.tracing import create_span
from kourai_common.virtues import update_virtue

if TYPE_CHECKING:
    from a2a.server.agent_execution import RequestContext
    from a2a.server.events import EventQueue
    from a2a.server.tasks import TaskUpdater

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
            # Resolve player's project root once; used by both test and e2e branches
            project_root = parse_project_root(user_input)

            input_lower = user_input.lower()
            is_run_request = any(
                kw in input_lower for kw in ["run test", "make test", "pytest", "run all"]
            )
            is_e2e_request = any(
                kw in input_lower
                for kw in ["e2e", "playwright", "frontend test", "browser test", "ui test"]
            )

            if is_e2e_request:
                # Playwright E2E testing
                await send_working_status(
                    updater,
                    task,
                    "Generating Playwright E2E tests...",
                    emoji="🎭",
                )

                # Generate E2E tests based on user input (feature description)
                await generate_playwright_tests(
                    page_source=user_input,
                    page_name="e2e",
                    context_id=task.context_id,
                )

                await send_working_status(
                    updater,
                    task,
                    "Running Playwright tests in headless browser...",
                    emoji="🎭",
                )

                # Run the generated tests
                test_results = await run_playwright(
                    test_path=user_input
                    if user_input.endswith((".spec.ts", ".test.ts"))
                    else "e2e.spec.ts",
                    cwd=str(project_root),
                    extra_args=["--reporter=json"],
                )

                final_output = f"🎭 Playwright E2E Test Results\n\n{test_results}"
                await updater.add_artifact(
                    [
                        Part(root=TextPart(text=final_output)),
                        Part(
                            root=DataPart(
                                data={
                                    "test_type": "e2e",
                                    "framework": "playwright",
                                    "output": test_results,
                                }
                            )
                        ),
                    ],
                    name="e2e_test_results",
                )
                await updater.complete()
                log.info("Dokimasia completed — ran Playwright E2E tests")

                # Virtue update: E2E test run → arete
                _profile = PlayerProfile.load()
                if _profile:
                    update_virtue(_profile.player_id, "arete", 0.01)

            elif is_run_request:
                from agents.dokimasia.agent import (
                    fix_test_issues,
                    run_pytest,
                )
                from kourai_common.fix_loop import DOKIMASIA_MESSAGES, run_fix_loop
                from kourai_common.subprocess import (
                    extract_files_from_output,
                    parse_and_apply_fixes,
                )

                # Callback streams each pytest output line to the player scratchpad.
                async def _pytest_status(line: str) -> None:
                    await send_working_status(updater, task, line, emoji="🧪")

                # Wrapper to adapt run_pytest to fix_loop interface
                async def _run_pytest_wrapper() -> tuple[bool, str]:
                    result = await run_pytest(cwd=str(project_root), status_callback=_pytest_status)
                    return result.success, result.output

                def _apply_fixes_with_validation(llm_output: str) -> int:
                    """Apply fixes with path safety validation."""
                    return parse_and_apply_fixes(llm_output, project_root=project_root)

                # Run iterative test-fix loop with personality messages
                all_passed, test_output, result = await run_fix_loop(
                    tool_name="pytest",
                    run_tool=_run_pytest_wrapper,
                    extract_files=extract_files_from_output,
                    fix_issues=fix_test_issues,
                    apply_fixes=_apply_fixes_with_validation,
                    updater=updater,
                    task=task,
                    emoji="🧪",
                    messages=DOKIMASIA_MESSAGES,
                )

                if all_passed:
                    final_output = "🧪 All tests survived the crucible!\n\n" + test_output
                else:
                    final_output = f"🧪 Tests completed with failures.\n\n{test_output}"

                # Emit both human-readable text and machine-readable structured data
                await updater.add_artifact(
                    [
                        Part(root=TextPart(text=final_output)),
                        Part(root=DataPart(data=result.to_dict())),
                    ],
                    name="test_results",
                )

                status = "all passed" if all_passed else "failures remain"
                await updater.complete()
                log.info("Dokimasia completed — %s", status)

                # Virtue update: clean test run → arete (excellence-seeking)
                _profile = PlayerProfile.load()
                if _profile:
                    _delta = (
                        0.01 if all_passed else 0.005
                    )  # full credit for passing, partial for trying
                    update_virtue(_profile.player_id, "arete", _delta)

            else:
                # Stream test generation with inner-thought updates
                await send_working_status(
                    updater,
                    task,
                    "Analyzing code and writing tests...",
                    emoji="🧪",
                )

                with create_span("dokimasia.generate"):
                    tests = ""
                    chunk_count = 0
                    async for chunk in generate_tests_stream(
                        source_code=user_input,
                        module_name="provided_code",
                        image_parts=extract_image_parts(context) or None,
                        context_id=task.context_id,
                    ):
                        tests += chunk
                        chunk_count += 1
                        if chunk_count % 5 == 0:
                            lines = tests.strip().split("\n")
                            latest = lines[-1] if lines else ""
                            if len(latest) > 60:
                                latest = latest[:57] + "..."
                            if latest.strip():
                                await send_working_status(
                                    updater, task, f"Writing: {latest}", emoji="🧪"
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
