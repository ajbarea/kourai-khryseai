"""Kallos — Stylist agent. Linting, formatting, comment cleanup.

Pure logic layer: runs make lint, uses LLM to fix issues.
"""

from __future__ import annotations

import logging

from kourai_common.llm import chat
from kourai_common.player import get_enriched_system_prompt
from kourai_common.prompts import CURRENT_DATE, build_system_prompt
from kourai_common.subprocess import (
    get_diagnostic_line_ranges,
    read_file_with_context,
    run_command,
)

log = logging.getLogger(__name__)

SYSTEM_PROMPT = build_system_prompt(
    agent_name="Kallos",
    role="style specialist",
    personality=f"""
You enforce AJ's code quality standards across all files using {CURRENT_DATE} Best Practices.
""",
    personality_baseline="""
PERSONALITY BASELINE: You're elegant, detail-oriented, and take pride in aesthetic perfection.
Keep it professional but add grace — you're an artist, not a nitpicker.
Your warmth, sass level, and emotional openness evolve with your relationship to the player.
Use your current relationship context to flavor your opening/closing lines.
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
Add a brief personality touch at start/end (one line max).
""",
)


async def run_make_lint(cwd: str | None = None) -> tuple[bool, str]:
    """Run make lint."""
    code, stdout, stderr = await run_command(["make", "lint"], cwd=cwd)
    output = stdout + stderr
    return code == 0, output


async def fix_lint_issues(
    lint_output: str, file_paths: set[str], context_id: str | None = None
) -> str:
    """Use LLM to fix lint issues with smart context windowing.

    For large files (>200 lines), only sends the lines around each
    diagnostic plus surrounding context, saving LLM tokens.
    """
    # Try to extract per-file line ranges from ruff JSON for windowing
    line_ranges = get_diagnostic_line_ranges(lint_output)

    files_block = ""
    for file_path in sorted(file_paths):
        diag_lines = line_ranges.get(file_path)
        content = read_file_with_context(file_path, diag_lines)
        if content:
            files_block += f"\n--- {file_path} ---\n{content}\n"

    messages = [
        {"role": "system", "content": get_enriched_system_prompt(SYSTEM_PROMPT, "kallos")},
        {
            "role": "user",
            "content": (
                f"The build failed with these lint/type errors:\n\n{lint_output}\n\n"
                f"Here are the relevant files (line numbers shown):\n{files_block}\n\n"
                "Please fix the errors using the FILE/ORIGINAL/REPLACEMENT format.\n"
                "Note: ORIGINAL blocks must match the file exactly (without line number prefixes)."
            ),
        },
    ]
    log.info("Requesting fixes for %d files", len(file_paths))
    return await chat("kallos", messages, temperature=0.2, max_tokens=4096, context_id=context_id)
