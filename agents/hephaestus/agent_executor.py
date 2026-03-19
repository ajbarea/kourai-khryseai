"""A2A bridge for Hephaestus — orchestrator executor with streaming progress."""

from __future__ import annotations

import logging

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.hephaestus.routing_agent import determine_pipeline, execute_pipeline
from kourai_common.a2a_utils import extract_file_attachments
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.messaging import send_input_required, send_working_status
from kourai_common.player import (
    PlayerProfile,
    get_affinity_tier,
    get_all_affinities,
    update_affinity,
)
from kourai_common.tracing import create_span
from kourai_common.virtues import update_virtue

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

            # Step 1: Determine the pipeline
            await send_working_status(
                updater,
                task,
                "Analyzing request...",
                emoji=AGENT_EMOJI["hephaestus"],
            )

            pipeline = await determine_pipeline(user_input, context_id=task.context_id)

            # Handle non-pipeline responses
            if isinstance(pipeline, str):
                if pipeline.startswith("ASK_USER:"):
                    clarification = pipeline.removeprefix("ASK_USER:").strip()
                    await send_input_required(
                        updater,
                        task,
                        clarification,
                    )
                    return

                if pipeline.startswith("CHAT:"):
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
                            Part(root=TextPart(text=chat_body)),
                            Part(
                                root=DataPart(
                                    data={
                                        "mode": "chat",
                                        "target_agent": target_agent,
                                    }
                                )
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
                pipeline, user_input, task.context_id, image_attachments or None
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

            # Step 4: Emit both human-readable and structured pipeline result
            await updater.add_artifact(
                [
                    Part(root=TextPart(text=last_agent_output or "Pipeline complete")),
                    Part(
                        root=DataPart(
                            data={
                                "mode": "pipeline",
                                "agents": pipeline,
                                "agent_count": len(pipeline),
                            }
                        )
                    ),
                ],
                name="pipeline_result",
            )
            await updater.complete()
            log.info("Hephaestus pipeline completed: %s", pipeline_display)

            # Virtue update: completed pipeline → Sophia (quality of intent)
            _profile = PlayerProfile.load()
            if _profile:
                update_virtue(_profile.player_id, "sophia", 0.005)
                update_virtue(_profile.player_id, "synergy", 0.005)

            # Update affinity for each agent that participated in the pipeline
            if _profile:
                for _agent_name in pipeline:
                    _new_score = update_affinity(_profile.player_id, _agent_name, delta=0.01)
                    log.debug(
                        "Affinity updated: %s → %.2f (tier %d)",
                        _agent_name,
                        _new_score,
                        get_affinity_tier(_new_score),
                    )

                # Task 4: Jealousy Trigger Check (>0.3 delta)
                all_aff = get_all_affinities(_profile.player_id)
                if len(all_aff) > 1:
                    scores = [a["affinity_score"] for a in all_aff.values()]
                    if max(scores) - min(scores) > 0.3:
                        # Find top and bottom agents for the message
                        sorted_agents = sorted(
                            all_aff.items(), key=lambda x: x[1]["affinity_score"], reverse=True
                        )
                        top_agent = sorted_agents[0][0]
                        bottom_agent = sorted_agents[-1][0]

                        await send_working_status(
                            updater,
                            task,
                            f"CHAT:cupid: Jealousy triggered — {top_agent} is far ahead of {bottom_agent}.",
                            emoji="💘",
                        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
