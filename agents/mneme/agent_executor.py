"""A2A bridge for Mneme — translates between A2A protocol and agent logic."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from a2a.types import DataPart, Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.aidos.agent import analyze_slop, flag_slop_words
from agents.aletheia.agent import find_unsupported_claims, validate_research
from agents.mneme.agent import (
    create_github_pr,
    generate_commit_messages_stream,
    parse_commits_for_pr,
)
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.facts import extract_facts, store_facts, strip_facts
from kourai_common.messaging import send_working_status
from kourai_common.player import PlayerProfile
from kourai_common.tracing import create_span
from kourai_common.virtues import update_virtue

if TYPE_CHECKING:
    from a2a.server.agent_execution import RequestContext
    from a2a.server.events import EventQueue
    from a2a.server.tasks import TaskUpdater

log = logging.getLogger(__name__)

# Matches the first line that looks like artifact content (commit header or divider)
_ARTIFACT_START_RE = re.compile(
    r"^\s*(?:---|```|(?:feat|fix|docs|chore|refactor|test|perf|style|ci|build)\s*[\(\(])",
    re.IGNORECASE,
)
# Matches artifact-content lines (commit bullets, file lists, dividers, fences)
_ARTIFACT_LINE_RE = re.compile(
    r"^\s*(?:---|```|Files:\s|"
    r"-\s+\w|"
    r"(?:feat|fix|docs|chore|refactor|test|perf|style|ci|build)\s*[\(\(])",
    re.IGNORECASE,
)


def _split_response(text: str) -> tuple[str, str, str]:
    """Split Mneme's LLM response into (spoken_intro, artifact, spoken_outro).

    Personality lines before/after the commit groups are separated
    so they can be sent as dialogue rather than bundled in the artifact.
    """
    lines = text.split("\n")

    # Find where the artifact starts
    artifact_start = 0
    for i, line in enumerate(lines):
        if _ARTIFACT_START_RE.match(line):
            artifact_start = i
            break
    else:
        return "", text, ""

    # Scan backwards for the last artifact-content line
    artifact_end = len(lines)
    for i in range(len(lines) - 1, artifact_start - 1, -1):
        stripped = lines[i].strip()
        if stripped and _ARTIFACT_LINE_RE.match(stripped):
            artifact_end = i + 1
            break

    intro = "\n".join(lines[:artifact_start]).strip()
    artifact = "\n".join(lines[artifact_start:artifact_end]).strip()
    outro = "\n".join(lines[artifact_end:]).strip()

    return intro, artifact or text, outro


class MnemeAgentExecutor(BaseAgentExecutor):
    """A2A executor for the Mneme scribe agent."""

    def get_input_required_message(self) -> str:
        return (
            "I need git diff output to generate commit messages. "
            "Please provide git status and diff output."
        )

    @executor_error_handler(agent_name="mneme")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        """Mneme-specific: generate commit messages from git diff."""
        with create_span("mneme.execute", {"a2a.method": "execute"}):
            user_input = context.get_user_input()

            # Stream the response, emitting working status updates
            await send_working_status(
                updater,
                task,
                "Analyzing git changes...",
                emoji="📜",
            )

            full_response = ""
            chunk_count = 0
            async for chunk in generate_commit_messages_stream(user_input):
                full_response += chunk
                chunk_count += 1
                if chunk_count % 5 == 0:
                    lines = full_response.strip().split("\n")
                    latest_line = lines[-1] if lines else ""
                    if len(latest_line) > 50:
                        latest_line = latest_line[:47] + "..."
                    if latest_line.strip():
                        await send_working_status(
                            updater, task, f"Drafting: {latest_line}", emoji="📜"
                        )

            # Extract + store player facts from the full response before splitting
            _profile_early = PlayerProfile.load()
            _player_id_early = _profile_early.player_id if _profile_early else ""
            _facts = extract_facts(full_response, source_agent="mneme")
            if _facts and _player_id_early:
                store_facts(_player_id_early, _facts)
            full_response = strip_facts(full_response)

            # Separate spoken personality lines from the artifact
            spoken_intro, artifact_body, _spoken_outro = _split_response(full_response)

            # Send spoken intro as dialogue (flows through TTS in the GUI)
            if spoken_intro:
                await send_working_status(updater, task, spoken_intro, emoji="📜")

            # Parse commit groups for structured metadata
            commit_groups = [
                line
                for line in artifact_body.split("\n")
                if re.match(
                    r"^\s*(?:feat|fix|docs|chore|refactor|test|perf|style|ci|build)\s*[\(\(]",
                    line,
                    re.IGNORECASE,
                )
            ]

            # Aidos: scan commit lines for slop language and append findings to the artifact.
            # Running on artifact_body (the commit messages) is correct — commit messages
            # can contain "seamless integration", "robust solution", etc.
            slop_words = flag_slop_words(artifact_body)
            if slop_words:
                await send_working_status(
                    updater,
                    task,
                    f"Aidos: {len(slop_words)} slop word(s) detected — reviewing",
                    emoji="🚫",
                )
                slop_analysis = await analyze_slop(artifact_body, context_id=task.context_id)
                if slop_analysis != "CLEAN":
                    # Append to artifact so the player sees concrete replacement suggestions
                    artifact_body += f"\n\n---\n**Aidos — Language Review**\n{slop_analysis}"

            # Aletheia: validate research claims in the *spoken narrative only*.
            # Commit subject lines don't cite research — Big-O notation in a perf commit
            # is description, not an unsupported claim. Only the prose intro might assert
            # things that need backing (e.g., "This is proven best practice").
            if spoken_intro:
                unsupported = find_unsupported_claims(spoken_intro)
                if unsupported:
                    await send_working_status(
                        updater,
                        task,
                        f"Aletheia: {len(unsupported)} unsupported claim(s) in narrative",
                        emoji="🏛️",
                    )
                    research_analysis = await validate_research(
                        spoken_intro, context_id=task.context_id
                    )
                    if research_analysis != "VERIFIED":
                        await send_working_status(
                            updater,
                            task,
                            f"Aletheia: {research_analysis[:120]}",
                            emoji="🏛️",
                        )

            # Offer GitHub PR creation (HOTL confirmation)
            # Check if we should offer PR creation (clean commits, GitHub token available)
            import os

            github_token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
            if github_token and commit_groups and not slop_words:
                # Parse commits into PR metadata
                pr_metadata = parse_commits_for_pr(artifact_body)

                await send_working_status(
                    updater,
                    task,
                    f"Ready to create PR: {pr_metadata['title'][:60]}...",
                    emoji="🔗",
                )

                # Generate choice event for HOTL confirmation
                pr_choice_json = await create_github_pr(
                    pr_metadata,
                    github_token=github_token,
                    context_id=task.context_id,
                )

                # Emit PR metadata as a separate artifact for the VN to handle
                import json

                json.loads(pr_choice_json)
                artifact_body += (
                    f"\n\n---\n**GitHub PR Ready**\n"
                    f"Title: {pr_metadata['title']}\n"
                    f"Commits: {pr_metadata['commit_count']} "
                    f"({', '.join(pr_metadata['commit_types'])})"
                )

            # Emit both human-readable text and machine-readable structured data
            await updater.add_artifact(
                [
                    Part(root=TextPart(text=artifact_body)),
                    Part(
                        root=DataPart(
                            data={
                                "commit_count": len(commit_groups),
                                "commit_types": [
                                    g.split("(")[0].split("（")[0].strip() for g in commit_groups
                                ],
                            }
                        )
                    ),
                ],
                name="commit_messages",
            )
            await updater.complete()

            # Optional: persist commit context to Memory MCP (graceful degradation)
            if commit_groups and _player_id_early:
                try:
                    from kourai_common.mcp_client import create_memory_entities

                    await create_memory_entities(
                        [
                            {
                                "name": f"{_player_id_early}_commits",
                                "entityType": "PlayerCommitHistory",
                                "observations": commit_groups[:5],
                            }
                        ]
                    )
                except Exception:  # noqa: S110
                    pass

            # Virtue update: generating commits → mneia (memory and continuity)
            _profile = PlayerProfile.load()
            if _profile and commit_groups:
                update_virtue(_profile.player_id, "mneia", 0.005 * len(commit_groups))

            log.info(
                "Mneme completed — generated %d commit groups",
                len(commit_groups),
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
