"""A2A executor for Puck — tutorial daimon."""

from __future__ import annotations

import logging

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.puck.agent import respond
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.facts import extract_facts, store_facts, strip_facts
from kourai_common.messaging import send_working_status
from kourai_common.player import PlayerProfile

log = logging.getLogger(__name__)


class PuckAgentExecutor(BaseAgentExecutor):
    """A2A executor for Puck."""

    def get_input_required_message(self) -> str:
        return "What is it? I'm everywhere but I'm still busy."

    @executor_error_handler(agent_name="puck")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        user_input = context.get_user_input()

        await send_working_status(updater, task, "Puck stirs...", emoji="🎭")

        profile = PlayerProfile.load()
        player_id = profile.player_id if profile else ""

        response = await respond(
            user_input, player_id=player_id or None, context_id=task.context_id
        )

        # Extract + store player facts; strip tags before sending to player
        facts = extract_facts(response, source_agent="puck")
        if facts and player_id:
            store_facts(player_id, facts)
        clean_response = strip_facts(response)

        # Optional: persist to Memory MCP knowledge graph (graceful degradation)
        if facts and player_id:
            try:
                from kourai_common.mcp_client import create_memory_entities  # noqa: PLC0415

                await create_memory_entities(
                    [
                        {
                            "name": player_id,
                            "entityType": "Player",
                            "observations": [f.body for f in facts],
                        }
                    ]
                )
            except Exception:  # noqa: BLE001, S110
                pass

        # Emit both human-readable text and structured metadata (C10 pattern)
        await updater.add_artifact(
            [
                Part(root=TextPart(text=clean_response)),
                Part(
                    root=DataPart(
                        data={
                            "mode": "guidance",
                            "context": "tutorial, nudge, gossip, or minigame",
                            "next_routing": "player_choice or self_contained",
                        }
                    )
                ),
            ],
            name="puck_response",
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
