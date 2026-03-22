"""VN Bridge HTTP Server - runs in Docker, proxies Ren'Py to A2A agents.

Exposes three endpoints:
  GET  /health  - liveness + agent connectivity check
  POST /action  - synchronous actions (profiles, virtues, resume)
  POST /message - streaming NDJSON: user message or choice to agent stream
"""

import contextlib
import json
import logging
import re
import sys
from collections.abc import AsyncGenerator
from typing import cast
from uuid import uuid4

import httpx
import uvicorn
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import (
    Message,
    Part,
    Role,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
    TextPart,
)
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from kourai_common.config import get_agent_url
from kourai_common.facts import process_agent_output

PORT = 10010

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("vn_bridge")

AGENT_NAMES = {
    "hephaestus",
    "techne",
    "kallos",
    "metis",
    "dokimasia",
    "mneme",
    "puck",
    "cupid",
    "aidos",
    "aletheia",
}

# Status keywords promoted to dialogue beats vs. silent HUD updates
DIALOGUE_KEYWORDS = ["pipeline:", "dispatching", "complete", "failed", "error"]


def _infer_portrait_state(agent: str, text: str) -> str:
    """Infer portrait emotional state from text content."""
    lower = text.lower()
    vulnerable_signals = [
        "i'm glad",
        "i care",
        "i appreciate",
        "thank you",
        "means a lot",
        "i worry",
        "proud of you",
        "you did well",
        "nicely done",
        "well done",
        "good work",
        "i noticed",
        "honest with you",
        "vulnerable",
    ]
    if any(sig in lower for sig in vulnerable_signals):
        return "vulnerable"
    tertiary: dict[str, tuple[list[str], str]] = {
        "hephaestus": (["approved", "well done", "as expected", "good"], "approving"),
        "techne": (["analyzing", "let me check", "running", "executing", "compiling"], "focused"),
        "kallos": (
            ["style violation", "messy", "inconsistent", "beautiful", "elegant", "clean"],
            "appraising",
        ),
        "metis": (
            ["consider", "the architecture", "planning", "structure", "design"],
            "contemplating",
        ),
        "dokimasia": (
            ["test", "assertion", "coverage", "failure", "passing", "green"],
            "scrutinizing",
        ),
        "mneme": (
            ["remember", "recorded", "stored", "history", "last time", "recall"],
            "remembering",
        ),
    }
    signals, state = tertiary.get(agent, ([], "neutral"))
    if any(sig in lower for sig in signals):
        return state
    return "neutral"


def _paginate(text: str) -> list[str]:
    """Split text into sentence-level dialogue beats."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


@contextlib.asynccontextmanager
async def lifespan(app: Starlette) -> AsyncGenerator[None, None]:
    agent_url = get_agent_url("hephaestus")
    log.info(f"Connecting to Hephaestus at {agent_url}")
    httpx_client = httpx.AsyncClient(timeout=600)
    config = ClientConfig(streaming=True, httpx_client=httpx_client)
    try:
        resolver = A2ACardResolver(cast(httpx.AsyncClient, config.httpx_client), agent_url)
        card = await resolver.get_agent_card()
        card.url = agent_url
        client = await ClientFactory.connect(card, client_config=config)
        log.info(f"Connected to {card.name} v{card.version}")
        app.state.a2a_client = client
    except Exception as e:
        log.error(f"Failed to connect to Hephaestus: {e}")
        app.state.a2a_client = None
    app.state.context_id = uuid4().hex
    yield
    await httpx_client.aclose()


async def health(request: Request) -> JSONResponse:
    ok = request.app.state.a2a_client is not None
    return JSONResponse(
        {"status": "ok" if ok else "disconnected"},
        status_code=200 if ok else 503,
    )


async def handle_action(request: Request) -> JSONResponse:
    data: dict = await request.json()
    action = data.get("action", "")
    log.info(f"Action: {action}")

    if action == "resume":
        ctx = data.get("context_id", "").strip()
        if ctx:
            request.app.state.context_id = ctx
        return JSONResponse(
            {"action": "status", "message": "The forge rekindles. Context restored."}
        )

    if action == "get_profiles":
        from kourai_common.player import list_profiles

        return JSONResponse({"action": "profiles_result", "profiles": list_profiles()})

    if action == "create_profile":
        from kourai_common.player import PlayerProfile, set_active_profile

        p = PlayerProfile()
        p.display_name = data.get("display_name", "")
        p.tts_name = data.get("tts_name", "")
        p.title = data.get("title", "")
        p.role = data.get("role", "mortal")
        p.pronouns = data.get("pronouns", "")
        p.save()
        set_active_profile(p.player_id)
        return JSONResponse({"action": "create_profile_result", "player_id": p.player_id})

    if action == "set_active_profile":
        from kourai_common.player import set_active_profile

        pid = data.get("player_id", "")
        if pid:
            set_active_profile(pid)
        return JSONResponse({"action": "ok"})

    if action == "get_virtue_context":
        from kourai_common.facts import get_relevant_facts_for_enrichment
        from kourai_common.virtues import get_all_virtues, get_virtue_deltas

        pid = data.get("player_id", "")
        return JSONResponse(
            {
                "action": "virtue_context_result",
                "virtues": get_all_virtues(pid) if pid else {},
                "deltas": get_virtue_deltas(pid) if pid else {},
                "facts": get_relevant_facts_for_enrichment(pid, limit=5) if pid else [],
            }
        )

    return JSONResponse({"error": f"Unknown action: {action}"}, status_code=400)


async def handle_message(request: Request) -> StreamingResponse:
    client = request.app.state.a2a_client
    if client is None:

        async def not_connected() -> AsyncGenerator[str, None]:
            yield (
                json.dumps({"agent": "system", "message": "Bridge not connected to agents."}) + "\n"
            )

        return StreamingResponse(not_connected(), media_type="application/x-ndjson")

    data: dict = await request.json()
    action = data.get("action", "message")
    req_context = data.get("context_id", "").strip()
    if req_context:
        request.app.state.context_id = req_context
    context_id = request.app.state.context_id
    current_player_id = data.get("player_id", "").strip()

    # Both "message" and "choice" resolve to a user text turn
    user_text = data.get("choice", "") if action == "choice" else data.get("text", "")
    if not user_text:

        async def empty() -> AsyncGenerator[str, None]:
            yield json.dumps({"agent": "system", "message": "Empty message received."}) + "\n"

        return StreamingResponse(empty(), media_type="application/x-ndjson")

    log.info(f"Message ({action}, ctx={context_id[:8]}): {user_text[:80]}")
    message = Message(
        role=Role.user,
        parts=[Part(root=TextPart(text=user_text))],
        message_id=str(uuid4()),
    )
    message.context_id = context_id

    async def stream_response() -> AsyncGenerator[str, None]:
        current_agent = "hephaestus"
        found_artifact = False
        try:
            async for event in client.send_message(message):
                if isinstance(event, Message):
                    text = "\n".join(p.root.text for p in event.parts if hasattr(p.root, "text"))
                    if text:
                        portrait_state = _infer_portrait_state(current_agent, text)
                        for beat in _paginate(text):
                            yield (
                                json.dumps(
                                    {
                                        "agent": current_agent,
                                        "message": beat,
                                        "portrait": portrait_state,
                                    }
                                )
                                + "\n"
                            )
                        found_artifact = True
                    continue
                if isinstance(event, tuple):
                    task, update = event
                    if isinstance(update, TaskStatusUpdateEvent):
                        status_msg = ""
                        if update.status.message and hasattr(update.status.message, "parts"):
                            status_msg = "\n".join(
                                p.root.text
                                for p in update.status.message.parts
                                if hasattr(p.root, "text")
                            )
                        if not status_msg:
                            continue
                        lower = status_msg.lower()
                        for name in AGENT_NAMES:
                            if name in lower:
                                current_agent = name
                                break
                        log.info(f"Status ({current_agent}): {status_msg[:100]}")
                        if any(kw in lower for kw in DIALOGUE_KEYWORDS):
                            yield (
                                json.dumps(
                                    {
                                        "agent": "hephaestus",
                                        "message": status_msg[:200],
                                        "portrait": "neutral",
                                    }
                                )
                                + "\n"
                            )
                        else:
                            yield (
                                json.dumps({"action": "status", "message": status_msg[:120]}) + "\n"
                            )
                    elif isinstance(update, TaskArtifactUpdateEvent):
                        if update.artifact and update.artifact.parts:
                            text = "\n".join(
                                p.root.text
                                for p in update.artifact.parts
                                if hasattr(p.root, "text")
                            )
                            if text:
                                log.info(f"Artifact ({current_agent}): {text[:80]}")
                                text = process_agent_output(
                                    text, current_player_id, source_agent=current_agent
                                )
                                portrait_state = _infer_portrait_state(current_agent, text)
                                for beat in _paginate(text):
                                    yield (
                                        json.dumps(
                                            {
                                                "agent": current_agent,
                                                "message": beat,
                                                "portrait": portrait_state,
                                            }
                                        )
                                        + "\n"
                                    )
                                found_artifact = True
        except Exception as e:
            log.error(f"Stream error: {e}", exc_info=True)
            yield json.dumps({"agent": "system", "message": f"Processing error: {e}"}) + "\n"
            return
        if not found_artifact:
            log.warning("Pipeline finished without artifact.")
            yield (
                json.dumps(
                    {
                        "agent": "system",
                        "message": "The pipeline completed but no response was generated.",
                    }
                )
                + "\n"
            )

    return StreamingResponse(stream_response(), media_type="application/x-ndjson")


app = Starlette(
    routes=[
        Route("/health", health),
        Route("/action", handle_action, methods=["POST"]),
        Route("/message", handle_message, methods=["POST"]),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")  # noqa: S104
