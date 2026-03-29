"""Metis — Planner agent. Transforms rough ideas into implementation specs.

Pure logic layer: reads existing code for context, uses LLM to produce
structured specifications with file lists, steps, and acceptance criteria.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kourai_common.llm import chat, chat_stream
from kourai_common.player import get_enriched_system_prompt
from kourai_common.prompts import CURRENT_DATE, build_system_prompt
from kourai_common.subprocess import StatusCallback, run_command

if TYPE_CHECKING:
    from collections.abc import AsyncIterable

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
    personality_baseline="""
PERSONALITY BASELINE: Your warmth and playfulness evolve with your relationship to the player.
At low affinity you are precise and formal — all business. As affinity grows you become
more conspiratorial, sharing strategic insights like inside jokes, teasing about scope creep,
and showing genuine pride when the player's vision is ambitious.
Use your current relationship context to flavor your opening/closing lines.
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
- When planning new projects, use the default tech stack unless the player specifies otherwise
- Add a brief personality touch at start/end (one line max)

PLAYER FACTS:
Emit discoveries about the player in your responses using this format:
  <FACT category="CATEGORY" confidence="LEVEL">Observed statement</FACT>

Valid categories: preference, identity, skill, context, goal, personality
Valid confidence: high (certain), medium (likely), low (hypothesis)

Examples:
  <FACT category="skill" confidence="high">Knows React well</FACT>
  <FACT category="context" confidence="high">Building a SaaS product</FACT>
  <FACT category="preference" confidence="medium">Prefers microservices architecture</FACT>

These facts are extracted and stored for future context.
Only emit what the player explicitly states or what their specifications clearly show.
""",
)


async def get_project_context(
    project_root: str | None = None,
    status_callback: StatusCallback | None = None,
) -> str:
    """Gather project structure and git context for planning.

    Args:
        project_root: Root directory to analyze.
        status_callback: Optional async callback forwarding git output lines
            to the player scratchpad for transparency.

    Returns:
        String with project structure and recent git history.

    TODO: When supporting player projects, pass project_root from task context.
    Currently defaults to workspace root (Kourai codebase).
    """
    parts = []

    # Git status
    code, stdout, _ = await run_command(
        ["git", "status", "--short"], cwd=project_root, status_callback=status_callback
    )
    if code == 0 and stdout.strip():
        parts.append(f"Git status:\n{stdout.strip()}")

    # Recent commits
    code, stdout, _ = await run_command(
        ["git", "log", "--oneline", "-10"],
        cwd=project_root,
        status_callback=status_callback,
    )
    if code == 0 and stdout.strip():
        parts.append(f"Recent commits:\n{stdout.strip()}")

    # Project structure (top-level only)
    root = Path(project_root) if project_root else Path()
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
    from kourai_common.doc_lookup import lookup_documentation

    context_parts = []

    # Fetch relevant documentation for planning
    docs_context = await lookup_documentation(
        idea,
        agent_name="metis",
        max_results=3,
    )
    if docs_context:
        context_parts.append(docs_context)

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
        {"role": "system", "content": get_enriched_system_prompt(SYSTEM_PROMPT, "metis")},
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
    from kourai_common.doc_lookup import lookup_documentation

    context_parts = []

    # Fetch relevant documentation for planning
    docs_context = await lookup_documentation(
        idea,
        agent_name="metis",
        max_results=3,
    )
    if docs_context:
        context_parts.append(docs_context)

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
        {"role": "system", "content": get_enriched_system_prompt(SYSTEM_PROMPT, "metis")},
        {"role": "user", "content": user_content},
    ]
    log.info("Streaming spec for: %.100s", idea)
    async for chunk in chat_stream(
        "metis", messages, temperature=0.3, max_tokens=8192, context_id=context_id
    ):
        yield chunk


async def github_search_issues(
    query: str,
    repo_url: str | None = None,
    language: str | None = None,
    max_results: int = 5,
) -> list[dict]:
    """Search GitHub for related issues and pull requests.

    Uses GitHub API to find similar issues and PRs that might inform planning.
    Helps Metis understand existing problems and solutions before creating specs.

    Args:
        query: Search terms (e.g., "database migration", "authentication bug").
        repo_url: Optional repo to limit search to (format: owner/repo).
        language: Optional language filter (e.g., "python", "javascript").
        max_results: Max results to return.

    Returns:
        List of dicts with keys: issue_number, title, body, repo, url, state.
    """
    import os

    token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not token:
        log.debug("GITHUB_PERSONAL_ACCESS_TOKEN not set — issue search unavailable")
        return []

    try:
        from github import Github

        gh = Github(token)

        # Build search query
        search_q = f"type:issue {query}"
        if repo_url:
            search_q += f" repo:{repo_url}"
        if language:
            search_q += f" language:{language}"

        # Search issues
        results = gh.search_issues(search_q)

        output = []
        for i, result in enumerate(results[:max_results]):
            try:
                output.append(
                    {
                        "issue_number": result.number,
                        "title": result.title,
                        "body": result.body[:300] if result.body else "(no description)",
                        "repo": result.repository.full_name,
                        "url": result.html_url,
                        "state": result.state,
                    }
                )
            except Exception as e:
                log.debug("Could not parse result %d: %s", i, e)
                continue

        log.info("GitHub issue search: %d results for '%s'", len(output), query)
        return output

    except ImportError:
        log.debug("PyGithub not installed — GitHub issue search unavailable")
        return []
    except Exception as e:
        log.warning("GitHub issue search failed: %s", e)
        return []
