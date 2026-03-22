"""Generic iterative fix-check loop for agent executors.

Kallos and Dokimasia share nearly identical retry patterns:
run tool -> extract files with issues -> ask LLM to fix -> apply -> repeat.

This module provides a reusable loop abstraction that works for any tool.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from a2a.server.tasks import TaskUpdater
    from a2a.types import Task

log = logging.getLogger(__name__)


@dataclass
class StatusMessages:
    """Per-agent personality templates for fix loop status messages.

    Use {tool}, {iteration}, {max}, {count}, {fixes} as placeholders.
    """

    running: str = "Running {tool} (iteration {iteration}/{max})..."
    passed: str = "{tool} passed!"
    found_issues: str = "Found issues in {count} files. Fixing..."
    applied_fixes: str = "Applied {fixes} fixes. Re-running {tool}..."

    def format_running(self, tool: str, iteration: int, max_iter: int) -> str:
        return self.running.format(tool=tool, iteration=iteration, max=max_iter)

    def format_passed(self, tool: str) -> str:
        return self.passed.format(tool=tool)

    def format_found_issues(self, count: int) -> str:
        return self.found_issues.format(count=count)

    def format_applied_fixes(self, tool: str, fixes: int) -> str:
        return self.applied_fixes.format(tool=tool, fixes=fixes)


# Pre-built personality message sets for agents
KALLOS_MESSAGES = StatusMessages(
    running="Scanning for imperfections... (pass {iteration}/{max})",
    passed="Everything is gorgeous~ Not a blemish in sight.",
    found_issues="Hmm, {count} files need my touch...",
    applied_fixes="Applied {fixes} fixes. Let me check my work...",
)

DOKIMASIA_MESSAGES = StatusMessages(
    running="Running the gauntlet... (attempt {iteration}/{max})",
    passed="All tests survived the crucible!",
    found_issues="{count} files are failing. Patching up...",
    applied_fixes="Patched {fixes} issues. Re-testing...",
)


@dataclass
class FixLoopResult:
    """Structured result from a fix loop run for DataPart emission."""

    all_passed: bool = False
    iterations_run: int = 0
    max_iterations: int = 3
    files_with_issues: list[str] = field(default_factory=list)
    total_fixes_applied: int = 0
    final_output: str = ""

    def to_dict(self) -> dict:
        return {
            "all_passed": self.all_passed,
            "iterations_run": self.iterations_run,
            "max_iterations": self.max_iterations,
            "files_with_issues": self.files_with_issues,
            "total_fixes_applied": self.total_fixes_applied,
        }


async def run_fix_loop(
    tool_name: str,
    run_tool: Callable[[], Awaitable[tuple[bool, str]]],
    extract_files: Callable[[str], set[str]],
    fix_issues: Callable[[str, set[str], str], Awaitable[str]],
    apply_fixes: Callable[[str], int],
    updater: TaskUpdater,
    task: Task,
    emoji: str = "✨",
    max_iterations: int = 3,
    messages: StatusMessages | None = None,
) -> tuple[bool, str, FixLoopResult]:
    """Run iterative fix-check loop until passing or max iterations reached.

    Args:
        tool_name: Display name for the tool (e.g., "make lint", "pytest")
        run_tool: Async function that runs the tool and returns (success, output)
        extract_files: Function that extracts file paths from tool output
        fix_issues: Async function that generates fixes via LLM
        apply_fixes: Function that applies fixes to disk
        updater: TaskUpdater for status messages
        task: Current task being executed
        emoji: Emoji prefix for status messages
        max_iterations: Maximum retry attempts (default: 3)
        messages: Per-agent personality status messages (uses generic defaults if None)

    Returns:
        Tuple of (all_passed: bool, final_output: str, result: FixLoopResult)
    """
    from kourai_common.messaging import send_working_status

    msgs = messages or StatusMessages()
    result = FixLoopResult(max_iterations=max_iterations)
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        result.iterations_run = iteration

        await send_working_status(
            updater,
            task,
            msgs.format_running(tool_name, iteration, max_iterations),
            emoji=emoji,
        )

        success, output = await run_tool()
        result.final_output = output

        if success:
            result.all_passed = True
            await send_working_status(
                updater,
                task,
                msgs.format_passed(tool_name),
                emoji=emoji,
            )
            break

        # Extract files with issues
        files_with_issues = extract_files(output)
        result.files_with_issues = sorted(files_with_issues)
        if not files_with_issues:
            log.warning("%s failed but could not extract file paths", tool_name)
            break

        await send_working_status(
            updater,
            task,
            msgs.format_found_issues(len(files_with_issues)),
            emoji=emoji,
        )

        # Ask LLM to fix
        llm_fixes = await fix_issues(output, files_with_issues, task.context_id)
        fixes_applied = apply_fixes(llm_fixes)
        result.total_fixes_applied += fixes_applied

        await send_working_status(
            updater,
            task,
            msgs.format_applied_fixes(tool_name, fixes_applied),
            emoji=emoji,
        )

        # Break if LLM couldn't generate valid fixes
        if fixes_applied == 0:
            log.warning(
                "LLM could not generate valid fixes for %s (iteration %d/%d). "
                "Stopping to avoid infinite loop.",
                tool_name,
                iteration,
                max_iterations,
            )
            break

    return result.all_passed, result.final_output, result
