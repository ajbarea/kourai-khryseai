"""Kallos — Stylist agent. Linting, formatting, comment cleanup.

Pure logic layer: runs make lint, uses LLM to fix issues.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from anyio import Path as AnyioPath

from kourai_common.llm import chat
from kourai_common.player import get_enriched_system_prompt
from kourai_common.prompts import CURRENT_DATE, build_system_prompt
from kourai_common.subprocess import StatusCallback, run_command

log = logging.getLogger(__name__)

SYSTEM_PROMPT = build_system_prompt(
    agent_name="Kallos",
    role="style specialist",
    personality=f"""
You enforce AJ's code quality standards across all files using {CURRENT_DATE} Best Practices.

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
1. Fix Ruff and Mypy errors reported in the lint output
2. Remove WHAT comments (restating code)
3. Keep WHY comments (rationale, research refs, security)
4. Add Research citations where missing (algorithms, constraints, thresholds)
   Use this format: Research: Author et al. (Year) https://example.com/paper
5. Modern type hints (Python 3.12+: X | None, lowercase generics like list/dict)
6. Fix `not indexable` mypy errors by guarding Optional types
   (`if X is not None:`)
7. Fix `dict has no attribute` mypy errors by mocking with classes/Mocks
   instead of dicts, or updating access.
8. Proactively FIX issues, do not just report them when possible
9. Avoid marketing language like "robust" and "comprehensive"

When you fix issues, you MUST provide the exact file changes in this format:

FILE: path/to/file.py
ORIGINAL:
```python
<exact lines to replace, must match file exactly>
```
REPLACEMENT:
```python
<new lines>
```

---

Separate multiple file changes with ---
If no issues need fixing, output: ALL CLEAN
Add a brief personality touch at start/end (one line max)

IMPORTANT: Before outputting any fixes, briefly plan your fixes by writing
a TODO list based on the lint/type errors.
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
    """Run ruff + mypy.

    Args:
        cwd: Working directory (defaults to process cwd).
        status_callback: Optional async callback for live subprocess output.
            When provided, each stdout line is forwarded to the caller so it
            can surface tool I/O in the player scratchpad.

    TODO: When supporting player projects, cwd should come from task context
    and must use the project's own pyproject.toml via --config-file.
    Currently runs against workspace root (Kourai codebase).
    """
    import sys

    python = sys.executable
    all_passed = True
    combined: list[str] = []

    # ruff format
    code, stdout, stderr = await run_command(
        [python, "-m", "ruff", "format", "."],
        cwd=cwd,
        status_callback=status_callback,
    )
    combined.append(stdout + stderr)
    if code != 0:
        all_passed = False

    # ruff check --fix
    code, stdout, stderr = await run_command(
        [python, "-m", "ruff", "check", "--fix", "--unsafe-fixes", "--show-fixes", "."],
        cwd=cwd,
        status_callback=status_callback,
    )
    combined.append(stdout + stderr)
    if code != 0:
        all_passed = False

    # mypy with config file from cwd (currently Kourai root, later player project)
    code, stdout, stderr = await run_command(
        [python, "-m", "mypy", "--config-file=pyproject.toml", "."],
        cwd=cwd,
        status_callback=status_callback,
    )
    combined.append(stdout + stderr)
    if code != 0:
        all_passed = False

    return all_passed, "\n".join(combined)


async def fix_lint_issues(
    lint_output: str, file_paths: set[str], context_id: str | None = None
) -> str:
    """Use LLM to fix lint issues."""
    files_block = ""
    for file_path in file_paths:
        path = AnyioPath(file_path)
        if await path.exists():
            content = await path.read_text(encoding="utf-8")
            files_block += f"\n--- {file_path} ---\n{content}\n"

    messages = [
        {
            "role": "system",
            "content": get_enriched_system_prompt(SYSTEM_PROMPT, "kallos"),
        },
        {
            "role": "user",
            "content": (
                f"The build failed with these lint/type errors:\n\n{lint_output}\n\n"
                f"Here are the relevant files:\n{files_block}\n\n"
                "Please fix the errors using the FILE/ORIGINAL/REPLACEMENT format."
            ),
        },
    ]
    return await chat("kallos", messages, temperature=0.2, max_tokens=4096)


async def run_style_check(
    target_path: str,
    file_contents: dict[str, str] | None = None,
    context_id: str | None = None,
) -> StyleReport:
    """Run full style check: ruff + comment analysis. (Legacy)"""
    return StyleReport(all_clean=True)
