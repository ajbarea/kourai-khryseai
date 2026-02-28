"""A2A client connections to specialist agents."""

from __future__ import annotations

import logging
import uuid

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    Message,
    MessageSendParams,
    Part,
    SendMessageRequest,
    TextPart,
)

from kourai_common.retry import with_retry
from kourai_common.tracing import create_span, get_trace_context

log = logging.getLogger(__name__)


class RemoteAgentConnection:
    """Wraps an A2A client connection to a single specialist agent."""

    def __init__(self, agent_name: str, agent_url: str):
        self.agent_name = agent_name
        self.agent_url = agent_url
        self.http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0),
        )
        self.client: A2AClient | None = None
        self.card = None

    async def connect(self) -> None:
        """Fetch agent card and initialize A2A client."""
        with create_span(f"a2a.connect.{self.agent_name}", {"url": self.agent_url}):
            resolver = A2ACardResolver(base_url=self.agent_url, httpx_client=self.http)
            self.card = await resolver.get_agent_card()
            self.client = A2AClient(httpx_client=self.http, agent_card=self.card)
            log.info("Connected to %s at %s", self.card.name, self.agent_url)

    @with_retry(max_attempts=3, base_delay=1.0)
    async def send(self, text: str, context_id: str) -> str:
        """Send a message to the specialist and return the artifact text.

        Args:
            text: The message/task content to send.
            context_id: Conversation context ID for multi-turn.

        Returns:
            Extracted text from the agent's response artifacts.
        """
        if not self.client:
            raise RuntimeError(f"Not connected to {self.agent_name}. Call connect() first.")

        with create_span(
            f"a2a.send.{self.agent_name}",
            {"target_agent": self.agent_name, "context_id": context_id},
        ):
            message_id = str(uuid.uuid4())
            request = SendMessageRequest(
                id=message_id,
                params=MessageSendParams(
                    message=Message(
                        role="user",
                        parts=[Part(root=TextPart(text=text))],
                        messageId=message_id,
                        contextId=context_id,
                        metadata=get_trace_context(),
                    ),
                    configuration={"blocking": True},
                ),
            )
            log.info("Sending to %s: %d chars", self.agent_name, len(text))
            response = await self.client.send_message(message_request=request)
            result = self._extract_text(response)
            log.info("Received from %s: %d chars", self.agent_name, len(result))
            return result

    def _extract_text(self, response) -> str:
        """Pull text content from an A2A response."""
        try:
            result = response.root.result
            if hasattr(result, "artifacts") and result.artifacts:
                return "\n".join(
                    part.root.text
                    for artifact in result.artifacts
                    for part in artifact.parts
                    if hasattr(part.root, "text")
                )
            if hasattr(result, "status") and result.status.message:
                msg = result.status.message
                if hasattr(msg, "parts"):
                    return "\n".join(
                        p.root.text for p in msg.parts if hasattr(p.root, "text")
                    )
                return str(msg)
        except AttributeError:
            pass
        return str(response)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.http.aclose()
