"""VN Bridge HTTP Server - runs in Docker, proxies Ren'Py to A2A agents.

Exposes five endpoints:
  GET  /health  - liveness + agent connectivity check
  POST /action  - synchronous actions (profiles, virtues, resume)
  POST /message - streaming NDJSON: user message or choice to agent stream
  POST /tts     - text-to-speech: {text, agent} → MP3 audio bytes
  POST /gossip  - live agent gossip: {agent, player_id, affinity} → {hint, line}
  GET  /*       - static web GUI bundle (Host B), served when KOURAI_WEB_DIR exists
"""

import contextlib
import io
import json
import logging
import os
import re
import sys
import wave
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.types import (
    Message,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
)
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from kourai_common.a2a_events import (
    extract_artifact_text,
    extract_message_text,
    extract_status_text,
)
from kourai_common.a2a_utils import make_a2a_http_client
from kourai_common.companion import infer_portrait_state
from kourai_common.config import get_agent_url
from kourai_common.facts import process_agent_output
from kourai_common.log import run_uvicorn
from kourai_common.messaging import (
    KIND_DIALOGUE,
    get_content_kind,
    send_request,
    stream_event,
    user_message,
)
from kourai_common.pipeline_status import PipelineTracker
from kourai_common.ssml import strip_ssml
from kourai_common.tts_cache import default_cache_dir
from kourai_common.tts_realtime import RealtimeTTSEngine

if TYPE_CHECKING:
    import httpx

PORT = 10010

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
    # research(2026-05): force=True wipes any handler installed by a
    # transitive import (RealtimeTTS / pydub / torch all attach to root
    # at import). Without it, basicConfig is a no-op and every logger
    # in the kourai_common tree silently drops messages.
    force=True,
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

# Short personality hints for gossip generation — keeps prompts small and fast.
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
    httpx_client = make_a2a_http_client(timeout=600)
    config = ClientConfig(streaming=True, httpx_client=httpx_client)
    try:
        resolver = A2ACardResolver(cast("httpx.AsyncClient", config.httpx_client), agent_url)
        card = await resolver.get_agent_card()
        for interface in card.supported_interfaces:
            interface.url = agent_url
        client = await create_client(card, client_config=config)
        log.info(f"Connected to {card.name} v{card.version}")
        app.state.a2a_client = client
    except Exception as e:
        log.error(f"Failed to connect to Hephaestus: {e}")
        app.state.a2a_client = None
    # research(2026-05): muted=True at construction is the documented
    # RealtimeTTS pattern for synth-only callers — runtime muted=True on
    # play() doesn't skip audio device opening, only construction-time
    # muted does (stream_player.AudioConfiguration.muted gate). vn_bridge
    # never calls speak(), so headless = correct.
    #
    # M6 sub-task 2: enable the TTS audio cache. Static dialogue dicts
    # (HANDOFF_LINES, VICTORY_LINES, AGENT_QUOTES, greetings) repeat
    # constantly across players — once warm, near-100% hit rate. Cache
    # lives at ${XDG_CACHE_HOME:-~/.cache}/kourai/tts and survives across
    # checkouts / make clean. Validating shape under Kokoro now; rides
    # along into the ElevenLabs swap (M6 sub-task 4).
    app.state.tts_engine = RealtimeTTSEngine(muted=True, cache_dir=default_cache_dir())
    app.state.context_id = uuid4().hex
    yield
    app.state.tts_engine.cleanup()
    await httpx_client.aclose()


async def handle_tts(request: Request) -> Response | JSONResponse:
    """Synthesize WAV bytes from text for Ren'Py's audio system.

    Response headers (M20 sub-task 2 VN surface — audio-led cps):
      - ``X-TTS-Duration-Seconds`` — total audio duration parsed from the
        WAV header (frames / framerate). Ren'Py uses this to compute a
        per-line ``{cps=N}`` value so the typewriter finishes when the
        voice finishes. Backwards-compatible: callers that ignore the
        header still get the same WAV body.

    The header is omitted when the WAV is malformed (defense — treat
    "no duration" the same as "duration unknown" rather than failing
    the synthesis call). Ren'Py defaults to its global cps in that case.
    """
    data: dict = await request.json()
    text = data.get("text", "").strip()
    agent = data.get("agent", "").lower().strip()
    if not text:
        return JSONResponse({"error": "Missing 'text' field"}, status_code=400)

    engine: RealtimeTTSEngine = request.app.state.tts_engine
    log.info(f"TTS ({agent}): {text[:60]}...")

    try:
        wav_bytes = await engine.synthesize_to_wav(text, agent_name=agent)
    except Exception as e:
        log.error(f"TTS synthesis failed: {e}", exc_info=True)
        return JSONResponse({"error": f"TTS failed: {e}"}, status_code=500)

    if not wav_bytes:
        return JSONResponse({"error": "TTS produced no audio"}, status_code=500)

    headers: dict[str, str] = {}
    duration = _wav_duration_seconds(wav_bytes)
    if duration is not None:
        headers["X-TTS-Duration-Seconds"] = f"{duration:.3f}"
        log.info(f"TTS ({agent}): duration={duration:.3f}s chars={len(text)}")

    return Response(wav_bytes, media_type="audio/wav", headers=headers)


def _wav_duration_seconds(wav_bytes: bytes) -> float | None:
    """Parse the WAV header to extract audio duration in seconds.

    Returns None on parse failure. We use Python's stdlib ``wave``
    module so the parsing is dependency-free and matches what Ren'Py's
    audio backend does internally.
    """
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            frames = wf.getnframes()
            framerate = wf.getframerate()
            if framerate <= 0:
                return None
            return frames / framerate
    except (wave.Error, EOFError, OSError):
        return None


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


def _project_json(p) -> dict:
    return {
        "project_id": p.project_id,
        "name": p.name,
        "template": p.template,
        "path": str(p.path),
        "created_at": p.created_at,
    }


def _session_json(s) -> dict:
    return {
        "session_id": s.session_id,
        "project_id": s.project_id,
        "branch": s.branch,
        "status": s.status,
        "started_at": s.started_at,
        "workdir": str(s.workdir),
    }


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

    if action == "affinities":
        from kourai_common.player import PlayerProfile
        from kourai_common.player_affinity import get_all_affinities

        prof = PlayerProfile.load()
        scores: dict = {}
        if prof:
            for agent_name, aff in get_all_affinities(prof.player_id).items():
                scores[agent_name] = aff.get("affinity_score", 0.0)
        return JSONResponse({"action": "affinities_result", "affinities": scores})

    if action == "get_virtue_context":
        from kourai_common.facts import get_relevant_facts_for_enrichment
        from kourai_common.player_affinity import get_all_affinities
        from kourai_common.virtues import get_all_virtues, get_virtue_deltas

        pid = data.get("player_id", "")
        return JSONResponse(
            {
                "action": "virtue_context_result",
                "virtues": get_all_virtues(pid) if pid else {},
                "deltas": get_virtue_deltas(pid) if pid else {},
                "affinities": get_all_affinities(pid) if pid else {},
                "facts": get_relevant_facts_for_enrichment(pid, limit=5) if pid else [],
            }
        )

    # ── Host B: projects + forge sessions (wrap existing managers) ──
    if action == "list_projects":
        from kourai_common.player import PlayerProfile
        from kourai_common.projects import ProjectManager

        profile = PlayerProfile.load()
        if profile is None:
            return JSONResponse(
                {"action": "projects_result", "projects": [], "error": "no_profile"}
            )
        projects = ProjectManager.list_for_player(profile.player_id)
        return JSONResponse(
            {"action": "projects_result", "projects": [_project_json(p) for p in projects]}
        )

    if action == "new_project":
        from kourai_common.player import PlayerProfile
        from kourai_common.projects import ProjectError, ProjectManager

        profile = PlayerProfile.load()
        if profile is None:
            return JSONResponse(
                {"action": "error", "message": "No active player profile."}, status_code=200
            )
        name = (data.get("name") or "").strip()
        template = (data.get("template") or "empty").strip() or "empty"
        if not name:
            return JSONResponse(
                {"action": "error", "message": "Project name required."}, status_code=200
            )
        try:
            project = ProjectManager.create(profile.player_id, name, template)
        except ProjectError as e:
            return JSONResponse({"action": "error", "message": str(e)}, status_code=200)
        return JSONResponse({"action": "project_created", "project": _project_json(project)})

    if action == "list_sessions":
        from kourai_common.forge_session import list_active_sessions

        project_id = (data.get("project_id") or "").strip()
        sessions = list_active_sessions(project_id) if project_id else []
        return JSONResponse(
            {"action": "sessions_result", "sessions": [_session_json(s) for s in sessions]}
        )

    if action in ("accept_session", "discard_session"):
        from kourai_common.forge_session import ForgeSessionError, get_session

        session_id = (data.get("session_id") or "").strip()
        session = get_session(session_id) if session_id else None
        if session is None:
            return JSONResponse(
                {"action": "error", "message": "Session not found."}, status_code=200
            )
        try:
            if action == "accept_session":
                session.accept()
                result = "accepted"
            else:
                session.discard()
                result = "discarded"
        except ForgeSessionError as e:
            return JSONResponse({"action": "error", "message": str(e)}, status_code=200)
        return JSONResponse({"action": "session_done", "session_id": session_id, "result": result})

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

    forge_metadata: dict = {}
    project_id = (data.get("project_id") or "").strip()
    if project_id:
        # Web GUI: start a forge worktree for the active project (the CLI host
        # does this per turn) and run the forge inside it.
        try:
            from kourai_common.forge_session import ForgeSession
            from kourai_common.projects import ProjectManager, derive_project_id

            project = ProjectManager.get(project_id)
            if project is not None:
                session = ForgeSession.start(project, label=(user_text or "forge")[:24])
                forge_metadata["project_root"] = str(session.workdir)
                forge_metadata["project_id"] = derive_project_id(project.path)
        except Exception as e:
            log.error(f"Forge session start failed: {e}")
    elif project_path:
        forge_metadata["project_root"] = project_path

    # Forward the affinity snapshot so Hephaestus can calibrate
    # relationship tiers without parsing prose.
    affinity_data: dict = data.get("affinity") or {}
    tiers = {k: float(v) for k, v in affinity_data.items() if isinstance(v, int | float)}
    if tiers:
        forge_metadata["relationship_tiers"] = tiers

    # Host B: forward the confirm-gate bypass flags when the web GUI sets them.
    if data.get("yolo"):
        forge_metadata["yolo"] = True
    if data.get("auto_approve_reads"):
        forge_metadata["auto_approve_reads"] = True

    # Resume turns: relay the real ask so the router doesn't re-route on "yes".
    original_request = (data.get("original_request") or "").strip()
    if original_request:
        forge_metadata["original_request"] = original_request

    if not user_text:

        async def empty() -> AsyncGenerator[str, None]:
            yield json.dumps({"agent": "system", "message": "Empty message received."}) + "\n"

        return StreamingResponse(empty(), media_type="application/x-ndjson")

    log.info(f"Message ({action}, ctx={context_id[:8]}): {user_text[:80]}")
    req_task_id = (data.get("task_id") or "").strip() or None
    message = user_message(
        user_text,
        context_id=context_id,
        task_id=req_task_id,
        metadata=forge_metadata or None,
    )

    async def stream_response() -> AsyncGenerator[str, None]:
        tracker = PipelineTracker(initial_agent="hephaestus")
        found_artifact = False
        final_state = None
        last_task_id = ""
        input_prompt = ""
        try:
            async for response in client.send_message(send_request(message)):
                event = stream_event(response)
                if isinstance(event, Message):
                    text = extract_message_text(event)
                    if text:
                        portrait_state = infer_portrait_state(tracker.current_agent, text)
                        for beat in _paginate(text):
                            yield (
                                json.dumps(
                                    {
                                        "agent": tracker.current_agent,
                                        "message": beat,
                                        "portrait": portrait_state,
                                    }
                                )
                                + "\n"
                            )
                        found_artifact = True
                    continue
                if isinstance(event, TaskStatusUpdateEvent):
                    final_state = event.status.state
                    if event.task_id:
                        last_task_id = event.task_id
                    status_msg = extract_status_text(event)
                    if not status_msg:
                        continue
                    if final_state == TaskState.TASK_STATE_INPUT_REQUIRED:
                        input_prompt = status_msg
                    # Strict M18 routing: only KIND_DIALOGUE goes to the
                    # VN dialogue layer.
                    kind = get_content_kind(event.status.message)
                    is_dialogue = kind == KIND_DIALOGUE
                    # Handoff only on genuine routing status, never on dialogue: an
                    # agent naming another maiden in its own speech (e.g. Hephaestus
                    # introducing the pipeline) must not reassign the speaker.
                    if not is_dialogue:
                        lower = status_msg.lower()
                        for name in AGENT_NAMES:
                            if name in lower:
                                tracker.handoff(name)
                                break
                    log.info(f"Status ({tracker.current_agent}): {status_msg[:100]}")

                    if is_dialogue:
                        # Defensive strip before yielding to Ren'Py — no
                        # producer currently emits SSML (see
                        # kourai_common.ssml docstring), but any future
                        # LLM-emitted markup would render literally in
                        # Ren'Py's dialogue layer without this guard.
                        display_msg = strip_ssml(status_msg)[:200]
                        yield (
                            json.dumps(
                                {
                                    "agent": "hephaestus",
                                    "message": display_msg,
                                    "portrait": "neutral",
                                }
                            )
                            + "\n"
                        )
                    else:
                        yield (json.dumps({"action": "status", "message": status_msg[:120]}) + "\n")
                elif isinstance(event, TaskArtifactUpdateEvent):
                    if event.task_id:
                        last_task_id = event.task_id
                    if event.artifact and event.artifact.parts:
                        # Extract jealousy_trigger from DataPart before processing text.
                        for p in event.artifact.parts:
                            part_data = p.data if p.HasField("data") else None
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
                        text = extract_artifact_text(event)
                        if text:
                            log.info(f"Artifact ({tracker.current_agent}): {text[:80]}")
                            text = process_agent_output(
                                text, current_player_id, source_agent=tracker.current_agent
                            )
                            portrait_state = infer_portrait_state(tracker.current_agent, text)
                            for beat in _paginate(text):
                                yield (
                                    json.dumps(
                                        {
                                            "agent": tracker.current_agent,
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
        if final_state == TaskState.TASK_STATE_INPUT_REQUIRED:
            prompt = strip_ssml(input_prompt or "Hephaestus needs your confirmation.")[:400]
            payload: dict = {"action": "input_required", "prompt": prompt}
            if last_task_id:
                payload["task_id"] = last_task_id
            root = forge_metadata.get("project_root")
            if root:
                payload["project_root"] = root
            yield json.dumps(payload) + "\n"
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


def _cors_origins() -> list[str]:
    """Dev CORS allow-list. Same-origin (served by the gateway) needs none;
    this only matters when the SPA runs from a separate dev server."""
    raw = os.environ.get("KOURAI_WEB_ORIGINS", "")
    if raw.strip():
        return [o.strip() for o in raw.split(",") if o.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


def _build_routes() -> list:
    routes: list = [
        Route("/health", health),
        Route("/action", handle_action, methods=["POST"]),
        Route("/message", handle_message, methods=["POST"]),
        Route("/tts", handle_tts, methods=["POST"]),
        Route("/gossip", handle_gossip, methods=["POST"]),
    ]
    # Host B: serve the web GUI bundle same-origin. Mounted LAST so the API
    # routes above always take precedence. Skipped when the dir is absent
    # (e.g. a VN-only deploy), so this never affects the Ren'Py path.
    repo_root = Path(__file__).resolve().parents[2]
    # Agent portraits — single source of truth is docs/assets/avatars. Mounted
    # before the "/" catch-all so /avatars/<id>_neutral.png resolves first.
    avatars_dir = Path(
        os.environ.get("KOURAI_AVATARS_DIR") or (repo_root / "docs" / "assets" / "avatars")
    )
    if avatars_dir.is_dir():
        routes.append(Mount("/avatars", app=StaticFiles(directory=str(avatars_dir))))
        log.info(f"Serving avatars from {avatars_dir}")
    web_dir = Path(os.environ.get("KOURAI_WEB_DIR") or (repo_root / "web"))
    if web_dir.is_dir():
        routes.append(Mount("/", app=StaticFiles(directory=str(web_dir), html=True)))
        log.info(f"Serving web GUI from {web_dir}")
    else:
        log.info(f"Web GUI dir not found at {web_dir}; static serving disabled")
    return routes


app = Starlette(
    routes=_build_routes(),
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=_cors_origins(),
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        ),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    run_uvicorn(app, host="0.0.0.0", port=PORT)  # noqa: S104
