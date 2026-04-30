"""A2A client connections to specialist agents."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    Message,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
)

from kourai_common.a2a_events import (
    extract_message_text,
    extract_parts_text,
    extract_status_text,
    extract_task_text,
)
from kourai_common.a2a_utils import make_a2a_http_client
from kourai_common.agents_manifest import fallback_card_for
from kourai_common.messaging import file_part_from_b64, user_message
from kourai_common.tracing import create_span, get_trace_context

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from a2a.client.client import Client

log = logging.getLogger(__name__)


class AgentInputRequired(Exception):
    """Raised when a specialist agent needs user clarification."""

    def __init__(self, agent_name: str, question: str):
        self.agent_name = agent_name
        self.question = question
        super().__init__(f"{agent_name} needs input: {question}")


class RemoteAgentConnection:
    """Wraps an A2A client connection to a single specialist agent."""

    def __init__(self, agent_name: str, agent_url: str):
        self.agent_name = agent_name
        self.agent_url = agent_url
        self.http = make_a2a_http_client(
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0),
        )
        self.client: Client | None = None
        self.card: AgentCard | None = None

    async def connect(self) -> None:
        """Fetch the agent card and initialize the A2A client.

        If live ``.well-known/agent-card`` fetch fails (specialist not up yet,
        network blip), fall back to a synthesized card so Hephaestus boot is
        not blocked — the next ``send()`` will naturally retry discovery.
        """
        with create_span(f"a2a.connect.{self.agent_name}", {"url": self.agent_url}):
            resolver = A2ACardResolver(self.http, self.agent_url)
            try:
                self.card = await resolver.get_agent_card()
            except Exception as exc:
                log.warning(
                    "Live agent card fetch failed for %s (%s); using manifest fallback",
                    self.agent_name,
                    exc,
                )
                self.card = fallback_card_for(self.agent_name, self.agent_url)
            if self.card:
                # Override every supported_interfaces URL with the Docker-network
                # address Hephaestus can actually reach. The agent may advertise
                # an internal hostname that's not resolvable from this side.
                for interface in self.card.supported_interfaces:
                    interface.url = self.agent_url
                config = ClientConfig(
                    streaming=True,
                    httpx_client=self.http,
                )
                factory = ClientFactory(config)
                self.client = factory.create(self.card)
                log.info("Connected to %s at %s", self.card.name, self.agent_url)

    async def send(
        self,
        text: str,
        context_id: str,
        attachments: list[tuple[str, str]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncGenerator[tuple[str, str], None]:
        """Send a message to the specialist and yield status and result updates.

        Args:
            text: The message/task content to send.
            context_id: Conversation context ID for multi-turn.
            attachments: Optional list of (base64_bytes, mime_type) image attachments.
            metadata: Forge metadata (``project_root``, ``project_id``,
                ``relationship_tiers``, etc.) to propagate to the specialist.
                Merged with the OTel trace-context dict so the wire metadata
                carries both transport-level (trace) and forge-level keys.

        Yields:
            Tuples of (event_type, text) where event_type is "status" or "result".
        """
        if not self.client:
            raise RuntimeError(f"Not connected to {self.agent_name}. Call connect() first.")

        with create_span(
            f"a2a.send.{self.agent_name}",
            {"target_agent": self.agent_name, "context_id": context_id},
        ):
            # Build multi-part message when images are present; plain text otherwise.
            extra_parts = [
                file_part_from_b64(
                    b64_data=b64_data,
                    media_type=mime_type,
                    filename="attachment.png",
                )
                for b64_data, mime_type in (attachments or [])
            ]
            merged_metadata: dict[str, Any] = dict(metadata or {})
            merged_metadata.update(get_trace_context())
            message = user_message(
                text,
                context_id=context_id,
                extra_parts=extra_parts or None,
                metadata=merged_metadata,
            )

            log.info("Sending to %s: %d chars", self.agent_name, len(text))
            latest_artifact_text = ""

            async for event in self.client.send_message(message):
                if isinstance(event, Message):
                    result = self._extract_message_text(event)
                    if result:
                        log.info("Received from %s: %d chars", self.agent_name, len(result))
                        yield ("result", result)
                        return
                    continue

                # ClientEvent: tuple[Task, update | None]
                task, update = event
                if isinstance(update, TaskStatusUpdateEvent):
                    if update.status.state == TaskState.TASK_STATE_INPUT_REQUIRED:
                        question = self._extract_status_message(update)
                        raise AgentInputRequired(
                            self.agent_name, question or "Additional input needed"
                        )
                    elif update.status.message:
                        status_msg = self._extract_status_message(update)
                        if status_msg:
                            yield ("status", status_msg)
                elif isinstance(update, TaskArtifactUpdateEvent):
                    if update.artifact:
                        artifact_text = self._extract_artifact_text(update.artifact)
                        if artifact_text:
                            latest_artifact_text = artifact_text
                elif update is None:
                    # Final task snapshot — extract artifacts
                    result = self._extract_task_text(task)
                    final_result = result or latest_artifact_text
                    if final_result:
                        log.info("Received from %s: %d chars", self.agent_name, len(final_result))
                        yield ("result", final_result)
                        return

            if latest_artifact_text:
                log.info("Received from %s: %d chars", self.agent_name, len(latest_artifact_text))
                yield ("result", latest_artifact_text)

    def _extract_message_text(self, message: Message) -> str:
        """Pull text from a direct Message response."""
        return extract_message_text(message)

    def _extract_status_message(self, event: TaskStatusUpdateEvent) -> str:
        """Pull text from a status update's message."""
        return extract_status_text(event)

    def _extract_task_text(self, task: Task) -> str:
        """Pull text from a completed task's artifacts or status."""
        return extract_task_text(task)

    def _extract_artifact_text(self, artifact: object) -> str:
        """Pull text from a task artifact."""
        if hasattr(artifact, "parts"):
            return extract_parts_text(artifact.parts)
        return ""

    def _extract_parts_text(self, parts: object) -> str:
        """Extract text/data payloads from A2A parts."""
        return extract_parts_text(parts)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self.client and hasattr(self.client, "close"):
            await self.client.close()  # type: ignore[attr-defined]
        await self.http.aclose()
