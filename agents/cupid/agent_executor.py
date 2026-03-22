"""A2A executor for Cupid — romantic eros spirit."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from a2a.types import DataPart, Part, Task, TextPart, UnsupportedOperationError
from a2a.utils.errors import ServerError

from agents.cupid.agent import translate_emotion
from kourai_common.base_executor import BaseAgentExecutor
from kourai_common.decorators import executor_error_handler
from kourai_common.facts import extract_facts, store_facts, strip_facts
from kourai_common.messaging import send_working_status
from kourai_common.player import PlayerProfile, get_all_affinities

if TYPE_CHECKING:
    from a2a.server.agent_execution import RequestContext
    from a2a.server.events import EventQueue
    from a2a.server.tasks import TaskUpdater

log = logging.getLogger(__name__)


class CupidAgentExecutor(BaseAgentExecutor):
    """A2A executor for Cupid."""

    def get_input_required_message(self) -> str:
        return "Tell me the situation. I'm very good at these."

    @executor_error_handler(agent_name="cupid")
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        await super().execute(context, event_queue)

    async def execute_agent_logic(
        self, context: RequestContext, task: Task, updater: TaskUpdater
    ) -> None:
        user_input = context.get_user_input()

        await send_working_status(updater, task, "Reading the room...", emoji="💘")

        profile = PlayerProfile.load()
        player_id = profile.player_id if profile else ""

        response = await translate_emotion(
            user_input, player_id=player_id, context_id=task.context_id
        )

        # Extract + store player facts; strip tags before sending to player
        facts = extract_facts(response, source_agent="cupid")
        if facts and player_id:
            store_facts(player_id, facts)
        clean_response = strip_facts(response)

        # Optional: persist relationship state to Memory MCP (graceful degradation)
        if player_id:
            try:
                from kourai_common.mcp_client import create_memory_entities

                affinities = get_all_affinities(player_id) or {}
                observations = [
                    f"Affinity with {agent}: {data.get('affinity_score', 0):.2f}"
                    for agent, data in affinities.items()
                ]
                if observations:
                    await create_memory_entities(
                        [
                            {
                                "name": f"{player_id}_relationships",
                                "entityType": "PlayerRelationships",
                                "observations": observations,
                            }
                        ]
                    )
            except Exception:  # noqa: S110
                pass

        # Emit both human-readable text and structured metadata (C10 pattern)
        await updater.add_artifact(
            [
                Part(root=TextPart(text=clean_response)),
                Part(
                    root=DataPart(
                        data={
                            "mode": "emotional_translation",
                            "context": "romance_coach, jealousy_mediator, or confession_handler",
                            "next_routing": "player_choice or self_contained",
                        }
                    )
                ),
            ],
            name="cupid_response",
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
