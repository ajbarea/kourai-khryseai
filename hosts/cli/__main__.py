"""Kourai Khryseai CLI — interactive client for the agent swarm.

Connects to Hephaestus (orchestrator) and streams pipeline progress
with agent-prefixed emoji status messages.

Usage: python -m hosts.cli [--agent URL] [--verbose]
"""

from __future__ import annotations

import asyncio
import sys
import time
from uuid import uuid4

import asyncclick as click
import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    JSONRPCErrorResponse,
    Message,
    MessageSendConfiguration,
    MessageSendParams,
    Part,
    Role,
    SendStreamingMessageRequest,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
)

from kourai_common.config import get_agent_url

# Agent emoji map (mirrors Hephaestus executor)
AGENT_EMOJI = {
    "hephaestus": "\U0001f525",
    "metis": "\U0001f4d0",
    "techne": "\u2699\ufe0f",
    "dokimasia": "\U0001f9ea",
    "kallos": "\u2728",
    "mneme": "\U0001f4dc",
}

# ANSI color helpers
_GOLD = "\033[1;33m"
_CYAN = "\033[1;36m"
_GREEN = "\033[1;32m"
_RED = "\033[0;31m"
_DIM = "\033[2m"
_RESET = "\033[0m"

BANNER = f"""\
{_GOLD}╔══════════════════════════════════════════╗
║     Kourai Khryseai — Golden Maidens     ║
╚══════════════════════════════════════════╝{_RESET}
Type your request. Commands: :q (quit), :status (agent info)
"""


def _extract_status_text(event: TaskStatusUpdateEvent) -> str:
    """Pull display text from a status update event."""
    if event.status.message and hasattr(event.status.message, "parts"):
        parts = []
        for p in event.status.message.parts:
            if hasattr(p.root, "text"):
                parts.append(p.root.text)
        if parts:
            return "\n".join(parts)
    return ""


def _extract_artifact_text(event: TaskArtifactUpdateEvent) -> str:
    """Pull display text from an artifact update event."""
    parts = []
    if event.artifact and event.artifact.parts:
        for p in event.artifact.parts:
            if hasattr(p.root, "text"):
                parts.append(p.root.text)
    return "\n".join(parts)


async def send_and_stream(
    client: A2AClient,
    user_text: str,
    context_id: str,
    task_id: str | None = None,
    verbose: bool = False,
) -> tuple[bool, str, str | None]:
    """Send a message and stream the response.

    Args:
        client: The A2A client connected to Hephaestus.
        user_text: User's input text.
        context_id: Conversation context ID.
        task_id: Existing task ID for follow-up messages.
        verbose: Show extra timing/debug info.

    Returns:
        (continue_loop, context_id, task_id) tuple.
    """
    t0 = time.monotonic()
    message = Message(
        role=Role.user,
        parts=[Part(root=TextPart(text=user_text))],
        message_id=str(uuid4()),
        task_id=task_id,
        context_id=context_id,
    )

    payload = MessageSendParams(
        message=message,
        configuration=MessageSendConfiguration(
            accepted_output_modes=["text"],
        ),
    )

    request = SendStreamingMessageRequest(
        id=str(uuid4()),
        params=payload,
    )

    if verbose:
        click.echo(f"{_DIM}[verbose] Sending {len(user_text)} chars, context={context_id}{_RESET}")

    final_state = None
    final_text = ""
    event_count = 0

    try:
        async for result in client.send_message_streaming(request):
            event_count += 1
            if isinstance(result.root, JSONRPCErrorResponse):
                click.echo(f"{_RED}Error: {result.root.error}{_RESET}")
                return True, context_id, task_id

            event = result.root.result
            if event.context_id:
                context_id = event.context_id

            if isinstance(event, Task):
                task_id = event.id

            elif isinstance(event, TaskStatusUpdateEvent):
                task_id = event.task_id
                final_state = event.status.state
                text = _extract_status_text(event)
                if text:
                    click.echo(text)

            elif isinstance(event, TaskArtifactUpdateEvent):
                task_id = event.task_id
                text = _extract_artifact_text(event)
                if text:
                    final_text = text

            elif isinstance(event, Message):
                for p in event.parts:
                    if hasattr(p.root, "text"):
                        click.echo(p.root.text)

    except httpx.ConnectError:
        click.echo(f"{_RED}Connection lost to Hephaestus{_RESET}")
        return True, context_id, task_id
    except httpx.TimeoutException:
        click.echo(f"{_RED}Request timed out{_RESET}")
        return True, context_id, task_id

    elapsed = time.monotonic() - t0

    # Show final artifact if we have one
    if final_text:
        click.echo(f"\n{_GREEN}{'─' * 40}{_RESET}")
        click.echo(final_text)
        click.echo(f"{_GREEN}{'─' * 40}{_RESET}")

    if verbose:
        click.echo(f"{_DIM}[verbose] {event_count} events in {elapsed:.1f}s{_RESET}")

    # Handle input_required — prompt user for follow-up
    if final_state == TaskState.input_required:
        follow_up: str = await click.prompt(f"\n{_GOLD}↳ Your response{_RESET}")
        if follow_up.strip().lower() in (":q", "quit"):
            return False, context_id, task_id
        return await send_and_stream(client, follow_up, context_id, task_id, verbose)

    return True, context_id, task_id


@click.command()
@click.option(
    "--agent",
    default=None,
    help="Hephaestus URL (default: auto from config)",
)
@click.option(
    "--timeout",
    default=600,
    help="Request timeout in seconds",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show timing and debug details",
)
async def main(agent: str | None, timeout: int, verbose: bool) -> None:
    """Interactive CLI for Kourai Khryseai agent swarm."""
    if not agent:
        agent = get_agent_url("hephaestus")

    click.echo(BANNER)
    click.echo(f"Connecting to Hephaestus at {agent}...")

    async with httpx.AsyncClient(timeout=timeout) as httpx_client:
        try:
            resolver = A2ACardResolver(httpx_client, agent)
            card = await resolver.get_agent_card()
        except httpx.ConnectError:
            click.echo(f"{_RED}Cannot reach Hephaestus at {agent}{_RESET}")
            click.echo("Start agents with: make up")
            sys.exit(1)
        except Exception as e:
            click.echo(f"{_RED}Failed to connect: {e}{_RESET}")
            sys.exit(1)

        click.echo(f"Connected to {card.name} v{card.version}")
        click.echo(f"Skills: {', '.join(s.name for s in card.skills)}")
        if verbose:
            click.echo(
                f"{_DIM}[verbose] URL={agent} streaming={card.capabilities.streaming}{_RESET}"
            )
        click.echo("")

        client = A2AClient(httpx_client, agent_card=card)
        context_id: str = uuid4().hex

        while True:
            try:
                prompt: str = await click.prompt(f"{_CYAN}kourai{_RESET}")
            except (EOFError, KeyboardInterrupt):
                click.echo("\nGoodbye!")
                break

            if prompt.strip().lower() in (":q", "quit", "exit"):
                click.echo("Goodbye!")
                break

            if prompt.strip() == ":status":
                click.echo(f"Agent: {card.name} v{card.version}")
                click.echo(f"URL: {agent}")
                click.echo(f"Context: {context_id}")
                click.echo(f"Streaming: {card.capabilities.streaming}")
                continue

            if not prompt.strip():
                continue

            click.echo("")
            keep_going, context_id, _ = await send_and_stream(
                client,
                prompt,
                context_id,
                verbose=verbose,
            )
            click.echo("")

            if not keep_going:
                click.echo("Goodbye!")
                break


if __name__ == "__main__":
    asyncio.run(main())
