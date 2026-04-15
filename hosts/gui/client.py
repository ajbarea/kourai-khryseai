"""Async A2A client wrapper for the pygame GUI.

Runs in a background thread with its own asyncio event loop.
Communicates with the pygame main thread via two queues:
  send_q  — GUI → client: strings to send to Hephaestus
  recv_q  — client → GUI: event dicts to render
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import (
    Message,
    Part,
    Role,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
)

from kourai_common.a2a_events import (
    extract_artifact_text,
    extract_status_text,
)
from kourai_common.config import AGENT_PORTS, get_agent_url

if TYPE_CHECKING:
    import queue as _queue

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
logger = logging.getLogger(__name__)


class GuiClient:
    """Bridges the async A2A pipeline to the pygame event queue."""

    def __init__(
        self,
        send_q: _queue.Queue[tuple[str, str] | None],
        recv_q: _queue.Queue[dict],
        agent_url: str | None = None,
    ) -> None:
        self._send = send_q
        self._recv = recv_q
        self._default_url = agent_url or get_agent_url("hephaestus")

    def _resolve_target_url(self, target_agent: str) -> str:
        """Resolve host-reachable URL for the selected target agent."""
        port = AGENT_PORTS.get(target_agent)
        if port is None:
            return self._default_url

        try:
            # Keep the same host as Hephaestus (localhost, remote host, or Docker DNS)
            # and only swap to the selected agent's port.
            return str(httpx.URL(self._default_url).copy_with(port=port))
        except Exception:
            logger.warning(
                "Failed to resolve target URL from default_url=%s for agent=%s; "
                "falling back to config resolver.",
                self._default_url,
                target_agent,
            )
            try:
                return get_agent_url(target_agent)
            except Exception:
                return self._default_url

    def _put(self, event: dict) -> None:
        if "text" in event and isinstance(event["text"], str):
            event["text"] = _ANSI_RE.sub("", event["text"])
        self._recv.put_nowait(event)

    async def run(self) -> None:
        """Main async loop: connect, then process messages from send_q."""
        # --- Connect and announce ---
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                resolver = A2ACardResolver(http, self._default_url)
                card = await resolver.get_agent_card()
                # Override card URL — the agent may advertise a Docker-internal
                # hostname that the host machine cannot reach.
                card.url = self._default_url
                self._put({"type": "connected", "name": card.name, "url": self._default_url})
        except Exception as e:
            self._put({"type": "error", "text": f"Cannot reach Hephaestus: {e}"})
            return

        # --- Message loop ---
        context_id = uuid4().hex
        loop = asyncio.get_running_loop()

        while True:
            # Block until a message arrives (run_in_executor so we don't block the loop)
            item = await loop.run_in_executor(None, self._send.get)
            if item is None:
                # Sentinel: shutdown signal
                self._put({"type": "disconnected"})
                break

            target_agent, text = item

            target_url = self._resolve_target_url(target_agent)
            logger.debug("Routing GUI request to agent=%s via %s", target_agent, target_url)

            await self._send_message(target_url, text, context_id)

    async def _send_message(self, target_url: str, user_text: str, context_id: str) -> None:
        import time

        message = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=user_text))],
            message_id=str(uuid4()),
        )
        message.context_id = context_id  # type: ignore[attr-defined]

        t0 = time.monotonic()
        final_text = ""

        try:
            async with httpx.AsyncClient(timeout=300.0) as http:
                config = ClientConfig(streaming=True, httpx_client=http)
                # Fetch card and override URL so Docker-internal hostnames
                # are replaced with the reachable target_url.
                resolver = A2ACardResolver(http, target_url)
                card = await resolver.get_agent_card()
                card.url = target_url
                client = await ClientFactory.connect(card, client_config=config)

                async for event in client.send_message(message):
                    if isinstance(event, Message):
                        for p in event.parts:
                            if hasattr(p.root, "text"):
                                self._put({"type": "status", "text": p.root.text})
                        continue

                    task, update = event

                    if isinstance(update, TaskStatusUpdateEvent):
                        text = self._extract_status(update)
                        if text:
                            self._put({"type": "status", "text": text})
                        if update.status.state == TaskState.failed:
                            self._put({"type": "error", "text": "Pipeline failed"})

                    elif isinstance(update, TaskArtifactUpdateEvent):
                        text = self._extract_artifact(update)
                        if text:
                            final_text = text

                    elif update is None:
                        pass  # final task snapshot — state already tracked

        except httpx.ConnectError:
            self._put({"type": "error", "text": "Lost forge connection — is 'make up' running?"})
            return
        except httpx.TimeoutException:
            self._put({"type": "error", "text": "Request timed out — forge is running hot."})
            return
        except Exception as e:
            self._put({"type": "error", "text": str(e)})
            return

        elapsed = time.monotonic() - t0

        if final_text:
            self._put({"type": "result", "text": final_text})

        self._put({"type": "complete", "elapsed": elapsed})

    @staticmethod
    def _extract_status(event: TaskStatusUpdateEvent) -> str:
        return extract_status_text(event)

    @staticmethod
    def _extract_artifact(event: TaskArtifactUpdateEvent) -> str:
        return extract_artifact_text(event)
