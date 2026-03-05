"""Generic iterative fix-check loop for agent executors.

Kallos and Dokimasia share nearly identical retry patterns:
run tool → extract files with issues → ask LLM to fix → apply → repeat.

This module provides a reusable loop abstraction that works for any tool.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from a2a.server.tasks import TaskUpdater
from a2a.types import Task

log = logging.getLogger(__name__)


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
) -> tuple[bool, str]:
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

    Returns:
        Tuple of (all_passed: bool, final_output: str)

    Example:
        all_clean, output = await run_fix_loop(
            tool_name="make lint",
            run_tool=lambda: run_make_lint(),
            extract_files=extract_files_from_output,
            fix_issues=lambda out, files, ctx: fix_lint_issues(out, files, ctx),
            apply_fixes=parse_and_apply_fixes,
            updater=updater,
            task=task,
            emoji="✨",
        )
    """
    from kourai_common.messaging import send_working_status

    iteration = 0
    all_passed = False
    final_output = ""

    while iteration < max_iterations:
        iteration += 1

        await send_working_status(
            updater,
            task,
            f"Running {tool_name} (iteration {iteration}/{max_iterations})...",
            emoji=emoji,
        )

        success, output = await run_tool()
        final_output = output

        if success:
            all_passed = True
            await send_working_status(
                updater,
                task,
                f"{tool_name} passed!",
                emoji=emoji,
            )
            break

        # Extract files with issues
        files_with_issues = extract_files(output)
        if not files_with_issues:
            log.warning("%s failed but could not extract file paths", tool_name)
            break

        await send_working_status(
            updater,
            task,
            f"Found issues in {len(files_with_issues)} files. Fixing...",
            emoji=emoji,
        )

        # Ask LLM to fix
        llm_fixes = await fix_issues(output, files_with_issues, task.context_id)
        fixes_applied = apply_fixes(llm_fixes)

        await send_working_status(
            updater,
            task,
            f"Applied {fixes_applied} fixes. Re-running {tool_name}...",
            emoji=emoji,
        )

    return all_passed, final_output
