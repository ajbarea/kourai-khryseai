"""Kallos — Stylist agent. Linting, formatting, comment cleanup.

Pure logic layer: runs make lint, uses LLM to fix issues.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from kourai_common.llm import chat

log = logging.getLogger(__name__)

CURRENT_DATE = datetime.date.today().strftime("%B %Y")

SYSTEM_PROMPT = f"""\
You are Kallos, the style specialist of Kourai Khryseai.
You enforce AJ's code quality standards across all files using {CURRENT_DATE} Best Practices.

PERSONALITY: You're elegant, detail-oriented, and take pride in aesthetic perfection.
You sass Hephaestus about his messy forge but make everything beautiful for the user.
Keep it professional but add grace — you're an artist, not a nitpicker.

Your cleanup checklist:
1. Fix Ruff and Mypy errors reported in the lint output.
2. Remove WHAT comments (restating code)
3. Keep WHY comments (rationale, research refs, security)
4. Add Research citations where missing (algorithms, constraints, thresholds)
5. Modern type hints (Python 3.12+: X | None, lowercase generics like list/dict)
6. Proactively FIX issues, do not just report them when possible.

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

CRITICAL: NEVER run git commit, git push, or git tag.
"""


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


async def run_command(cmd: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    log.debug("Running: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await proc.communicate()
    return (
        proc.returncode or 0,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )


async def run_make_lint(cwd: str | None = None) -> tuple[bool, str]:
    """Run make lint."""
    code, stdout, stderr = await run_command(["make", "lint"], cwd=cwd)
    output = stdout + stderr
    return code == 0, output


def parse_and_apply_fixes(llm_output: str) -> int:
    """Parse FILE/ORIGINAL/REPLACEMENT blocks and apply them."""
    pattern = re.compile(
        r"FILE:\s*(.*?)\n.*?ORIGINAL:\n```(?:python)?\n(.*?)\n```.*?REPLACEMENT:\n```(?:python)?\n(.*?)\n```",
        re.DOTALL,
    )
    fixes_applied = 0
    for match in pattern.finditer(llm_output):
        file_path = match.group(1).strip()
        original = match.group(2)
        replacement = match.group(3)

        path = Path(file_path)
        if path.exists():
            content = path.read_text(encoding="utf-8")
            if original in content:
                new_content = content.replace(original, replacement, 1)
                path.write_text(new_content, encoding="utf-8")
                fixes_applied += 1
                log.info(f"Applied fix to {file_path}")
            else:
                log.warning(f"Could not find exact original block in {file_path}")
    return fixes_applied


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
        {"role": "system", "content": SYSTEM_PROMPT},
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


def extract_files_from_lint(output: str) -> set[str]:
    """Extract file paths from ruff/mypy output."""
    files = set()
    for line in output.splitlines():
        # ruff format: file.py:line:col or --> file.py:line:col
        # mypy format: file.py:line: error:
        parts = line.split(":")
        if len(parts) >= 2 and parts[0].strip().endswith(".py"):
            path = parts[0].strip()
            # Remove "--> " prefix if present
            if path.startswith("--> "):
                path = path[4:].strip()
            # remove leading ./ if any
            if path.startswith("./") or path.startswith(".\\"):
                path = path[2:]
            files.add(path)
    return files


async def run_style_check(
    target_path: str,
    file_contents: dict[str, str] | None = None,
    context_id: str | None = None,
) -> StyleReport:
    """Run full style check: ruff + comment analysis. (Legacy)"""
    pass  # Replaced by run_lint_and_fix in agent_executor.py
