"""Kourai Khryseai CLI — interactive client for the agent swarm.

Connects to Hephaestus (orchestrator) and streams pipeline progress
with agent-prefixed emoji status messages.

Usage: python -m hosts.cli [--agent URL] [--verbose]
"""

from __future__ import annotations

import asyncio
import io
import sys
import time
from uuid import uuid4

# Windows consoles default to cp1252 — force UTF-8 so emoji and box-drawing work
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import asyncclick as click
import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.client.client import Client
from a2a.types import (
    Message,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
)

from kourai_common.config import get_agent_url

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
        parts = [p.root.text for p in event.status.message.parts if hasattr(p.root, "text")]
        if parts:
            return "\n".join(parts)
    return ""


def _extract_artifact_text(event: TaskArtifactUpdateEvent) -> str:
    """Pull display text from an artifact update event."""
    if event.artifact and event.artifact.parts:
        return "\n".join(p.root.text for p in event.artifact.parts if hasattr(p.root, "text"))
    return ""


async def send_and_stream(
    client: Client,
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

    from a2a.client.helpers import create_text_message_object

    message = create_text_message_object(content=user_text)
    message.context_id = context_id
    if task_id:
        message.task_id = task_id

    if verbose:
        click.echo(f"{_DIM}[verbose] Sending {len(user_text)} chars, context={context_id}{_RESET}")

    final_state = None
    final_text = ""
    event_count = 0

    try:
        async for event in client.send_message(message):
            event_count += 1

            if isinstance(event, Message):
                for p in event.parts:
                    if hasattr(p.root, "text"):
                        click.echo(p.root.text)
                continue

            # ClientEvent: tuple[Task, update | None]
            task, update = event

            if task.context_id:
                context_id = task.context_id
            task_id = task.id

            if isinstance(update, TaskStatusUpdateEvent):
                final_state = update.status.state
                text = _extract_status_text(update)
                if text:
                    click.echo(text)

            elif isinstance(update, TaskArtifactUpdateEvent):
                text = _extract_artifact_text(update)
                if text:
                    final_text = text

            elif update is None:
                # Final task snapshot
                final_state = task.status.state

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

    config = ClientConfig(
        streaming=True,
        httpx_client=httpx.AsyncClient(timeout=timeout),
    )

    try:
        client = await ClientFactory.connect(agent, client_config=config)
    except httpx.ConnectError:
        click.echo(f"{_RED}Cannot reach Hephaestus at {agent}{_RESET}")
        click.echo("Start agents with: make up")
        sys.exit(1)
    except Exception as e:
        click.echo(f"{_RED}Failed to connect: {e}{_RESET}")
        sys.exit(1)

    card = await client.get_card()
    click.echo(f"Connected to {card.name} v{card.version}")
    click.echo(f"Skills: {', '.join(s.name for s in card.skills)}")
    if verbose:
        click.echo(f"{_DIM}[verbose] URL={agent} streaming={card.capabilities.streaming}{_RESET}")
    click.echo("")

    context_id: str = uuid4().hex

    try:
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
    finally:
        if hasattr(client, "close"):
            await client.close()  # type: ignore[attr-defined]


if __name__ == "__main__":
    asyncio.run(main())
