"""Core A2A communication — message sending and response streaming.

Contains the main send_and_stream() function and connection helpers.
"""

from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING, Any

import asyncclick as click
import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.types import (
    Message,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
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
from hosts.cli.maidens import _MAIDEN_FACES
from hosts.cli.rendering import (
    _comms_window,
    _echo,
    _render_markdown,
    karaoke_dialogue_close,
    karaoke_dialogue_open,
    karaoke_word_separator,
    synthesis_indicator,
    synthesis_indicator_clear,
)
from hosts.cli.styling import _DIM, _GOLD, _GOLD_BRIGHT, _RED, _RESET
from kourai_common.a2a_events import extract_artifact_data
from kourai_common.federation.host_helpers import build_pipeline_turn_entry
from kourai_common.hooks_interaction import synthesise_fact_from_pause
from kourai_common.message_classifier import is_scratchpad_content
from kourai_common.messaging import (
    KIND_DIALOGUE,
    file_part_from_b64,
    get_content_kind,
    send_request,
    stream_event,
    user_message,
)
from kourai_common.pause_state import pop_preference_kind
from kourai_common.projects import derive_project_id
from kourai_common.scratchpad import get_scratchpad

if TYPE_CHECKING:
    from a2a.client.client import Client
    from a2a.types import AgentCard

    from kourai_common.federation.memoir import Memoir
    from kourai_common.tts_realtime import RealtimeTTSEngine

# ---------------------------------------------------------------------------
# Last result store — for /copy / /save
# ---------------------------------------------------------------------------
_last_result: str = ""


def _project_id_from_metadata(forge_metadata: dict[str, Any] | None) -> str | None:
    """Resolve the M17 fact-axis project id from the message's forge metadata.

    Prefers the explicit ``project_id`` key (the stable, project-rooted
    sha256). Falls back to deriving from ``project_root`` for callers
    that haven't surfaced the explicit id yet — that fallback is unstable
    when the path is a per-session forge worktree.
    """
    if not forge_metadata:
        return None
    explicit = forge_metadata.get("project_id")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    root = forge_metadata.get("project_root")
    if isinstance(root, str) and root.strip():
        return derive_project_id(root.strip())
    return None


def _try_synthesise_pause_fact(
    *,
    context_id: str,
    user_text: str,
    forge_metadata: dict[str, Any] | None,
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

    bare_answer = (user_text or "").strip()
    if not bare_answer:
        return

    try:
        from kourai_common.player_profile import PlayerProfile
    except ImportError:  # pragma: no cover — narrow guard for trimmed builds
        return

    profile = PlayerProfile.load()
    if not profile or not profile.player_id:
        return

    project_id = _project_id_from_metadata(forge_metadata)
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
    tts: RealtimeTTSEngine | None = None,
    gossip_enabled: bool = True,
    captions_enabled: bool = True,
    dialogue_sync_mode: str = "audio-led",
    *,
    memoir: Memoir | None = None,
    scene_id: str | None = None,
    forge_metadata: dict[str, Any] | None = None,
) -> tuple[bool, str, str | None]:
    """Send a message and stream the response.

    Returns:
        (continue_loop, context_id, task_id) tuple.

    ``forge_metadata`` rides on the outbound ``Message.metadata`` channel
    (M7 Phase 5). Carries ``project_root``, ``project_id``, ``yolo``, and
    ``auto_approve_reads`` so specialists chdir into the worktree, drop
    CONFIRM_ORDER when the player has /yolo on, and resolve the M17 fact
    axis. Propagates across input_required follow-ups (M13 confirmations,
    mid-pipeline ASK_USER replies) by being re-passed on the recursive
    call below.
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
        forge_metadata=forge_metadata,
    )

    # Build multi-part message so images travel alongside text in the A2A envelope.
    extra_parts = [
        file_part_from_b64(
            b64_data=b64_data,
            media_type=mime_type,
            filename="screenshot.png",
        )
        for b64_data, mime_type in (attachments or [])
    ]
    message = user_message(
        user_text,
        context_id=context_id,
        task_id=task_id or None,
        extra_parts=extra_parts or None,
        metadata=forge_metadata,
    )

    if verbose:
        img_count = len(attachments or [])
        _echo(
            f"{_DIM}[verbose] Sending {len(user_text)} chars"
            f"{f' + {img_count} image(s)' if img_count else ''}, context={context_id}{_RESET}"
        )

    final_state = None
    final_text = ""
    event_count = 0
    # None = mneme didn't emit commit_messages (no scribe step in the
    # pipeline); 0 = mneme ran but produced no commits.
    observed_commit_count: int | None = None

    try:
        async for response in client.send_message(send_request(message)):
            event_count += 1
            event = stream_event(response)

            if isinstance(event, Message):
                for p in event.parts:
                    if p.HasField("text"):
                        text = p.text
                        _echo(text)
                        if tts:
                            await tts.speak(text, "hephaestus")
                continue

            if isinstance(event, TaskStatusUpdateEvent):
                if event.context_id:
                    context_id = event.context_id
                task_id = event.task_id
                final_state = event.status.state
                text = _extract_status_text(event)
                if text:
                    formatted, agent = _maidenify_status(text)
                    # Strict M18 routing: only KIND_DIALOGUE goes to TTS.
                    kind = get_content_kind(event.status.message)
                    # Cross-host scratchpad rebuild: agent reasoning
                    # (multi-line bullet / TODO / checkbox text) gets
                    # buffered so /scratchpad can recall it later.
                    # Side-effect only — display routing below stays
                    # unchanged so players still see reasoning inline.
                    if agent and kind != KIND_DIALOGUE and is_scratchpad_content(text):
                        get_scratchpad().add(agent, text)
                    # Captions off + TTS on → audio-only (drop visual);
                    # without TTS, visual must land or dialogue is lost.
                    suppress_visual = (
                        kind == KIND_DIALOGUE and tts is not None and not captions_enabled
                    )
                    will_speak = kind == KIND_DIALOGUE and tts is not None and bool(agent)
                    will_display = not suppress_visual
                    audio_led = dialogue_sync_mode == "audio-led"

                    if will_display and will_speak and audio_led:
                        # M20 sub-task 2 Tier 1 (karaoke single-line) +
                        # Tier 2 (deferred box) fallback. The closures
                        # are invoked synchronously inside this iteration's
                        # `await tts.speak(...)` and never outlive it, so
                        # `formatted`, `agent`, `face`, `karaoke_started`,
                        # `indicator_shown`, `last_was_word`, and
                        # `words_revealed` cannot rebind before either
                        # callback runs. Suppressed with B023 inline.
                        karaoke_started = [False]
                        last_was_word = [False]
                        words_revealed = [False]
                        indicator_shown = [False]
                        face = _MAIDEN_FACES.get(agent or "", "")

                        # Pre-render the synthesis indicator so the player
                        # sees that the agent is about to speak during the
                        # ~3s Kokoro CPU synthesis-wait window before
                        # _open_karaoke fires.
                        _echo(synthesis_indicator(agent or "", face), nl=False)
                        indicator_shown[0] = True

                        def _open_karaoke() -> None:
                            if karaoke_started[0]:  # noqa: B023
                                return
                            if indicator_shown[0]:  # noqa: B023
                                _echo(synthesis_indicator_clear(), nl=False)
                                indicator_shown[0] = False  # noqa: B023
                            _echo(
                                karaoke_dialogue_open(agent or "", face),  # noqa: B023
                                nl=False,
                            )
                            karaoke_started[0] = True  # noqa: B023

                        def _reveal_word(word: object) -> None:
                            w = getattr(word, "word", "")
                            if not w:
                                return
                            sep = karaoke_word_separator(w, last_was_word[0])  # noqa: B023
                            _echo(sep + w, nl=False)
                            last_was_word[0] = True  # noqa: B023
                            words_revealed[0] = True  # noqa: B023

                        msg = text.split(" ", 1)[-1] if " " in text else text
                        try:
                            await tts.speak(
                                msg,
                                agent,
                                on_audio_start=_open_karaoke,
                                on_word=_reveal_word,
                            )
                        finally:
                            if karaoke_started[0]:
                                if words_revealed[0]:
                                    # Close the karaoke quote after words
                                    # were revealed.
                                    _echo(karaoke_dialogue_close(), nl=False)
                                else:
                                    # Karaoke started but no words revealed
                                    # (Kokoro CPU engine or auto-muted).
                                    # Fall back to static text render.
                                    _echo(formatted)
                            else:
                                # Tier 2 fallback — neither audio_start
                                # nor on_word fired (auto-muted, engine
                                # never reached playback). Wipe the
                                # indicator first so the box doesn't
                                # render below a stuck ellipsis line.
                                if indicator_shown[0]:
                                    _echo(synthesis_indicator_clear(), nl=False)
                                    indicator_shown[0] = False
                                _echo(formatted)
                    elif will_display and will_speak:
                        # M20 sub-task 4 "instant" mode: legacy behavior
                        # — text appears immediately, audio catches up.
                        _echo(formatted)
                        msg = text.split(" ", 1)[-1] if " " in text else text
                        await tts.speak(msg, agent)
                    elif will_display:
                        _echo(formatted)
                    elif will_speak:
                        msg = text.split(" ", 1)[-1] if " " in text else text
                        await tts.speak(msg, agent)

            elif isinstance(event, TaskArtifactUpdateEvent):
                if event.context_id:
                    context_id = event.context_id
                task_id = event.task_id
                text = _extract_artifact_text(event)
                if text:
                    final_text = text
                for payload in extract_artifact_data(event):
                    if "commit_count" in payload:
                        with contextlib.suppress(TypeError, ValueError):
                            observed_commit_count = int(payload["commit_count"])

            elif isinstance(event, Task):
                # Final task snapshot
                if event.context_id:
                    context_id = event.context_id
                task_id = event.id
                final_state = event.status.state

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

    # COMPLETED + no commits is a legitimate non-mneme run (metis-only
    # spec discussion). FAILED + no commit_count is the crash
    # discriminator that triggers the abort banner.
    softfail_message: str | None = None
    if observed_commit_count == 0:
        softfail_message = (
            "the forge ran but nothing landed. Check the result above for what Mneme reported."
        )
    elif observed_commit_count is None and final_state == TaskState.TASK_STATE_FAILED:
        softfail_message = "the forge aborted before Mneme could commit. Nothing landed."

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

        if softfail_message:
            _echo(f"{_RED}\u26a0 No commits produced \u2014 {softfail_message}{_RESET}")

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

        _echo(f"{_DIM}/copy clipboard \u00b7 /save <file> \u00b7 /help commands{_RESET}")

    elif softfail_message:
        # Aborted before any artifact landed; without this branch the
        # stream trails off silently after the last specialist's status.
        _echo(f"{_RED}\u26a0 No commits produced \u2014 {softfail_message}{_RESET}")
        _echo(f"{_RED}Forge aborted at {elapsed:.1f}s{_RESET}")

    if verbose:
        _echo(f"{_DIM}[verbose] {event_count} events in {elapsed:.1f}s{_RESET}")

    if final_state == TaskState.TASK_STATE_INPUT_REQUIRED:
        follow_up: str = await click.prompt(f"\n{_GOLD}\u21b3 Your response{_RESET}")
        if follow_up.strip().lower() in ("/q", "/quit", "quit"):
            return False, context_id, task_id
        # Stash original_request in metadata so Hephaestus's resumed
        # routing relays the actual ask, not the confirmation token
        # ("yes" / "light it"). Forward forge_metadata too — without
        # project_root, Metis/Techne fall back to Path.cwd() = /app in
        # the container and git operations exit 128.
        follow_up_metadata: dict[str, Any] = dict(forge_metadata or {})
        original_request = (user_text or "").strip()
        if original_request:
            follow_up_metadata["original_request"] = original_request
        return await send_and_stream(
            client,
            follow_up,
            context_id,
            task_id,
            verbose,
            tts=tts,
            gossip_enabled=gossip_enabled,
            captions_enabled=captions_enabled,
            forge_metadata=follow_up_metadata or None,
        )

    return True, context_id, task_id


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------
async def _connect_with_url_override(
    url: str,
    config: ClientConfig,
) -> tuple[Client, AgentCard]:
    """Connect to an agent, overriding the card URL with the reachable URL.

    Agent cards in Docker advertise internal hostnames (e.g. http://hephaestus:10000/)
    that the host machine cannot resolve. This fetches the card, patches the URL
    to the one we actually connected through, then hands it to the SDK. The
    fetched card is returned alongside the client so callers can read
    name/version/skills without a second round-trip — a2a-sdk 1.0's Client
    does not expose ``get_card()``.
    """
    http = config.httpx_client
    if http is None:
        raise ValueError("ClientConfig must have an httpx_client")
    resolver = A2ACardResolver(http, url)
    card = await resolver.get_agent_card()
    for interface in card.supported_interfaces:
        interface.url = url
    client = await create_client(card, client_config=config)
    return client, card
