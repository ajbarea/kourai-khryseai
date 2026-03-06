"""A2A bridge for Mneme — translates between A2A protocol and agent logic."""

from __future__ import annotations

import logging
import re

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.mneme.agent import generate_commit_messages_stream
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.messaging import send_working_status
from kourai_common.tracing import create_span

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

            # Separate spoken personality lines from the artifact
            spoken_intro, artifact_body, _spoken_outro = _split_response(full_response)

            # Send spoken intro as dialogue (flows through TTS in the GUI)
            if spoken_intro:
                await send_working_status(updater, task, spoken_intro, emoji="📜")

            # Emit the final artifact with only the commit messages
            await updater.add_artifact(
                [Part(root=TextPart(text=artifact_body))],
                name="commit_messages",
            )
            await updater.complete()
            log.info("Mneme completed — generated commit messages")

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
