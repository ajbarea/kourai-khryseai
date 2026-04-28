"""Core A2A communication — message sending and response streaming.

Contains the main send_and_stream() function and connection helpers.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from uuid import uuid4

import asyncclick as click
import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import (
    FilePart,
    FileWithBytes,
    Message,
    Part,
    Role,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
)

from hosts.cli.events import (
    _extract_artifact_text,
    _extract_status_text,
    _maidenify_status,
    _victory_chatter,
    get_last_seen_agent,
    reset_last_seen_agent,
    set_pipeline_chatter_enabled,
)
from hosts.cli.rendering import _comms_window, _echo, _render_markdown
from hosts.cli.styling import _DIM, _GOLD, _GOLD_BRIGHT, _RED, _RESET
from kourai_common.config import get_agent_url
from kourai_common.elicitation import parse_outbound_marker
from kourai_common.federation.host_helpers import build_pipeline_turn_entry

if TYPE_CHECKING:
    from a2a.client.client import Client

    from hosts.gui.tts_engine import TTSEngine
    from kourai_common.federation.memoir import Memoir

# ---------------------------------------------------------------------------
# Last result store — for /copy / /save
# ---------------------------------------------------------------------------
_last_result: str = ""


def get_last_result() -> str:
    """Return the last artifact text from a completed pipeline run."""
    return _last_result


async def _handle_elicitation(
    elicitation_id: str,
    specialist: str,
    question: str,
) -> None:
    """Surface an MCP elicitation to the player and POST the answer back.

    Called inline from the streaming loop when an ``[ELICIT:...]``
    marker arrives in a specialist's working_status. The specialist's
    forge tool is blocked awaiting an asyncio Future; POSTing to its
    ``/internal/elicitation/{id}`` endpoint resolves that Future and
    unblocks the tool. The streaming connection stays open the whole
    time, so the eventual artifact still reaches us via Hephaestus.

    Maps player input liberally:
      - "y"/"yes"/"<enter>" → accept
      - "n"/"no" → decline
      - "/q"/"/cancel" → cancel
    """
    _echo(
        f"\n{_GOLD}✨ {specialist.title()} needs your call:{_RESET}\n"
        f"  {question}\n"
        f"{_DIM}  [y]es / [n]o / /cancel{_RESET}"
    )
    raw: str = await click.prompt(
        f"{_GOLD}↳ Your call{_RESET}",
        default="y",
        show_default=False,
    )
    answer = raw.strip().lower()
    if answer in ("/q", "/quit", "/cancel"):
        action = "cancel"
    elif answer in ("n", "no"):
        action = "decline"
    else:
        action = "accept"

    url = f"{get_agent_url(specialist)}/internal/elicitation/{elicitation_id}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json={"action": action})
        if resp.status_code == 204:
            _echo(f"{_DIM}⤷ forwarded “{action}” to {specialist}{_RESET}")
        elif resp.status_code == 404:
            # Specialist's pending Future already cleaned up — most likely
            # the elicitation timed out on the agent side. Player's reply
            # is moot but we already prompted them; tell them what happened.
            _echo(
                f"{_RED}⚠ {specialist}'s elicitation expired before "
                f"your reply landed (id {elicitation_id[:8]}…){_RESET}"
            )
        else:
            _echo(
                f"{_RED}⚠ elicitation answer rejected by {specialist} "
                f"(HTTP {resp.status_code}): {resp.text[:120]}{_RESET}"
            )
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        _echo(f"{_RED}⚠ couldn't reach {specialist} at {url}: {exc}{_RESET}")


# ---------------------------------------------------------------------------
# Core streaming logic
# ---------------------------------------------------------------------------
async def send_and_stream(
    client: Client,
    user_text: str,
    context_id: str,
    task_id: str | None = None,
    verbose: bool = False,
    attachments: list[tuple[str, str]] | None = None,
    tts: TTSEngine | None = None,
    gossip_enabled: bool = True,
    *,
    memoir: Memoir | None = None,
    scene_id: str | None = None,
    forge_tags: list[str] | None = None,
) -> tuple[bool, str, str | None]:
    """Send a message and stream the response.

    Returns:
        (continue_loop, context_id, task_id) tuple.

    ``forge_tags`` carries the bracket-tag prefixes the REPL prepended on
    the original turn (``[project_root: …]``, ``[yolo: on]``,
    ``[auto_approve_reads: on]``). The ``input_required`` follow-up loop
    re-prepends them to the player's response so multi-turn confirmation
    flows preserve forge metadata. Without this, every M13 ``yes`` would
    arrive at specialists stripped of project_root, dropping them back to
    ``Path.cwd()`` (= ``/app`` in the agent container — not a git repo,
    fails with ``exit 128``). A2A v1.0's ``Message.metadata`` channel is
    the spec-correct destination for these (see M7 scope) but the
    text-tag carrier ships value today on 0.3.x.
    """
    global _last_result
    t0 = time.monotonic()
    reset_last_seen_agent()  # Reset pipeline tracking for this run
    set_pipeline_chatter_enabled(gossip_enabled)

    # Build multi-part message so images travel alongside text in the A2A envelope.
    parts: list[Part] = [Part(TextPart(text=user_text))]
    for b64_data, mime_type in attachments or []:
        parts.append(
            Part(
                FilePart(
                    file=FileWithBytes(bytes=b64_data, mime_type=mime_type, name="screenshot.png")
                )
            )
        )
    message = Message(role=Role.user, parts=parts, message_id=str(uuid4()))
    message.context_id = context_id
    if task_id:
        message.task_id = task_id

    if verbose:
        img_count = len(attachments or [])
        _echo(
            f"{_DIM}[verbose] Sending {len(user_text)} chars"
            f"{f' + {img_count} image(s)' if img_count else ''}, context={context_id}{_RESET}"
        )

    final_state = None
    final_text = ""
    event_count = 0

    try:
        async for event in client.send_message(message):
            event_count += 1

            if isinstance(event, Message):
                for p in event.parts:
                    if hasattr(p.root, "text"):
                        text = p.root.text
                        _echo(text)
                        if tts:
                            await tts.speak(text, "hephaestus")
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
                    # M2 Change 4: detect MCP-elicitation markers carried
                    # over the streaming pipe. The text shape is "<emoji>
                    # [ELICIT:{id}:{agent}] <question>"; parse_outbound_
                    # marker accepts any prefix as long as it finds the
                    # pattern. When detected, we render an inline prompt
                    # and POST the answer to the specialist out-of-band —
                    # the streaming task stays open so the eventual
                    # artifact still reaches the player.
                    elicit_idx = text.find("[ELICIT:")
                    if elicit_idx >= 0:
                        marker = parse_outbound_marker(text[elicit_idx:])
                        if marker:
                            await _handle_elicitation(*marker)
                            continue
                    formatted, agent = _maidenify_status(text)
                    _echo(formatted)
                    if tts and agent:
                        # Extract the status message without the name box etc.
                        # For now, just speak the raw status (it doesn't have markdown)
                        msg = text.split(" ", 1)[-1] if " " in text else text
                        await tts.speak(msg, agent)

            elif isinstance(update, TaskArtifactUpdateEvent):
                text = _extract_artifact_text(update)
                if text:
                    final_text = text

            elif update is None:
                # Final task snapshot
                final_state = task.status.state

    except httpx.ConnectError:
        _echo(
            f"{_RED}\U0001f525 Hephaestus lost the forge connection \u2014 "
            f"try {_GOLD}/status{_RESET}{_RED} or {_GOLD}make up{_RESET}"
        )
        return True, context_id, task_id
    except httpx.TimeoutException:
        _echo(
            f"{_RED}\u23f3 Request timed out \u2014 "
            "the forge is running hot. Try again or simplify your request.{_RESET}"
        )
        return True, context_id, task_id

    elapsed = time.monotonic() - t0

    # Show final artifact with rendered markdown
    if final_text:
        _last_result = final_text
        _echo(
            f"\n{_GOLD}\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501{_RESET}"
        )
        rendered = _render_markdown(final_text)
        _echo(rendered)
        _echo(
            f"{_GOLD}\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501{_RESET}"
        )

        # Always show elapsed time — the golden forge signature
        _echo(f"{_GOLD_BRIGHT}\u2728 Forged in {elapsed:.1f}s{_RESET}")

        # Write a Memoir entry capturing this turn for FL training data.
        if memoir is not None and scene_id is not None:
            last_agent = get_last_seen_agent()
            if last_agent:
                try:
                    entry = build_pipeline_turn_entry(
                        scene_id=scene_id,
                        agent=last_agent,
                        agent_proposed=final_text,
                    )
                    memoir.append(entry)
                except (ValueError, OSError) as e:
                    # Memoir failures must not break the user's pipeline.
                    # Log at debug; the user already saw their result.
                    import logging

                    logging.getLogger("cli.streaming").debug("Memoir append skipped: %s", e)

        # Victory chatter from the last maiden who worked on this
        last_agent = get_last_seen_agent()
        if last_agent and gossip_enabled:
            victory = _victory_chatter(last_agent)
            if victory:
                _echo("")
                _echo(_comms_window(last_agent, victory, style="speak"))
                if tts:
                    await tts.speak(victory, last_agent)

        # Post-output suggestions
        _echo(f"{_DIM}/copy clipboard \u00b7 /save <file> \u00b7 /help commands{_RESET}")

    if verbose:
        _echo(f"{_DIM}[verbose] {event_count} events in {elapsed:.1f}s{_RESET}")

    # Handle input_required — prompt user for follow-up
    if final_state == TaskState.input_required:
        follow_up: str = await click.prompt(f"\n{_GOLD}\u21b3 Your response{_RESET}")
        if follow_up.strip().lower() in ("/q", "/quit", "quit"):
            return False, context_id, task_id
        # Re-prepend the original turn's bracket-tags so specialists
        # still receive [project_root: ...] / [yolo: on] / [auto_approve_reads: on]
        # on the resumed task. Without this, the M13 confirmation `yes`
        # arrives bare and Hephaestus's transcript-build emits an empty
        # `Project root:` line. Metis/Techne then fall back to Path.cwd()
        # (= /app inside the agent container) and git operations fail
        # with exit 128. Tags propagate per-turn until the player exits
        # to the REPL outer loop and the next turn rebuilds them.
        if forge_tags:
            follow_up = "\n".join((*forge_tags, follow_up))
        return await send_and_stream(
            client,
            follow_up,
            context_id,
            task_id,
            verbose,
            tts=tts,
            gossip_enabled=gossip_enabled,
            forge_tags=forge_tags,
        )

    return True, context_id, task_id


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------
async def _connect_with_url_override(
    url: str,
    config: ClientConfig,
) -> Client:
    """Connect to an agent, overriding the card URL with the reachable URL.

    Agent cards in Docker advertise internal hostnames (e.g. http://hephaestus:10000/)
    that the host machine cannot resolve. This fetches the card, patches the URL
    to the one we actually connected through, then hands it to the SDK.
    """
    http = config.httpx_client
    if http is None:
        raise ValueError("ClientConfig must have an httpx_client")
    resolver = A2ACardResolver(http, url)
    card = await resolver.get_agent_card()
    card.url = url
    return await ClientFactory.connect(card, client_config=config)
