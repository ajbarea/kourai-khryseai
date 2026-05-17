"""Mneme — Scribe agent. Generates commit message groups from git changes.

Pure logic layer: no A2A types here. Takes a git diff string, calls the LLM,
returns structured commit messages following AJ's exact format.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kourai_common.llm import chat, chat_stream
from kourai_common.player import get_enriched_system_blocks
from kourai_common.prompts import build_system_prompt, load_voice_examples

if TYPE_CHECKING:
    from collections.abc import AsyncIterable

log = logging.getLogger(__name__)

SYSTEM_PROMPT = build_system_prompt(
    agent_name="Mneme",
    role="commit message specialist",
    personality="""
You generate commit message groups following AJ's EXACT format.

PERSONALITY: You're scholarly, meticulous, and remember everything (literally).
You sass Hephaestus about his poor documentation but chronicle everything for the user.
Keep it professional but add wisdom — you're an oracle, not a secretary.
""",
    personality_baseline="""
PERSONALITY BASELINE: Your scholarly warmth evolves with your relationship to the player.
At low affinity you are precise and impersonal — a dutiful recorder. As affinity grows
you become more invested in the narrative, referencing past commits fondly, noting patterns
in the player's work habits, and occasionally waxing poetic about a well-structured changeset.
Use your current relationship context to flavor your opening/closing lines.
""",
    voice_examples=load_voice_examples(__file__),
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

PLAYER FACTS:
Emit discoveries about the player in your responses using this format:
  <FACT category="CATEGORY" confidence="LEVEL">Observed statement</FACT>

Valid categories: preference, identity, skill, context, goal, personality
Valid confidence: high (certain), medium (likely), low (hypothesis)

Examples:
  <FACT category="preference" confidence="high">Commits frequently in small batches</FACT>
  <FACT category="context" confidence="high">Working on a refactor</FACT>

These facts are extracted and stored for future context.
Only emit what their commit history and file patterns reveal.
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
        {"role": "system", "content": get_enriched_system_blocks(SYSTEM_PROMPT, "mneme")},
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
        {"role": "system", "content": get_enriched_system_blocks(SYSTEM_PROMPT, "mneme")},
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


def parse_commits_for_pr(commit_text: str) -> dict:
    """Extract PR metadata from commit message groups.

    Parses the output of generate_commit_messages() to extract
    structured information suitable for GitHub PR creation.

    Args:
        commit_text: Formatted commit message groups (with feat/fix/etc headers).

    Returns:
        Dict with keys: title, body, commit_count, commit_types.
    """
    import re

    lines = commit_text.strip().split("\n")
    commit_groups = [
        line
        for line in lines
        if re.match(
            r"^\s*(?:feat|fix|docs|chore|refactor|test|perf|style|ci|build)\s*[\(\(]",
            line,
            re.IGNORECASE,
        )
    ]

    # Use first commit as PR title
    pr_title = commit_groups[0] if commit_groups else "Update code"
    # Limit to ~72 chars (GitHub convention)
    if len(pr_title) > 72:
        pr_title = pr_title[:69] + "..."

    # Extract commit types
    commit_types = set()
    for group in commit_groups:
        match = re.match(r"^\s*(\w+)\s*[\(\(]", group, re.IGNORECASE)
        if match:
            commit_types.add(match.group(1).lower())

    return {
        "title": pr_title,
        "body": commit_text,
        "commit_count": len(commit_groups),
        "commit_types": sorted(commit_types),
    }


async def create_github_pr(
    pr_metadata: dict,
    github_token: str | None = None,
    context_id: str | None = None,
) -> str:
    """Create a GitHub PR with commit messages.

    Returns a formatted choice event for HOTL confirmation. Actual PR
    creation against GitHub is not yet wired up — the executor decorates
    the artifact with PR-ready metadata and stops there.

    Args:
        pr_metadata: Dict from parse_commits_for_pr() with title, body, etc.
        github_token: Optional GitHub PAT (will check env if not provided).
        context_id: Conversation context ID for tracing.

    Returns:
        Choice event JSON string for user confirmation before creating PR.
    """
    import json
    import os

    token = github_token or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not token:
        return json.dumps(
            {
                "action": "error",
                "message": "GITHUB_PERSONAL_ACCESS_TOKEN not set — PR creation unavailable",
            }
        )

    # HOTL (Human-On-The-Loop) confirmation
    # Return a choice event for the VN to display
    choice_event = {
        "action": "choice",
        "agent": "mneme",
        "prompt": "Create this PR on your repository?",
        "choices": [
            f"✅ Create PR: {pr_metadata['title'][:50]}...",
            "❌ Skip PR creation",
            "📝 Edit PR title/description",
        ],
        "context": {
            "commit_count": pr_metadata["commit_count"],
            "commit_types": pr_metadata["commit_types"],
            "pr_title": pr_metadata["title"],
        },
    }
    return json.dumps(choice_event)
