"""A2A bridge for Hephaestus — orchestrator executor with streaming progress."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

from a2a.types import Task, UnsupportedOperationError

from agents.hephaestus.agent import determine_pipeline, execute_pipeline
from agents.hephaestus.confirmation import parse_confirmation_response
from agents.metis.agent import discuss_tradeoffs
from kourai_common.a2a_utils import extract_file_attachments, get_message_metadata
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.messaging import data_part, send_input_required, send_working_status, text_part
from kourai_common.player import (
    PlayerProfile,
    get_affinity_tier,
    get_all_affinities,
    update_affinity,
)
from kourai_common.tracing import create_span
from kourai_common.virtues import update_virtue

if TYPE_CHECKING:
    from a2a.server.agent_execution import RequestContext
    from a2a.server.events import EventQueue
    from a2a.server.tasks import TaskUpdater

log = logging.getLogger(__name__)


# Emoji map for status messages
AGENT_EMOJI = {
    "hephaestus": "\U0001f525",  # fire
    "metis": "\U0001f4d0",  # triangular ruler
    "techne": "\u2699\ufe0f",  # gear
    "dokimasia": "\U0001f9ea",  # test tube
    "kallos": "\u2728",  # sparkles
    "mneme": "\U0001f4dc",  # scroll
}


class HephaestusAgentExecutor(BaseAgentExecutor):
    """A2A executor for the Hephaestus orchestrator."""

    def get_input_required_message(self) -> str:
        return (
            "What would you like me to help with? "
            "I can route your request to the right specialist agents."
        )

    @executor_error_handler(agent_name="hephaestus")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        log.info("Hephaestus execute triggered")
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        """Hephaestus-specific: determine pipeline and orchestrate specialist agents."""
        with create_span("hephaestus.execute", {"a2a.method": "execute"}):
            user_input = context.get_user_input()
            forge_meta = get_message_metadata(context)

            # Step 1: Determine the pipeline
            await send_working_status(
                updater,
                task,
                "Analyzing request...",
                emoji=AGENT_EMOJI["hephaestus"],
            )

            # M14 — kick Metis's discuss_tradeoffs in parallel with the
            # router classifier so the dead zone between "Analyzing
            # request..." and the CONFIRM_ORDER card becomes useful
            # architectural context. Surfaced to the player only on
            # tier-2 (smart) and tier-3 (clarify) confirmations; on
            # tier-1 (clear) Metis stays silent so the read-back beat
            # is a beat, not an interrogation. Skip entirely when
            # /yolo is on — power-user flow doesn't want the chatter.
            metis_task = self._maybe_spawn_metis_discussion(
                user_input, task.context_id, metadata=forge_meta
            )

            try:
                pipeline = await determine_pipeline(
                    user_input,
                    context_id=task.context_id,
                    metadata=forge_meta,
                )
            except Exception:
                await self._cancel_metis(metis_task)
                raise

            # Handle non-pipeline responses
            if isinstance(pipeline, str):
                # M13 — Forge Order Confirmation gate. Hephaestus's router
                # ALWAYS emits CONFIRM_ORDER before any pipeline; we surface
                # the read-back to the player via INPUT_REQUIRED and let
                # the A2A task pause. The next user message lands in the
                # same context_id, the LLM sees the prior CONFIRM_ORDER
                # turn in memory, and emits the agent list (response #1)
                # on the resumed routing call. No explicit resume metadata
                # plumbing needed.
                if pipeline.startswith("CONFIRM_ORDER:"):
                    try:
                        confirmation = parse_confirmation_response(pipeline)
                        # Compose the input_required message so the existing
                        # _maidenify_status pipeline in the host renders it
                        # as a Hephaestus comms window (via the 🔥 emoji
                        # prefix) and italicizes the read-back per M10
                        # (the LLM already wraps it in double quotes).
                        # Tier-specific hint trails on smart/clarify so the
                        # player knows whether to expect Metis chiming in
                        # or whether the forge is genuinely waiting.
                        body = confirmation.read_back
                        if confirmation.tier == "smart":
                            body += "  (Metis is muttering — say the word.)"
                        elif confirmation.tier == "clarify":
                            body += "  (Forge cools while we sort this out.)"
                        message = f"{AGENT_EMOJI['hephaestus']} {body}"
                    except ValueError as parse_err:
                        # Fail-safe: malformed token from the LLM (rare).
                        # Don't crash the request and don't auto-execute.
                        # Surface a generic ask so the player can clarify.
                        log.warning(
                            "Hephaestus emitted malformed CONFIRM_ORDER (%s); "
                            "surfacing generic ask. Raw: %r",
                            parse_err,
                            pipeline,
                        )
                        # No tier on parse failure — discard Metis's work.
                        await self._cancel_metis(metis_task)
                        message = (
                            f"{AGENT_EMOJI['hephaestus']} \"I couldn't parse "
                            "my own confirmation. Could you re-state the "
                            'request?"'
                        )
                        await send_input_required(updater, task, message)
                        return

                    # M14 — surface Metis's parallel discussion BEFORE the
                    # confirmation card on smart/clarify tiers, so the
                    # player has architectural context when they decide.
                    # On clear tier, discard Metis's work — the player
                    # just wants to ship and a wall of text would be noise.
                    if confirmation.tier in ("smart", "clarify"):
                        await self._await_and_emit_metis(metis_task, updater, task)
                    else:
                        await self._cancel_metis(metis_task)

                    await send_input_required(updater, task, message)
                    return

                if pipeline.startswith("ASK_USER:"):
                    # Ambiguous request — Metis's discussion is moot
                    # because we don't know what to discuss yet.
                    await self._cancel_metis(metis_task)
                    clarification = pipeline.removeprefix("ASK_USER:").strip()
                    await send_input_required(
                        updater,
                        task,
                        clarification,
                    )
                    return

                if pipeline.startswith("CHAT:"):
                    # Conversational route — Metis's architectural notes
                    # are irrelevant to a casual chat. Drop her output.
                    await self._cancel_metis(metis_task)
                    chat_body = pipeline.removeprefix("CHAT:").strip()
                    # Check for agent-directed chat: "CHAT:kallos: ..."
                    # Includes companion spirits puck and cupid
                    target_agent = None
                    for agent_name in (
                        "metis",
                        "techne",
                        "dokimasia",
                        "kallos",
                        "mneme",
                        "puck",
                        "cupid",
                    ):
                        prefix = f"{agent_name}:"
                        if chat_body.lower().startswith(prefix):
                            target_agent = agent_name
                            chat_body = chat_body[len(prefix) :].strip()
                            break

                    if target_agent:
                        # Route to specific agent for casual chat
                        emoji = AGENT_EMOJI.get(target_agent, "")
                        await send_working_status(
                            updater,
                            task,
                            chat_body or f"Connecting to {target_agent}...",
                            emoji=emoji,
                        )
                    else:
                        # Hephaestus responds directly
                        await send_working_status(
                            updater,
                            task,
                            chat_body,
                            emoji=AGENT_EMOJI["hephaestus"],
                        )

                    await updater.add_artifact(
                        [
                            text_part(chat_body),
                            data_part(
                                {
                                    "mode": "chat",
                                    "target_agent": target_agent,
                                }
                            ),
                        ],
                        name="chat_response",
                    )
                    await updater.complete()
                    log.info("Hephaestus chat — target: %s", target_agent or "self")

                    # Update affinity for the agent that spoke
                    _responding_agent = target_agent or "hephaestus"
                    _profile = PlayerProfile.load()
                    if _profile:
                        _new_score = update_affinity(
                            _profile.player_id, _responding_agent, delta=0.02
                        )
                        log.info(
                            "Affinity updated: %s → %.2f (tier %d)",
                            _responding_agent,
                            _new_score,
                            get_affinity_tier(_new_score),
                        )
                    return

            # Step 2: Report the pipeline (pipeline must be list[str] here)
            # Reaching this branch means /yolo bypassed CONFIRM_ORDER and
            # we got the agent list directly. Player wants speed, not
            # commentary — drop Metis's parallel discussion silently.
            await self._cancel_metis(metis_task)

            if not isinstance(pipeline, list):
                raise TypeError(
                    f"Pipeline should be list[str] at this point, but got {type(pipeline)}"
                )

            pipeline_display = " -> ".join(pipeline)
            await send_working_status(
                updater,
                task,
                f"Pipeline: {pipeline_display}",
                emoji=AGENT_EMOJI["hephaestus"],
            )

            # Step 3: Execute pipeline with real-time status updates
            image_attachments = extract_file_attachments(context)
            last_agent_output = ""
            input_required = False
            async for agent_name, status, agent_output in execute_pipeline(
                pipeline,
                user_input,
                task.context_id,
                image_attachments or None,
                metadata=forge_meta,
            ):
                # Detect INPUT_REQUIRED from specialist agents
                if status.startswith("INPUT_REQUIRED:"):
                    question = status.removeprefix("INPUT_REQUIRED:")
                    emoji = AGENT_EMOJI.get(agent_name, "")
                    await send_input_required(
                        updater,
                        task,
                        f"{emoji} {agent_name} needs your input: {question}",
                    )
                    input_required = True
                    break

                emoji = AGENT_EMOJI.get(agent_name, "")
                await send_working_status(
                    updater,
                    task,
                    status,
                    emoji=emoji,
                )
                # Track the last real agent output for the final artifact
                if agent_output:
                    last_agent_output = agent_output

            if input_required:
                return

            # Step 4: Virtue + affinity updates, jealousy check — all before complete()
            _profile = PlayerProfile.load()
            if _profile:
                update_virtue(_profile.player_id, "sophia", 0.005)
                update_virtue(_profile.player_id, "synergy", 0.005)

                for _agent_name in pipeline:
                    _new_score = update_affinity(_profile.player_id, _agent_name, delta=0.01)
                    log.debug(
                        "Affinity updated: %s → %.2f (tier %d)",
                        _agent_name,
                        _new_score,
                        get_affinity_tier(_new_score),
                    )

            # Jealousy check: flag in DataPart when one agent is far ahead (>0.3 spread).
            # Hosts read jealousy_trigger from the artifact DataPart and route to Cupid.
            jealousy_trigger: dict | None = None
            if _profile:
                all_aff = get_all_affinities(_profile.player_id)
                if len(all_aff) > 1:
                    scores = [v["affinity_score"] for v in all_aff.values()]
                    if max(scores) - min(scores) > 0.3:
                        sorted_agents = sorted(
                            all_aff.items(), key=lambda x: x[1]["affinity_score"], reverse=True
                        )
                        top_agent = sorted_agents[0][0]
                        bottom_agent = sorted_agents[-1][0]
                        jealousy_trigger = {"top": top_agent, "bottom": bottom_agent}
                        log.info("Jealousy triggered: %s far ahead of %s", top_agent, bottom_agent)

            # Step 5: Emit artifact then complete
            pipeline_data: dict = {
                "mode": "pipeline",
                "agents": pipeline,
                "agent_count": len(pipeline),
            }
            if jealousy_trigger:
                pipeline_data["jealousy_trigger"] = jealousy_trigger

            await updater.add_artifact(
                [
                    text_part(last_agent_output or "Pipeline complete"),
                    data_part(pipeline_data),
                ],
                name="pipeline_result",
            )
            await updater.complete()
            log.info("Hephaestus pipeline completed: %s", pipeline_display)

    # ── M14 Metis-First Parallel Routing helpers ──────────────────

    def _maybe_spawn_metis_discussion(
        self,
        user_input: str,
        context_id: str | None,
        *,
        metadata: dict | None = None,
    ) -> asyncio.Task[str] | None:
        """Spawn Metis's ``discuss_tradeoffs`` as a parallel asyncio task.

        Returns the task so cancellation/awaiting is the caller's
        responsibility. Skips entirely when ``yolo`` is on — the
        power-user opt-out also opts out of the parallel chatter.
        """
        md = metadata or {}
        yolo = bool(md.get("yolo")) or md.get("yolo") == "on"
        if yolo:
            log.debug("yolo on — skipping parallel Metis discussion")
            return None
        return asyncio.create_task(
            discuss_tradeoffs(user_input, context_id=context_id),
            name="metis-discuss-tradeoffs",
        )

    async def _cancel_metis(self, metis_task: asyncio.Task[str] | None) -> None:
        """Cancel Metis's discussion and swallow ``CancelledError``.

        Used when the route turns out to be CHAT, ASK_USER, malformed
        CONFIRM_ORDER, tier-1 (clear) confirmation, or yolo pipeline —
        any path where the player won't see Metis's output.
        """
        if metis_task is None or metis_task.done():
            return
        metis_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await metis_task

    async def _await_and_emit_metis(
        self,
        metis_task: asyncio.Task[str] | None,
        updater: TaskUpdater,
        task: Task,
        deadline_seconds: float = 8.0,
    ) -> None:
        """Wait for Metis's discussion (with deadline) and emit as a status event.

        Called only on tier-2 (smart) and tier-3 (clarify) confirmations.
        The deadline guards against a Metis call that drags past the
        classifier's wall-clock window — better to drop her contribution
        than make the player wait for it. Output is emitted with the
        Metis emoji prefix so the existing host-side ``_maidenify_status``
        renders it as a Metis comms window, italicizing any quoted
        speech per M10.
        """
        if metis_task is None:
            return
        try:
            metis_text = await asyncio.wait_for(metis_task, timeout=deadline_seconds)
        except (TimeoutError, asyncio.CancelledError):
            log.debug("Metis discussion timed out or cancelled — skipping emit")
            await self._cancel_metis(metis_task)
            return
        except Exception:
            log.warning("Metis discussion errored — skipping emit", exc_info=True)
            return

        text = (metis_text or "").strip()
        if not text:
            return
        await send_working_status(updater, task, text, emoji=AGENT_EMOJI["metis"])

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise UnsupportedOperationError()
