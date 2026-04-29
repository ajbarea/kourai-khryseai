"""Core A2A communication — message sending and response streaming.

Contains the main send_and_stream() function and connection helpers.
"""

from __future__ import annotations

import re
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
from kourai_common.federation.host_helpers import build_pipeline_turn_entry
from kourai_common.hooks_interaction import synthesise_fact_from_pause
from kourai_common.pause_state import pop_preference_kind
from kourai_common.projects import derive_project_id

if TYPE_CHECKING:
    from a2a.client.client import Client

    from hosts.gui.tts_engine import TTSEngine
    from kourai_common.federation.memoir import Memoir

# ---------------------------------------------------------------------------
# Last result store — for /copy / /save
# ---------------------------------------------------------------------------
_last_result: str = ""


_PROJECT_ROOT_TAG = re.compile(r"\[project_root:\s*([^\]]+)\]", re.IGNORECASE)
# Explicit, project-stable id. Set by the REPL alongside ``[project_root: …]``
# so the M17 fact axis stays stable across forge sessions whose ``workdir`` is
# uuid'd per-turn. Specialists ignore this tag (their regex matches
# ``project_root`` only); only the streaming-side fact synthesiser reads it.
_PROJECT_ID_TAG = re.compile(r"\[project_id:\s*([^\]\s]+)\s*\]", re.IGNORECASE)


def _strip_forge_tag_prefix(text: str, forge_tags: list[str] | None) -> str:
    """Recover the bare follow-up text from a forge-tag-prefixed payload.

    ``send_and_stream`` re-prepends ``forge_tags`` (joined with ``\\n``)
    before recursing on an ``input_required`` follow-up; the M17 fact
    synthesiser wants the player's actual answer, not the prefix.
    """
    if not forge_tags:
        return text
    prefix = "\n".join(forge_tags) + "\n"
    return text.removeprefix(prefix)


def _project_id_from_forge_tags(forge_tags: list[str] | None) -> str | None:
    """Resolve the M17 fact-axis project id from forge tags.

    Prefers the explicit ``[project_id: <stable>]`` tag (carries the id
    derived from the project's persistent root). Falls back to deriving
    from ``[project_root: <path>]`` for callers that haven't been updated
    to emit the explicit tag yet — note this fallback is unstable when
    the path is a per-session forge worktree.
    """
    if not forge_tags:
        return None
    for tag in forge_tags:
        match = _PROJECT_ID_TAG.search(tag)
        if match:
            return match.group(1).strip()
    for tag in forge_tags:
        match = _PROJECT_ROOT_TAG.search(tag)
        if match:
            return derive_project_id(match.group(1).strip())
    return None


def _try_synthesise_pause_fact(
    *,
    context_id: str,
    user_text: str,
    forge_tags: list[str] | None,
) -> None:
    """Idempotently store a project-scoped fact when the resumed turn lands.

    Pops any pause stashed by a specialist's PAUSE token on a prior turn
    for ``context_id``. The pop is unconditional — turns with nothing
    stashed (the common case) make this a cheap no-op. When a pause is
    present, the player's bare answer becomes the fact body and the
    stashed ``source_agent`` carries through to ``synthesise_fact_from_pause``.
    """
    pending = pop_preference_kind(context_id)
    if pending is None:
        return

    bare_answer = _strip_forge_tag_prefix(user_text, forge_tags).strip()
    if not bare_answer:
        return

    try:
        from kourai_common.player_profile import PlayerProfile
    except ImportError:  # pragma: no cover — narrow guard for trimmed builds
        return

    profile = PlayerProfile.load()
    if not profile or not profile.player_id:
        return

    project_id = _project_id_from_forge_tags(forge_tags)
    synthesise_fact_from_pause(
        player_id=profile.player_id,
        project_id=project_id,
        preference_kind=pending.preference_kind,
        player_response=bare_answer,
        source_agent=pending.source_agent,
    )


def get_last_result() -> str:
    """Return the last artifact text from a completed pipeline run."""
    return _last_result


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

    # M17 Phase 1 — if the prior turn paused with a stashed preference_kind
    # (Metis's PAUSE token), this call carries the player's answer in
    # ``user_text``. Synthesise the project-scoped fact NOW so the resumed
    # turn's prompt-enrichment can already see it, and so a follow-on PAUSE
    # in this same turn doesn't overwrite the prior kind in the stash.
    _try_synthesise_pause_fact(
        context_id=context_id,
        user_text=user_text,
        forge_tags=forge_tags,
    )

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
