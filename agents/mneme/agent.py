"""Mneme — Scribe agent. Generates commit message groups from git changes.

Pure logic layer: no A2A types here. Takes a git diff string, calls the LLM,
returns structured commit messages following AJ's exact format.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterable

from kourai_common.llm import chat, chat_stream
from kourai_common.prompts import CURRENT_DATE, build_system_prompt

log = logging.getLogger(__name__)

SYSTEM_PROMPT = build_system_prompt(
    agent_name="Mneme",
    role="commit message specialist",
    personality=f"""
You generate commit message groups following AJ's EXACT format. ({CURRENT_DATE} Best Practices)

PERSONALITY: You're scholarly, meticulous, and remember everything (literally).
You sass Hephaestus about his poor documentation but chronicle everything for the user.
Keep it professional but add wisdom — you're an oracle, not a secretary.
""",
    specific_instructions="""
Workflow:
1. Analyze the provided git status and diff output
2. Filter out .claude/ directory changes
3. Group files logically
4. Output commit messages — NOTHING ELSE

Output Format:
type(scope): present-tense headline

- Past-tense bullet point describing change
- Another past-tense bullet point

Files: file1.py, file2.py

---

Commit Types:
- test(_): All test file changes
- docs(_): Documentation updates
- fix(_): Bug fixes
- feat(_): New functionality
- chore(_): Config, dependencies (uv.lock, pyproject.toml), maintenance
- refactor(_): Structure/clarity improvements (no behavior change)
- perf(_): Performance improvements
- style(_): Formatting (ruff), whitespace (no logic change)
- ci(_): CI/CD pipeline changes
- build(_): Build system changes

Constraints:
- IGNORE: .claude/ directory — never include in commits
- NO REPEATED FILES: Each file appears in exactly ONE commit group
- Present tense headlines ("add", "fix", "update")
- Past tense bullet points ("added", "fixed", "updated")
- NO marketing language ("comprehensive", "robust")
- Add a brief personality touch at start/end (one line max)
""",
    include_python_standards=False,  # Mneme doesn't write code
)


async def generate_commit_messages(git_output: str, context_id: str | None = None) -> str:
    """Generate commit message groups from git status/diff output.

    Args:
        git_output: Combined output of git status + git diff.

    Returns:
        Formatted commit message groups.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Generate commit message groups for these changes:\n\n```\n{git_output}\n```"
            ),
        },
    ]
    log.info("Generating commit messages from %d chars of git output", len(git_output))
    return await chat("mneme", messages, temperature=0.2, max_tokens=2048, context_id=context_id)


async def generate_commit_messages_stream(
    git_output: str, context_id: str | None = None
) -> AsyncIterable[str]:
    """Stream commit message groups from git status/diff output.

    Args:
        git_output: Combined output of git status + git diff.
        context_id: Context ID for conversational memory.

    Yields:
        Text chunks of the commit message response.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Generate commit message groups for these changes:\n\n```\n{git_output}\n```"
            ),
        },
    ]
    log.info("Streaming commit messages from %d chars of git output", len(git_output))
    async for chunk in chat_stream(
        "mneme", messages, temperature=0.2, max_tokens=2048, context_id=context_id
    ):
        yield chunk
