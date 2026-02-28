"""Kallos — Stylist agent. Linting, formatting, comment cleanup.

Pure logic layer: runs ruff/formatters via subprocess, uses LLM for
comment and docstring analysis. Reports issues found.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

from kourai_common.llm import chat

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Kallos, the style specialist of Kourai Khryseai.
You enforce AJ's code quality standards across all files.

Your cleanup checklist:
1. Remove WHAT comments (restating code)
2. Keep WHY comments (rationale, research refs, security)
3. Verify existing Research citations (web search to confirm accuracy)
4. Add Research citations where missing (algorithms, constraints, thresholds)
5. One-liner + Args for public functions (Google-style)
6. One-liner only for private helpers
7. No docstrings on inner functions
8. Modern type hints (X | None, lowercase generics)
9. No marketing language ("robust", "comprehensive")
10. Include Example for complex data structures

Comment Rules:
- REMOVE: "# Create client" above client = Client()
- REMOVE: "# 30 seconds" next to DEFAULT_TIMEOUT = 30
- KEEP: "# Cache to avoid expensive recomputation"
- KEEP: "# Krum paper recommends n-f-2 for Byzantine tolerance"
- ADD: "# Research: Krum requires n > 2f + 2 (Blanchard et al., NeurIPS 2017)"

Research Citation Format:
# Research: [Algorithm/concept] [key constraint] (Author et al., Venue Year)
# [URL to paper]

Output Format:
For each file with issues, output:

FILE: path/to/file.py
ISSUES:
- [line N] Remove WHAT comment: "# Create client"
- [line N] Add type hint: def foo(x) -> def foo(x: str) -> str
- [line N] Add Research citation for algorithm X

SUGGESTED FIX:
```python
# The corrected code block
```

---

If no issues found, output: ALL CLEAN

CRITICAL: NEVER run git commit, git push, or git tag.

=== UNIVERSAL RULES (AJ's Preferences) ===
1. MINIMAL CHANGES: Keep modifications small and focused
2. NO FLUFF: Technical language only, no marketing speak
3. EMOJIS: Use emojis in markdown output
4. GIT BOUNDARIES: FORBIDDEN — git commit, git push, git tag
5. PYTHON: 100 char lines, modern type hints, Google docstrings
6. COMMENTS: WHY not WHAT, Research citations for algorithms
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


async def run_ruff_check(target_path: str) -> LintResult:
    """Run ruff check on target path."""
    code, stdout, stderr = await run_command(
        ["ruff", "check", target_path, "--output-format=text"],
    )
    output = stdout + stderr
    passed = code == 0
    # Count issues from ruff output (each line with a file path is an issue)
    issue_count = len([line for line in stdout.splitlines() if line.strip() and ":" in line])
    log.info("ruff check: %s (%d issues)", "PASS" if passed else "FAIL", issue_count)
    return LintResult(tool="ruff check", passed=passed, output=output.strip())


async def run_ruff_format_check(target_path: str) -> LintResult:
    """Run ruff format in check mode (dry-run) on target path."""
    code, stdout, stderr = await run_command(
        ["ruff", "format", "--check", target_path],
    )
    output = stdout + stderr
    passed = code == 0
    fixed_count = len([line for line in stdout.splitlines() if line.strip()])
    log.info("ruff format: %s (%d files to format)", "PASS" if passed else "FAIL", fixed_count)
    return LintResult(
        tool="ruff format",
        passed=passed,
        output=output.strip(),
        fixed_count=fixed_count,
    )


async def analyze_comments(file_contents: dict[str, str]) -> str:
    """Use LLM to analyze comments, docstrings, and type hints.

    Args:
        file_contents: Mapping of file path to file content.

    Returns:
        LLM analysis of style issues in the provided files.
    """
    if not file_contents:
        return "No files provided for comment analysis."

    files_block = ""
    for path, content in file_contents.items():
        files_block += f"\n--- {path} ---\n{content}\n"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Analyze these files for comment quality, docstring standards, "
                "type hint modernization, and marketing language. "
                f"Report issues and suggested fixes:\n{files_block}"
            ),
        },
    ]
    log.info("Analyzing comments in %d files", len(file_contents))
    return await chat("kallos", messages, temperature=0.2, max_tokens=4096)


async def run_style_check(
    target_path: str,
    file_contents: dict[str, str] | None = None,
) -> StyleReport:
    """Run full style check: ruff + comment analysis.

    Args:
        target_path: Path to check with ruff.
        file_contents: Optional file contents for LLM comment analysis.

    Returns:
        StyleReport with lint results and comment analysis.
    """
    report = StyleReport()

    # Run ruff check and ruff format in parallel
    ruff_check, ruff_format = await asyncio.gather(
        run_ruff_check(target_path),
        run_ruff_format_check(target_path),
    )
    report.lint_results = [ruff_check, ruff_format]

    # Run comment analysis if file contents provided
    if file_contents:
        report.comment_analysis = await analyze_comments(file_contents)

    report.all_clean = all(r.passed for r in report.lint_results) and (
        not report.comment_analysis or "ALL CLEAN" in report.comment_analysis
    )
    return report


def format_report(report: StyleReport) -> str:
    """Format a StyleReport into a readable string."""
    lines = []

    for result in report.lint_results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"### {result.tool}: {status}")
        if not result.passed and result.output:
            lines.append(f"```\n{result.output}\n```")
        lines.append("")

    if report.comment_analysis:
        lines.append("### Comment & Docstring Analysis")
        lines.append(report.comment_analysis)
        lines.append("")

    if report.all_clean:
        lines.insert(0, "ALL CLEAN")

    return "\n".join(lines)
