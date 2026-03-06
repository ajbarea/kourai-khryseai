"""A2A client connections to specialist agents."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.client.client import Client
from a2a.types import (
    AgentCard,
    FilePart,
    FileWithBytes,
    Message,
    Part,
    Role,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
)

from kourai_common.tracing import create_span, get_trace_context

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
        self.http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0),
        )
        self.client: Client | None = None
        self.card: AgentCard | None = None

    async def connect(self) -> None:
        """Fetch agent card and initialize A2A client."""
        with create_span(f"a2a.connect.{self.agent_name}", {"url": self.agent_url}):
            resolver = A2ACardResolver(self.http, self.agent_url)
            self.card = await resolver.get_agent_card()
            if self.card:
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
    ) -> AsyncGenerator[tuple[str, str], None]:
        """Send a message to the specialist and yield status and result updates.

        Args:
            text: The message/task content to send.
            context_id: Conversation context ID for multi-turn.
            attachments: Optional list of (base64_bytes, mime_type) image attachments.

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
            if attachments:
                parts: list[Part] = [Part(TextPart(text=text))]
                for b64_data, mime_type in attachments:
                    parts.append(
                        Part(
                            FilePart(
                                file=FileWithBytes(
                                    bytes=b64_data, mime_type=mime_type, name="attachment.png"
                                )
                            )
                        )
                    )
                message = Message(
                    role=Role.user,
                    parts=parts,
                    message_id=str(uuid4()),
                )
            else:
                from a2a.client.helpers import create_text_message_object

                message = create_text_message_object(content=text)
            message.context_id = context_id
            message.metadata = get_trace_context()

            log.info("Sending to %s: %d chars", self.agent_name, len(text))

            async for event in self.client.send_message(message):
                if isinstance(event, Message):
                    result = self._extract_message_text(event)
                    log.info("Received from %s: %d chars", self.agent_name, len(result))
                    yield ("result", result)
                    return

                # ClientEvent: tuple[Task, update | None]
                task, update = event
                if isinstance(update, TaskStatusUpdateEvent):
                    if update.status.state == TaskState.input_required:
                        question = self._extract_status_message(update)
                        raise AgentInputRequired(
                            self.agent_name, question or "Additional input needed"
                        )
                    elif update.status.message:
                        status_msg = self._extract_status_message(update)
                        if status_msg:
                            yield ("status", status_msg)
                elif isinstance(update, TaskArtifactUpdateEvent):
                    if update.artifact and update.artifact.parts:
                        result = "\n".join(
                            p.root.text for p in update.artifact.parts if hasattr(p.root, "text")
                        )
                        log.info("Received from %s: %d chars", self.agent_name, len(result))
                        yield ("result", result)
                        return
                elif update is None:
                    # Final task snapshot — extract artifacts
                    result = self._extract_task_text(task)
                    if result:
                        log.info("Received from %s: %d chars", self.agent_name, len(result))
                        yield ("result", result)
                        return

    def _extract_message_text(self, message: Message) -> str:
        """Pull text from a direct Message response."""
        return "\n".join(p.root.text for p in message.parts if hasattr(p.root, "text"))

    def _extract_status_message(self, event: TaskStatusUpdateEvent) -> str:
        """Pull text from a status update's message."""
        if event.status.message and hasattr(event.status.message, "parts"):
            return "\n".join(
                p.root.text for p in event.status.message.parts if hasattr(p.root, "text")
            )
        return ""

    def _extract_task_text(self, task: Task) -> str:
        """Pull text from a completed task's artifacts or status."""
        if task.artifacts:
            return "\n".join(
                p.root.text
                for artifact in task.artifacts
                for p in artifact.parts
                if hasattr(p.root, "text")
            )
        if task.status.message and hasattr(task.status.message, "parts"):
            return "\n".join(
                p.root.text for p in task.status.message.parts if hasattr(p.root, "text")
            )
        return ""

    async def close(self) -> None:
        """Close the HTTP client."""
        if self.client and hasattr(self.client, "close"):
            await self.client.close()  # type: ignore[attr-defined]
        await self.http.aclose()
