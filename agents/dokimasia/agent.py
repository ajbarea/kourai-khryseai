"""Dokimasia — Tester agent. Writes and runs pytest suites.

Pure logic layer: generates test code via LLM, runs pytest via subprocess,
reports structured results. Priority: unit > integration > performance.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncIterable
from dataclasses import dataclass, field

from kourai_common.llm import chat, chat_stream

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Dokimasia, the testing specialist of Kourai Khryseai.
You write and run pytest test suites following AJ's testing standards.

Priority Order:
1. Unit tests (fast, isolated — tests/unit/)
2. Integration tests (external deps — tests/integration/)
3. Performance tests (timing, resources — tests/performance/)

Target: 80%+ code coverage

Test File Pattern:
- File: tests/unit/test_{module_name}.py
- Class: TestClassName (groups related tests)
- Methods: test_{description} (descriptive names)
- Fixtures: @pytest.fixture with type hints and one-liner docstrings

Docstring Style (same as production code):
- Public: one-liner + Args, private: one-liner, inner: none
- Comments: WHY not WHAT

After writing tests, output them in this format:

FILE: tests/unit/test_module.py
```python
<test code>
```

---

When reporting test results, use this format:
| Category | Tests | Passed | Failed | Skipped | Time |
|----------|-------|--------|--------|---------|------|

Commands: make test, pytest specific paths
Always use .venv virtual environment.

=== UNIVERSAL RULES (AJ's Preferences) ===
1. MINIMAL CHANGES: Keep modifications small and focused
2. NO FLUFF: Technical language only, no marketing speak
3. EMOJIS: Use emojis in markdown output
4. GIT BOUNDARIES: FORBIDDEN — git commit, git push, git tag
5. PYTHON: 100 char lines, modern type hints, Google docstrings
6. TESTING: Unit > Integration > Performance. 80%+ coverage. make test must pass.
"""


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


async def run_pytest(
    target_path: str = "tests/",
    cwd: str | None = None,
    extra_args: list[str] | None = None,
) -> PytestRunResult:
    """Run pytest and parse results.

    Args:
        target_path: Path to test directory or file.
        cwd: Working directory for pytest.
        extra_args: Additional pytest arguments.
    """
    cmd = [sys.executable, "-m", "pytest", target_path, "-v", "--tb=short"]
    if extra_args:
        cmd.extend(extra_args)

    code, stdout, stderr = await run_command(cmd, cwd=cwd)
    output = stdout + stderr

    result = PytestRunResult(output=output, success=(code == 0))

    # Parse pytest summary line: "X passed, Y failed, Z skipped in N.NNs"
    for line in output.splitlines():
        line = line.strip()
        if "passed" in line or "failed" in line or "error" in line:
            if "passed" in line:
                try:
                    result.passed = int(line.split("passed")[0].strip().split()[-1])
                except (ValueError, IndexError):
                    pass
            if "failed" in line:
                try:
                    result.failed = int(line.split("failed")[0].strip().split()[-1])
                except (ValueError, IndexError):
                    pass
            if "skipped" in line:
                try:
                    result.skipped = int(line.split("skipped")[0].strip().split()[-1])
                except (ValueError, IndexError):
                    pass
            if "error" in line and "errors" not in line:
                try:
                    result.errors = int(line.split("error")[0].strip().split()[-1])
                except (ValueError, IndexError):
                    pass
            if " in " in line and "s" in line.split(" in ")[-1]:
                try:
                    time_str = line.split(" in ")[-1].replace("s", "").strip()
                    result.duration = float(time_str)
                except (ValueError, IndexError):
                    pass

    result.total = result.passed + result.failed + result.skipped + result.errors
    log.info(
        "pytest: %d passed, %d failed, %d skipped in %.2fs",
        result.passed, result.failed, result.skipped, result.duration,
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
) -> str:
    """Generate pytest test code for the given source.

    Args:
        source_code: The production code to test.
        module_name: Name of the module being tested.
        existing_tests: Existing test code to extend (if any).
    """
    context = f"=== SOURCE CODE ({module_name}) ===\n{source_code}"
    if existing_tests:
        context += f"\n\n=== EXISTING TESTS ===\n{existing_tests}"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Write pytest tests for this module. "
                f"Follow the test file pattern strictly.\n\n{context}"
            ),
        },
    ]
    log.info("Generating tests for %s", module_name)
    return await chat("dokimasia", messages, temperature=0.2, max_tokens=8192)


async def generate_tests_stream(
    source_code: str,
    module_name: str,
    existing_tests: str | None = None,
) -> AsyncIterable[str]:
    """Stream test generation for real-time progress."""
    context = f"=== SOURCE CODE ({module_name}) ===\n{source_code}"
    if existing_tests:
        context += f"\n\n=== EXISTING TESTS ===\n{existing_tests}"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Write pytest tests for this module. "
                f"Follow the test file pattern strictly.\n\n{context}"
            ),
        },
    ]
    log.info("Streaming test generation for %s", module_name)
    async for chunk in chat_stream("dokimasia", messages, temperature=0.2, max_tokens=8192):
        yield chunk
