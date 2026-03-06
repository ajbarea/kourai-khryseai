"""Kallos — Stylist agent. Linting, formatting, comment cleanup.

Pure logic layer: runs make lint, uses LLM to fix issues.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from kourai_common.llm import chat
from kourai_common.player import get_enriched_system_prompt
from kourai_common.prompts import CURRENT_DATE, build_system_prompt
from kourai_common.subprocess import run_command

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
    specific_instructions="""
Your cleanup checklist:
1. Fix Ruff and Mypy errors reported in the lint output
2. Remove WHAT comments (restating code)
3. Keep WHY comments (rationale, research refs, security)
4. Add Research citations where missing (algorithms, constraints, thresholds).
   Format: Research: Author et al. (URL/Ref)
5. Modern type hints (Python 3.12+: X | None, lowercase generics like list/dict)
6. Proactively FIX issues, do not just report them when possible
7. No marketing language or "fluff" (e.g., avoid "robust", "comprehensive", "powerful")

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


def format_report(report: StyleReport) -> str:
    """Format the style report as a string for display."""
    if report.all_clean:
        return "✨ ALL CLEAN: Everything is elegant and follows the style guide. PASS."

    lines = []
    for result in report.lint_results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"{status}: {result.tool}")
        if not result.passed and result.output:
            lines.append(result.output)

    if report.comment_analysis:
        lines.append("\nComment Analysis:")
        lines.append(report.comment_analysis)

    return "\n".join(lines)


async def analyze_comments(file_contents: dict[str, str], context_id: str | None = None) -> str:
    """Analyze comments in files for WHAT vs WHY compliance."""
    if not file_contents:
        return "No files provided for comment analysis."

    files_block = ""
    for file_path, content in file_contents.items():
        files_block += f"\n--- {file_path} ---\n{content}\n"

    messages = [
        {"role": "system", "content": get_enriched_system_prompt(SYSTEM_PROMPT, "kallos")},
        {
            "role": "user",
            "content": (
                f"Analyze the comments in these files. Remove WHAT (restating code), "
                f"keep WHY (intent/research). Output 'ALL CLEAN' if perfect.\n\n"
                f"Files:\n{files_block}"
            ),
        },
    ]
    log.info("Analyzing comments for %d files", len(file_contents))
    return await chat("kallos", messages, temperature=0, max_tokens=1024, context_id=context_id)


async def run_make_lint(cwd: str | None = None) -> tuple[bool, str]:
    """Run make lint."""
    code, stdout, stderr = await run_command(["make", "lint"], cwd=cwd)
    output = stdout + stderr
    return code == 0, output


async def fix_lint_issues(
    lint_output: str, file_paths: set[str], context_id: str | None = None
) -> str:
    """Use LLM to fix lint issues."""
    files_block = ""
    for file_path in file_paths:
        path = Path(file_path)
        if path.exists():
            content = path.read_text(encoding="utf-8")
            files_block += f"\n--- {file_path} ---\n{content}\n"

    messages = [
        {"role": "system", "content": get_enriched_system_prompt(SYSTEM_PROMPT, "kallos")},
        {
            "role": "user",
            "content": (
                f"The build failed with these lint/type errors:\n\n{lint_output}\n\n"
                f"Here are the relevant files:\n{files_block}\n\n"
                "Please fix the errors using the FILE/ORIGINAL/REPLACEMENT format."
            ),
        },
    ]
    log.info("Requesting fixes for %d files", len(file_paths))
    return await chat("kallos", messages, temperature=0.2, max_tokens=4096, context_id=context_id)


async def run_style_check(
    target_path: str,
    file_contents: dict[str, str] | None = None,
    context_id: str | None = None,
) -> StyleReport:
    """Run full style check: ruff + comment analysis. (Legacy)"""
    pass  # Replaced by run_lint_and_fix in agent_executor.py
