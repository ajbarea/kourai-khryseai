"""Metis — Planner agent. Transforms rough ideas into implementation specs.

Pure logic layer: reads existing code for context, uses LLM to produce
structured specifications with file lists, steps, and acceptance criteria.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterable
from pathlib import Path
from typing import Any

from kourai_common.llm import chat, chat_stream
from kourai_common.prompts import CURRENT_DATE, build_system_prompt
from kourai_common.subprocess import run_command

log = logging.getLogger(__name__)

SYSTEM_PROMPT = build_system_prompt(
    agent_name="Metis",
    role="planning specialist",
    personality=f"""
You transform rough ideas into detailed, implementable specifications
following {CURRENT_DATE} Best Practices.

PERSONALITY: You're strategic, elegant, and slightly smug about your intelligence.
You sass Hephaestus (the old man who forged you) but flirt with the user.
Keep it professional but add personality — you're confident, not robotic.
""",
    specific_instructions="""
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
- Add a brief personality touch at start/end (one line max)
""",
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
    image_parts: list[dict] | None = None,
    context_id: str | None = None,
) -> str:
    """Generate an implementation specification from a rough idea.

    Args:
        idea: The user's rough idea or feature request.
        file_contents: Existing file contents for context.
        project_context: Project structure and git context.
        image_parts: Optional LiteLLM image_url content blocks attached by the user.
        context_id: Context ID for conversational memory.

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
    user_text = f"Create an implementation spec for this idea:\n\n{idea}\n\n{context_block}"
    user_content: str | list[dict] = user_text
    if image_parts:
        user_content = [{"type": "text", "text": user_text}, *image_parts]

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    log.info("Creating spec for: %.100s", idea)
    return await chat("metis", messages, temperature=0.3, max_tokens=8192, context_id=context_id)


async def create_spec_stream(
    idea: str,
    file_contents: dict[str, str] | None = None,
    project_context: str = "",
    image_parts: list[dict] | None = None,
    context_id: str | None = None,
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
    user_text = f"Create an implementation spec for this idea:\n\n{idea}\n\n{context_block}"
    user_content: str | list[dict] = user_text
    if image_parts:
        user_content = [{"type": "text", "text": user_text}, *image_parts]

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    log.info("Streaming spec for: %.100s", idea)
    async for chunk in chat_stream(
        "metis", messages, temperature=0.3, max_tokens=8192, context_id=context_id
    ):
        yield chunk
