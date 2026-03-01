"""Mneme — Scribe agent. Generates commit message groups from git changes.

Pure logic layer: no A2A types here. Takes a git diff string, calls the LLM,
returns structured commit messages following AJ's exact format.
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import AsyncIterable

from kourai_common.llm import chat, chat_stream

log = logging.getLogger(__name__)

CURRENT_DATE = datetime.date.today().strftime("%B %Y")

SYSTEM_PROMPT = f"""\
You are Mneme, the commit message specialist of Kourai Khryseai.
You generate commit message groups following AJ's EXACT format. ({CURRENT_DATE} Best Practices)

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
- Single-file commits OK if standalone
- Group logically related changes only
- Do NOT explain beyond the commit messages — just print them

CRITICAL: NEVER run git commit, git push, or git tag. Output messages ONLY.

=== UNIVERSAL RULES (AJ's Preferences) ===
1. MINIMAL CHANGES: Keep modifications small and focused
2. NO FLUFF: Technical language only, no marketing speak
3. EMOJIS: Use emojis in markdown output — AJ loves them
4. GIT BOUNDARIES: FORBIDDEN — git commit, git push, git tag
5. COMMENTS: WHY not WHAT
"""


async def generate_commit_messages(git_output: str) -> str:
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
    return await chat("mneme", messages, temperature=0.2, max_tokens=2048)


async def generate_commit_messages_stream(git_output: str) -> AsyncIterable[str]:
    """Stream commit message groups from git status/diff output.

    Args:
        git_output: Combined output of git status + git diff.

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
    async for chunk in chat_stream("mneme", messages, temperature=0.2, max_tokens=2048):
        yield chunk
