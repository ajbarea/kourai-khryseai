"""VN Bridge HTTP Server - runs in Docker, proxies Ren'Py to A2A agents.

Exposes five endpoints:
  GET  /health  - liveness + agent connectivity check
  POST /action  - synchronous actions (profiles, virtues, resume)
  POST /message - streaming NDJSON: user message or choice to agent stream
  POST /tts     - text-to-speech: {text, agent} → MP3 audio bytes
  POST /gossip  - live agent gossip: {agent, player_id, affinity} → {hint, line}
"""

import contextlib
import io
import json
import logging
import re
import sys
from collections.abc import AsyncGenerator
from typing import cast
from uuid import uuid4

import edge_tts
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

from kourai_common.companion import infer_portrait_state
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

# Agent → edge-tts voice config. Source of truth: designs/TTS_ARCHITECTURE.md
VOICE_MAP: dict[str, dict] = {
    "hephaestus": {"voice": "en-US-GuyNeural", "rate": "-5%", "pitch": "+0Hz"},
    "metis": {"voice": "en-US-AriaNeural", "rate": "-10%", "pitch": "+10%"},
    "kallos": {"voice": "en-US-JennyNeural", "rate": "+5%", "pitch": "+15%"},
    "mneme": {"voice": "en-US-MichelleNeural", "rate": "-8%", "pitch": "-5%"},
    "techne": {"voice": "en-GB-SoniaNeural", "rate": "-7%", "pitch": "+5%"},
    "dokimasia": {"voice": "en-US-AriaNeural", "rate": "-12%", "pitch": "+0Hz"},
    "puck": {"voice": "en-US-AndrewNeural", "rate": "+5%", "pitch": "+0Hz"},
    "cupid": {"voice": "en-US-AmberNeural", "rate": "-5%", "pitch": "+10%"},
    "aidos": {"voice": "en-US-JaneNeural", "rate": "-10%", "pitch": "-5%"},
    "aletheia": {"voice": "en-US-NancyNeural", "rate": "-7%", "pitch": "+0Hz"},
}
_DEFAULT_VOICE = {"voice": "en-US-AriaNeural", "rate": "+0%", "pitch": "+0Hz"}

# Short personality hints for gossip generation — keeps prompts small and fast.
# Source of truth: designs/CHARACTER_DESIGN.md
GOSSIP_HINTS: dict[str, str] = {
    "hephaestus": "Gruff forge-master. Laconic. Shows approval through craft metaphors.",
    "techne": "Precise British coder. Dry wit. Notices technical habits. Tsundere about caring.",
    "kallos": "Elegant stylist. Opinionated about aesthetics. Notices effort in presentation.",
    "metis": "Strategic architect. Speaks in systems. Sees patterns others miss.",
    "dokimasia": "Stern tester. Counts everything. Quietly satisfied by thoroughness.",
    "mneme": "Gentle scribe. Poetic. Remembers everything. Finds meaning in repetition.",
    "puck": "Sarcastic companion spirit. Conspiratorial. Calls the player 'boss'.",
    "cupid": "Romantic idealist. Reads emotional subtext. Warm and perceptive.",
    "aidos": "Spirit of shame. Terse. Notices when people are being vague or dishonest.",
    "aletheia": "Truth-seeker. Factual. Values evidence over opinion.",
}


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
        resolver = A2ACardResolver(cast("httpx.AsyncClient", config.httpx_client), agent_url)
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


async def handle_tts(request: Request) -> StreamingResponse | JSONResponse:
    """Generate MP3 audio from text using edge-tts with per-agent voice settings."""
    data: dict = await request.json()
    text = data.get("text", "").strip()
    agent = data.get("agent", "").lower().strip()
    if not text:
        return JSONResponse({"error": "Missing 'text' field"}, status_code=400)

    voice_cfg = VOICE_MAP.get(agent, _DEFAULT_VOICE)
    log.info(f"TTS ({agent}): {text[:60]}... → {voice_cfg['voice']}")
    try:
        communicate = edge_tts.Communicate(
            text,
            voice=voice_cfg["voice"],
            rate=voice_cfg["rate"],
            pitch=voice_cfg["pitch"],
        )
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        buf.seek(0)
        return StreamingResponse(buf, media_type="audio/mpeg")
    except Exception as e:
        log.error(f"TTS generation failed: {e}", exc_info=True)
        return JSONResponse({"error": f"TTS failed: {e}"}, status_code=500)


async def handle_gossip(request: Request) -> JSONResponse:
    """Generate a live gossip line from an idle agent about the player.

    Uses kourai_common.llm.chat() directly (not A2A) for speed — gossip
    is flavor text that shouldn't go through the full orchestrator pipeline.
    """
    from kourai_common.facts import get_relevant_facts_for_enrichment
    from kourai_common.llm import chat

    data: dict = await request.json()
    agent = data.get("agent", "").lower().strip()
    player_id = data.get("player_id", "").strip()
    affinity_data: dict = data.get("affinity") or {}

    if agent not in AGENT_NAMES:
        return JSONResponse({"error": f"Unknown agent: {agent}"}, status_code=400)

    hint_text = GOSSIP_HINTS.get(agent, "An AI agent.")
    agent_affinity = affinity_data.get(agent, 0.5)

    # Gather player facts for personalization
    fact_lines = ""
    if player_id:
        facts = get_relevant_facts_for_enrichment(player_id, agent_name=agent, limit=3)
        if facts:
            fact_lines = "\n".join(f"- {f.get('content', '')}" for f in facts)
            fact_lines = f"\nWhat you know about the player:\n{fact_lines}"

    prompt = (
        f"You are {agent.capitalize()}, observing the player from the sidelines.\n"
        f"Personality: {hint_text}\n"
        f"Your affinity with the player: {agent_affinity:.2f} (0=cold, 1=intimate).{fact_lines}\n\n"
        f"Generate exactly ONE idle observation about the player. Stay in character.\n"
        f'Respond with ONLY valid JSON: {{"hint": "*stage direction*", "line": "Your observation."}}'
    )

    result = ""
    try:
        result = await chat(
            agent,
            [{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=100,
        )
        # Parse the JSON response — strip markdown fences if the LLM wraps it
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        parsed = json.loads(cleaned)
        hint = parsed.get("hint", "*observing*")
        line = parsed.get("line", "")
        if not line:
            return JSONResponse({"error": "Empty gossip"}, status_code=500)
        log.info(f"Gossip ({agent}): {hint} {line[:60]}")
        return JSONResponse({"hint": hint, "line": line})
    except (json.JSONDecodeError, KeyError) as e:
        log.warning(f"Gossip parse error ({agent}): {e} — raw: {result[:100]}")
        return JSONResponse({"error": "Gossip generation failed"}, status_code=500)
    except Exception as e:
        log.error(f"Gossip LLM error ({agent}): {e}", exc_info=True)
        return JSONResponse({"error": f"Gossip failed: {e}"}, status_code=500)


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
    project_path = data.get("project_path", "").strip()

    # Both "message" and "choice" resolve to a user text turn
    user_text = data.get("choice", "") if action == "choice" else data.get("text", "")

    if project_path:
        user_text = f"[project_root: {project_path}]\n{user_text}"

    # Inject affinity snapshot so Hephaestus can calibrate relationship tier context.
    affinity_data: dict = data.get("affinity") or {}
    if affinity_data:
        tiers_str = ",".join(
            f"{k}={v:.2f}" for k, v in affinity_data.items() if isinstance(v, int | float)
        )
        if tiers_str:
            user_text = f"[relationship_tiers: {tiers_str}]\n{user_text}"
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
                        portrait_state = infer_portrait_state(current_agent, text)
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
                            # Extract jealousy_trigger from DataPart before processing text.
                            for p in update.artifact.parts:
                                part_data = getattr(p.root, "data", None)
                                if isinstance(part_data, dict):
                                    jealousy = part_data.get("jealousy_trigger")
                                    if jealousy and isinstance(jealousy, dict):
                                        yield (
                                            json.dumps(
                                                {
                                                    "action": "jealousy",
                                                    "agent": jealousy.get("agent", ""),
                                                    "score": jealousy.get("score", 0.0),
                                                }
                                            )
                                            + "\n"
                                        )
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
                                portrait_state = infer_portrait_state(current_agent, text)
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
        Route("/tts", handle_tts, methods=["POST"]),
        Route("/gossip", handle_gossip, methods=["POST"]),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")  # noqa: S104
