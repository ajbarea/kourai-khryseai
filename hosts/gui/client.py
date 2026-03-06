"""Async A2A client wrapper for the pygame GUI.

Runs in a background thread with its own asyncio event loop.
Communicates with the pygame main thread via two queues:
  send_q  — GUI → client: strings to send to Hephaestus
  recv_q  — client → GUI: event dicts to render
"""

from __future__ import annotations

import asyncio
import queue as _queue
import re
from uuid import uuid4

import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types import (
    Message,
    Part,
    Role,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
)

from kourai_common.config import get_agent_url

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


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

    def _put(self, event: dict) -> None:
        if "text" in event and isinstance(event["text"], str):
            event["text"] = _ANSI_RE.sub("", event["text"])
        self._recv.put_nowait(event)

    async def run(self) -> None:
        """Main async loop: connect, then process messages from send_q."""
        # --- Connect and announce ---
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                config = ClientConfig(streaming=True, httpx_client=http)
                client = await ClientFactory.connect(self._default_url, client_config=config)
                card = await client.get_card()
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

            try:
                target_url = get_agent_url(target_agent)
            except Exception:
                target_url = self._default_url

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
                client = await ClientFactory.connect(target_url, client_config=config)

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
        if event.status.message and hasattr(event.status.message, "parts"):
            parts = [p.root.text for p in event.status.message.parts if hasattr(p.root, "text")]
            return "\n".join(parts)
        return ""

    @staticmethod
    def _extract_artifact(event: TaskArtifactUpdateEvent) -> str:
        if event.artifact and event.artifact.parts:
            return "\n".join(p.root.text for p in event.artifact.parts if hasattr(p.root, "text"))
        return ""
