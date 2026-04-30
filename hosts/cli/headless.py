"""Non-interactive (headless) mode — run a single prompt and exit.

Used for scripts and piping: python -m hosts.cli -p "generate commit messages"
"""

from __future__ import annotations

import sys
import time
from uuid import uuid4

import asyncclick as click
import httpx
from a2a.client import ClientConfig
from a2a.types import (
    Message,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
)

from hosts.cli.events import _extract_artifact_text, _extract_status_text
from hosts.cli.streaming import _connect_with_url_override
from kourai_common.a2a_utils import make_a2a_http_client
from kourai_common.messaging import send_request, stream_event, user_message


# ---------------------------------------------------------------------------
async def _headless(agent_url: str, prompt: str, timeout_seconds: int, verbose: bool) -> None:
    """Run a single prompt non-interactively and exit. For scripts and piping."""
    config = ClientConfig(
        streaming=True,
        httpx_client=make_a2a_http_client(timeout=timeout_seconds),
    )

    try:
        client, _ = await _connect_with_url_override(agent_url, config)
    except httpx.ConnectError:
        click.echo(f"Error: cannot reach Hephaestus at {agent_url}", err=True)
        click.echo("Start agents with: make up", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    context_id: str = uuid4().hex
    t0 = time.monotonic()

    # Build and send message
    message = user_message(prompt, context_id=context_id)

    final_text = ""
    try:
        async for response in client.send_message(send_request(message)):
            event = stream_event(response)

            if isinstance(event, Message):
                for p in event.parts:
                    if p.HasField("text") and verbose:
                        click.echo(p.text, err=True)
                continue

            if isinstance(event, TaskStatusUpdateEvent):
                if verbose:
                    text = _extract_status_text(event)
                    if text:
                        click.echo(text, err=True)

            elif isinstance(event, TaskArtifactUpdateEvent):
                text = _extract_artifact_text(event)
                if text:
                    final_text = text

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    elapsed = time.monotonic() - t0

    # In headless mode, output the raw result to stdout (for piping)
    if final_text:
        click.echo(final_text)

    if verbose:
        click.echo(f"Completed in {elapsed:.1f}s", err=True)

    if hasattr(client, "close"):
        await client.close()  # type: ignore[attr-defined]
