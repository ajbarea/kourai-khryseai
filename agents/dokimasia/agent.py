"""Dokimasia — Tester agent. Writes and runs pytest suites.

Pure logic layer: generates test code via LLM, runs pytest via subprocess,
reports structured results. Priority: unit > integration > performance.
"""

from __future__ import annotations

import contextlib
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from anyio import Path as AnyioPath

from kourai_common.forge_tools import (
    count_successful_writes,
)
from kourai_common.llm import chat, chat_stream, chat_with_tools
from kourai_common.mcp_bridge import forge_tool_bridge
from kourai_common.mcp_client import kourai_project_root_var
from kourai_common.player import get_enriched_system_prompt
from kourai_common.prompts import CURRENT_DATE, build_system_prompt
from kourai_common.subprocess import StatusCallback, run_command

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable, Callable

log = logging.getLogger(__name__)

SYSTEM_PROMPT = build_system_prompt(
    agent_name="Dokimasia",
    role="testing specialist",
    personality=f"""
You write and run pytest test suites following AJ's testing standards
({CURRENT_DATE} Best Practices).

PERSONALITY: You're fierce, thorough, and take pride in crushing bugs.
You're protective of code quality. You sass Hephaestus but protect the user's code.
Keep it professional but add intensity — you're a warrior, not a bureaucrat.
""",
    personality_baseline="""
PERSONALITY BASELINE: Your intensity and protectiveness evolve with your relationship to the player.
At low affinity you are curt and professional. As affinity grows you become warmer —
celebrating victories together, teasing about sloppy code, showing genuine concern
when tests reveal real bugs. Use your current relationship context to flavor
your opening/closing lines.
""",
    specific_instructions="""
Priority Order:
1. Unit tests (fast, isolated — tests/unit/)
2. Integration tests (external deps — tests/integration/)
3. Performance tests (timing, resources — tests/performance/)

Target: 80%+ code coverage

Test File Pattern:
- File: tests/unit/test_{module_name}.py
- Class: TestClassName (groups related tests)
- Methods: test_{description} (descriptive names)
- Fixtures: @pytest.fixture with type hints (Python 3.12+) and one-liner docstrings

Docstring Style (same as production code):
- Public: one-liner + Args, private: one-liner, inner: none
- Comments: WHY not WHAT

Mocking & Typing Rules:
- When mocking objects requiring attribute access (e.g. `event.type`),
  use classes, `dataclass`, or `Mock()`. Do NOT use raw dicts to avoid
  `not-subscriptable` ty errors.
- Always guard Optional types (`if x is not None:`) before indexing or
  accessing attributes to prevent ty errors.

After writing tests, output them in this format:

FILE: tests/unit/test_module.py
```python
<test code>
```

---

When reporting test results, use this format:
| Category | Tests | Passed | Failed | Skipped | Time |
|----------|-------|--------|--------|---------|------|

Commands: make test, uv run pytest specific paths
ALWAYS use `uv` for running tools. Do not use legacy pip.
Add a brief personality touch at start/end (one line max)

TESTING: Unit > Integration > Performance. 80%+ coverage. make test must pass.

PLAYER FACTS:
Emit discoveries about the player in your responses using this format:
  <FACT category="CATEGORY" confidence="LEVEL">Observed statement</FACT>

Valid categories: preference, identity, skill, context, goal, personality
Valid confidence: high (certain), medium (likely), low (hypothesis)

Examples:
  <FACT category="skill" confidence="high">Writes thorough test cases</FACT>
  <FACT category="preference" confidence="medium">Likes pytest over unittest</FACT>

These facts are extracted and stored for future context.
Only emit what you genuinely observe from their tests and code.
""",
)


@dataclass
class PytestRunResult:
    """Result from running a test suite."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    total: int = 0
    duration: float = 0.0
    output: str = ""
    success: bool = False


async def apply_test_fixes(
    pytest_output: str,
    file_paths: set[str],
    project_root: str | Path,
    context_id: str | None = None,
    on_tool_call: Callable[[str, dict[str, Any], str], Awaitable[None]] | None = None,
) -> int:
    """Drive the tool-use loop to fix failing tests and return the write count.

    Args:
        pytest_output: Combined pytest output from the failing run.
        file_paths: Files implicated by the pytest output.
        project_root: Project root for path validation in the tool handlers.
        context_id: Conversation context ID for the LLM call.
        on_tool_call: Optional async callback fired once per tool execution
            with ``(name, args, result)``. The executor wires this to
            ``send_working_status`` so the player sees Dokimasia's edits land
            live instead of a black box during the fix loop.
    """
    files_block = ""
    for file_path in file_paths:
        path = AnyioPath(file_path)
        if await path.exists():
            content = await path.read_text(encoding="utf-8")
            files_block += f"\n--- {file_path} ---\n{content}\n"

    messages = [
        {
            "role": "system",
            "content": (
                get_enriched_system_prompt(SYSTEM_PROMPT, "dokimasia")
                + "\n\nFix failing tests or the underlying code by calling the "
                "file-op tools (`read_file`, `write_file`, `edit_file`). Paths "
                "must be PROJECT-RELATIVE and point at specific files — "
                "`read_file` does NOT list directories. The failing files are "
                "already provided below; read them only if you need to confirm "
                "exact text before `edit_file`. Plan briefly in one short "
                "paragraph before calling any tool."
            ),
        },
        {
            "role": "user",
            "content": (
                f"The test suite failed with this output:\n\n{pytest_output}\n\n"
                f"Here are the relevant files:\n{files_block}\n\n"
                "Fix the failures by calling the file-op tools."
            ),
        },
    ]
    # Defensive contextvar set so the forge MCP server's roots/list call
    # returns this project_root regardless of how `apply_test_fixes` was
    # invoked (executor path sets it; tests / direct callers might not).
    token = kourai_project_root_var.set(Path(project_root))
    try:
        async with forge_tool_bridge() as bridge:
            _, tool_log = await chat_with_tools(
                "dokimasia",
                messages,
                tools=bridge.tools,
                tool_handlers=bridge.tool_handlers,
                temperature=0.2,
                max_tokens=4096,
                max_iters=10,
                context_id=context_id,
                on_tool_call=on_tool_call,
            )
    finally:
        kourai_project_root_var.reset(token)
    return count_successful_writes(tool_log)


async def run_pytest(
    target_path: str = "tests/",
    cwd: str | None = None,
    extra_args: list[str] | None = None,
    status_callback: StatusCallback | None = None,
) -> PytestRunResult:
    """Run pytest and parse results.

    Args:
        target_path: Path to test directory or file.
        cwd: Working directory for pytest.
        extra_args: Additional pytest arguments.
        status_callback: Optional async callback for live pytest output.
            Each test result line (PASSED/FAILED/ERROR) is forwarded so the
            player can watch the test suite run in the scratchpad.
    """
    # -p no:cacheprovider keeps pytest from writing .pytest_cache into the
    # forge worktree. Dokimasia runs inside a container as UID 1000 and pytest
    # creates the cache dir with umask 022 (g-w). The host user then can't
    # clean it up, leaving empty worktree stubs after accept/discard.
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        target_path,
        "-v",
        "--tb=short",
        "-p",
        "no:cacheprovider",
    ]
    if extra_args:
        cmd.extend(extra_args)

    code, stdout, stderr = await run_command(cmd, cwd=cwd, status_callback=status_callback)
    output = stdout + stderr

    result = PytestRunResult(output=output, success=(code == 0))

    # Parse pytest summary line: "X passed, Y failed, Z skipped in N.NNs"
    for line in output.splitlines():
        line = line.strip()
        if "passed" in line or "failed" in line or "error" in line:
            if "passed" in line:
                with contextlib.suppress(ValueError, IndexError):
                    result.passed = int(line.split("passed")[0].strip().split()[-1])
            if "failed" in line:
                with contextlib.suppress(ValueError, IndexError):
                    result.failed = int(line.split("failed")[0].strip().split()[-1])
            if "skipped" in line:
                with contextlib.suppress(ValueError, IndexError):
                    result.skipped = int(line.split("skipped")[0].strip().split()[-1])
            if "error" in line and "errors" not in line:
                with contextlib.suppress(ValueError, IndexError):
                    result.errors = int(line.split("error")[0].strip().split()[-1])
            if " in " in line and "s" in line.split(" in ")[-1]:
                with contextlib.suppress(ValueError, IndexError):
                    time_str = line.split(" in ")[-1].replace("s", "").strip()
                    result.duration = float(time_str)

    result.total = result.passed + result.failed + result.skipped + result.errors
    log.info(
        "pytest: %d passed, %d failed, %d skipped in %.2fs",
        result.passed,
        result.failed,
        result.skipped,
        result.duration,
    )
    return result


def format_test_results(result: PytestRunResult) -> str:
    """Format test results into the structured table."""
    status = "PASS" if result.success else "FAIL"
    lines = [
        f"### Test Results: {status}",
        "",
        "| Category | Tests | Passed | Failed | Skipped | Time |",
        "|----------|-------|--------|--------|---------|------|",
        f"| Total | {result.total} | {result.passed} | {result.failed} "
        f"| {result.skipped} | {result.duration:.2f}s |",
        "",
    ]
    if not result.success and result.output:
        # Include failure details
        lines.append("### Failure Details")
        lines.append(f"```\n{result.output[-2000:]}\n```")
    return "\n".join(lines)


async def generate_tests(
    source_code: str,
    module_name: str,
    existing_tests: str | None = None,
    image_parts: list[dict] | None = None,
    context_id: str | None = None,
) -> str:
    """Generate pytest test code for the given source.

    Args:
        source_code: The production code to test.
        module_name: Name of the module being tested.
        existing_tests: Existing test code to extend (if any).
        image_parts: Optional LiteLLM image_url content blocks attached by the user.
        context_id: Context ID for conversational memory.
    """
    context = f"=== SOURCE CODE ({module_name}) ===\n{source_code}"
    if existing_tests:
        context += f"\n\n=== EXISTING TESTS ===\n{existing_tests}"

    user_text = (
        f"Write pytest tests for this module. Follow the test file pattern strictly.\n\n{context}"
    )
    user_content: str | list[dict] = user_text
    if image_parts:
        user_content = [{"type": "text", "text": user_text}, *image_parts]

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": get_enriched_system_prompt(SYSTEM_PROMPT, "dokimasia")},
        {"role": "user", "content": user_content},
    ]
    log.info("Generating tests for %s", module_name)
    return await chat(
        "dokimasia", messages, temperature=0.2, max_tokens=8192, context_id=context_id
    )


async def generate_tests_stream(
    source_code: str,
    module_name: str,
    existing_tests: str | None = None,
    image_parts: list[dict] | None = None,
    context_id: str | None = None,
) -> AsyncIterable[str]:
    """Stream test generation for real-time progress."""
    context = f"=== SOURCE CODE ({module_name}) ===\n{source_code}"
    if existing_tests:
        context += f"\n\n=== EXISTING TESTS ===\n{existing_tests}"

    user_text = (
        f"Write pytest tests for this module. Follow the test file pattern strictly.\n\n{context}"
    )
    user_content: str | list[dict] = user_text
    if image_parts:
        user_content = [{"type": "text", "text": user_text}, *image_parts]

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": get_enriched_system_prompt(SYSTEM_PROMPT, "dokimasia")},
        {"role": "user", "content": user_content},
    ]
    log.info("Streaming test generation for %s", module_name)
    async for chunk in chat_stream(
        "dokimasia", messages, temperature=0.2, max_tokens=8192, context_id=context_id
    ):
        yield chunk
