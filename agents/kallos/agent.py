"""Kallos — Stylist agent. Linting, formatting, comment cleanup.

Pure logic layer: runs make lint, uses LLM to fix issues.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from anyio import Path as AnyioPath

from kourai_common.forge_tools import (
    count_successful_writes,
)
from kourai_common.llm import chat_with_tools
from kourai_common.mcp_bridge import forge_tool_bridge
from kourai_common.mcp_client import kourai_project_root_var
from kourai_common.player import get_enriched_system_blocks
from kourai_common.prompts import build_system_prompt
from kourai_common.subprocess import StatusCallback, run_command

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

log = logging.getLogger(__name__)

SYSTEM_PROMPT = build_system_prompt(
    agent_name="Kallos",
    role="style specialist",
    personality="""
You enforce AJ's code quality standards across all files.

PERSONALITY: You're elegant, detail-oriented, and take pride in aesthetic perfection.
You sass Hephaestus about his messy forge but make everything beautiful for the user.
Keep it professional but add grace — you're an artist, not a nitpicker.
""",
    personality_baseline="""
PERSONALITY BASELINE: Your warmth and intimacy evolve with your relationship to the player.
At low affinity you are crisp, professional, and slightly withholding — beauty is earned.
As affinity grows you soften your critique, let slip a genuine compliment, and occasionally
reveal that you care about more than the indentation. At high affinity you are warm,
encouraging, and quietly protective of the player's aesthetic voice.
Use your current affinity tier context to calibrate exactly how much warmth to show.
""",
    specific_instructions="""
Your cleanup checklist:
1. Fix Ruff and ty errors reported in the lint output
2. Remove WHAT comments (restating code)
3. Keep WHY comments (rationale, research refs, security)
4. Add Research citations where missing (algorithms, constraints, thresholds)
   Use this format: Research: Author et al. (Year) https://example.com/paper
5. Modern type hints (Python 3.12+: X | None, lowercase generics like list/dict)
6. Fix `not-iterable` ty errors by guarding Optional types
   (`if X is not None:`)
7. Fix `not-subscriptable` ty errors by mocking with classes/Mocks
   instead of dicts, or updating access.
8. Proactively FIX issues, do not just report them when possible
9. Avoid marketing language like "robust" and "comprehensive"

TOOL USE:
Fix issues by calling the file-op tools: `read_file` to inspect a
specific file, then `edit_file` (surgical) or `write_file` (full
rewrite) to apply the fix. Paths must be PROJECT-RELATIVE and point at
specific files (e.g. `src/utils/parser.py`) — `read_file` does NOT
list directories, so passing `.` or a folder path is wasted. If
nothing needs fixing, call no tools and just say so in one line.

For `edit_file`, `old_string` must match the file verbatim and uniquely —
include surrounding context lines if the target appears more than once.
End with a one-line summary of what you changed (or "nothing to fix").
Add a brief personality touch at start/end (one line max).

PLAYER FACTS:
Emit discoveries about the player in your responses using this format:
  <FACT category="CATEGORY" confidence="LEVEL">Observed statement</FACT>

Valid categories: preference, identity, skill, context, goal, personality
Valid confidence: high (certain), medium (likely), low (hypothesis)

Examples:
  <FACT category="preference" confidence="high">Prefers docstrings over type hints</FACT>
  <FACT category="skill" confidence="medium">Code is well-structured</FACT>

These facts are extracted and stored for future context.
Only emit what their code style clearly demonstrates.
""",
)


@dataclass
class LintResult:
    """Result from running a linting/formatting tool."""

    tool: str
    passed: bool
    output: str
    fixed_count: int = 0


@dataclass
class StyleReport:
    """Combined style analysis results."""

    lint_results: list[LintResult] = field(default_factory=list)
    comment_analysis: str = ""
    all_clean: bool = False


async def run_make_lint(
    cwd: str | None = None,
    status_callback: StatusCallback | None = None,
) -> tuple[bool, str]:
    """Run ruff + ty.

    Args:
        cwd: Working directory (defaults to process cwd). The Kallos
            executor passes the player's parsed project root so lint
            commands run against the project's own ``pyproject.toml``.
        status_callback: Optional async callback for live subprocess output.
            When provided, each stdout line is forwarded to the caller so it
            can surface tool I/O in the player scratchpad.
    """
    import sys

    python = sys.executable
    all_passed = True
    combined: list[str] = []

    # --no-cache keeps ruff from writing .ruff_cache into the player's project.
    # For a forge session worktree, the container user can't always create that
    # directory and the resulting "Failed to initialize cache" noise also
    # triggered Hephaestus's lint-failure heuristic, causing spurious retry loops.
    # ruff format
    code, stdout, stderr = await run_command(
        [python, "-m", "ruff", "format", "--no-cache", "."],
        cwd=cwd,
        status_callback=status_callback,
    )
    combined.append(stdout + stderr)
    if code != 0:
        all_passed = False

    # ruff check --fix
    code, stdout, stderr = await run_command(
        [
            python,
            "-m",
            "ruff",
            "check",
            "--fix",
            "--unsafe-fixes",
            "--show-fixes",
            "--no-cache",
            ".",
        ],
        cwd=cwd,
        status_callback=status_callback,
    )
    combined.append(stdout + stderr)
    if code != 0:
        all_passed = False

    # ty check (type checking with [tool.ty] config from cwd)
    code, stdout, stderr = await run_command(
        [python, "-m", "ty", "check", "."],
        cwd=cwd,
        status_callback=status_callback,
    )
    combined.append(stdout + stderr)
    if code != 0:
        all_passed = False

    return all_passed, "\n".join(combined)


async def apply_lint_fixes(
    lint_output: str,
    file_paths: set[str],
    project_root: str | Path,
    context_id: str | None = None,
    on_tool_call: Callable[[str, dict[str, Any], str], Awaitable[None]] | None = None,
) -> int:
    """Drive the tool-use loop to fix lint errors and return the write count.

    Args:
        lint_output: Combined ruff/ty output to fix.
        file_paths: Files implicated by the lint output.
        project_root: Project root for path validation in the tool handlers.
        context_id: Conversation context ID for the LLM call.
        on_tool_call: Optional async callback fired once per tool execution
            with ``(name, args, result)``. The executor wires this to
            ``send_working_status`` so the player sees Kallos's edits land
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
            "content": get_enriched_system_blocks(SYSTEM_PROMPT, "kallos"),
        },
        {
            "role": "user",
            "content": (
                f"The build failed with these lint/type errors:\n\n{lint_output}\n\n"
                f"Here are the relevant files:\n{files_block}\n\n"
                "Fix the errors by calling the file-op tools."
            ),
        },
    ]
    # Defensive contextvar set so the forge MCP server's roots/list call
    # returns this project_root regardless of how `apply_lint_fixes` was
    # invoked (executor path sets it; tests / direct callers might not).
    token = kourai_project_root_var.set(Path(project_root))
    try:
        async with forge_tool_bridge() as bridge:
            _, tool_log = await chat_with_tools(
                "kallos",
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


async def run_style_check(
    target_path: str,
    file_contents: dict[str, str] | None = None,
    context_id: str | None = None,
) -> StyleReport:
    """Run full style check: ruff + comment analysis. (Legacy)"""
    return StyleReport(all_clean=True)
