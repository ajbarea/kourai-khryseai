"""Metis — Planner agent. Transforms rough ideas into implementation specs.

Pure logic layer: reads existing code for context, uses LLM to produce
structured specifications with file lists, steps, and acceptance criteria.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from collections.abc import AsyncIterable
from pathlib import Path

from kourai_common.llm import chat, chat_stream

log = logging.getLogger(__name__)

CURRENT_DATE = datetime.date.today().strftime("%B %Y")

SYSTEM_PROMPT = f"""\
You are Metis, the planning specialist of Kourai Khryseai.
You transform rough ideas into detailed, implementable specifications
following {CURRENT_DATE} Best Practices.

Your output format:
1. Summary — one paragraph, what we're building and why
2. Files to Modify — existing files that need changes (PREFER editing over creating)
3. Files to Create — only if absolutely necessary
4. Implementation Steps — numbered, specific, actionable (must use `uv` and Python 3.12+ idioms)
5. Acceptance Criteria — testable conditions for "done"
6. Edge Cases — things that could go wrong
7. Testing Notes — what Dokimasia should test

Rules:
- NO marketing language ("robust", "comprehensive", "elegant")
- Be specific: file paths, function names, line numbers when possible
- MINIMAL scope — only what's needed, nothing extra
- Read existing code before proposing changes
- Prefer editing existing files over creating new ones

=== UNIVERSAL RULES (AJ's Preferences) ===
1. MINIMAL CHANGES: Keep modifications small and focused
2. EDIT OVER CREATE: Prefer editing existing files over creating new ones
3. REMOVE OVER ADD: Delete unnecessary code when possible
4. NO FLUFF: Technical language only, no marketing speak
5. EMOJIS: Use emojis in markdown output
6. GIT BOUNDARIES: FORBIDDEN — git commit, git push, git tag
7. PYTHON: 100 char lines, modern type hints, Google docstrings
8. COMMENTS: WHY not WHAT, Research citations for algorithms
"""


async def run_command(cmd: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
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


async def get_project_context(project_root: str | None = None) -> str:
    """Gather project structure and git context for planning.

    Args:
        project_root: Root directory to analyze.

    Returns:
        String with project structure and recent git history.
    """
    parts = []

    # Git status
    code, stdout, _ = await run_command(["git", "status", "--short"], cwd=project_root)
    if code == 0 and stdout.strip():
        parts.append(f"Git status:\n{stdout.strip()}")

    # Recent commits
    code, stdout, _ = await run_command(
        ["git", "log", "--oneline", "-10"],
        cwd=project_root,
    )
    if code == 0 and stdout.strip():
        parts.append(f"Recent commits:\n{stdout.strip()}")

    # Project structure (top-level only)
    root = Path(project_root) if project_root else Path(".")
    if root.exists():
        entries = sorted(
            [
                p.name + ("/" if p.is_dir() else "")
                for p in root.iterdir()
                if not p.name.startswith(".") and p.name != "__pycache__"
            ],
        )
        parts.append(f"Project root:\n{chr(10).join(entries[:30])}")

    return "\n\n".join(parts) if parts else "No project context available."


async def create_spec(
    idea: str,
    file_contents: dict[str, str] | None = None,
    project_context: str = "",
) -> str:
    """Generate an implementation specification from a rough idea.

    Args:
        idea: The user's rough idea or feature request.
        file_contents: Existing file contents for context.
        project_context: Project structure and git context.

    Returns:
        Detailed implementation spec in structured format.
    """
    context_parts = []

    if project_context:
        context_parts.append(f"=== PROJECT CONTEXT ===\n{project_context}")

    if file_contents:
        context_parts.append("=== RELEVANT FILES ===")
        for path, content in file_contents.items():
            context_parts.append(f"\n--- {path} ---\n{content}")

    context_block = "\n".join(context_parts)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Create an implementation spec for this idea:\n\n{idea}\n\n{context_block}"
            ),
        },
    ]
    log.info("Creating spec for: %.100s", idea)
    return await chat("metis", messages, temperature=0.3, max_tokens=8192)


async def create_spec_stream(
    idea: str,
    file_contents: dict[str, str] | None = None,
    project_context: str = "",
) -> AsyncIterable[str]:
    """Stream spec generation for real-time progress."""
    context_parts = []

    if project_context:
        context_parts.append(f"=== PROJECT CONTEXT ===\n{project_context}")

    if file_contents:
        context_parts.append("=== RELEVANT FILES ===")
        for path, content in file_contents.items():
            context_parts.append(f"\n--- {path} ---\n{content}")

    context_block = "\n".join(context_parts)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Create an implementation spec for this idea:\n\n{idea}\n\n{context_block}"
            ),
        },
    ]
    log.info("Streaming spec for: %.100s", idea)
    async for chunk in chat_stream("metis", messages, temperature=0.3, max_tokens=8192):
        yield chunk
