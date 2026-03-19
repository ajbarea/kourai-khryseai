"""VN Bridge Entry Point — translates between stdin/stdout JSON and A2A agents.

This allows the Ren'Py VN Host to talk to the agent swarm without
needing to manage HTTP connections or ports directly.
"""

import asyncio
import json
import logging
import re
import sys
from pathlib import Path
from typing import cast
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TaskArtifactUpdateEvent, TaskStatusUpdateEvent, TextPart

from kourai_common.config import get_agent_url
from kourai_common.facts import process_agent_output

# Configure logging to both stderr and a file
PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "bridge_agents.log"

# Agent names for attribution tracking
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

# Status keywords that are meaningful enough to surface as dialogue beats
# (rather than silently updating the "thinking" overlay)
DIALOGUE_KEYWORDS = ["pipeline:", "dispatching", "complete", "failed", "error"]


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("vn_bridge")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    # Stderr handler
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    # File handler
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger


log = setup_logging()


def _infer_portrait_state(agent: str, text: str) -> str:
    """Infer portrait emotional state from text content.

    Maps key emotional signals to per-agent portrait state names.
    All states fall back to "neutral" if the asset doesn't exist —
    handled by validate_portrait_state() in script.rpy.
    """
    lower = text.lower()

    # Vulnerability / warmth signals → "vulnerable" state
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

    # Per-agent tertiary states from PORTRAIT_GENERATION_GUIDE.md
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
    """Split text into sentence-level dialogue beats.

    Splits on sentence boundaries (.!?) so each beat fits a Ren'Py dialogue
    box without walls of text. Empty sentences are discarded.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


async def main() -> None:
    agent_url = get_agent_url("hephaestus")
    log.info(f"Connecting to Hephaestus at {agent_url}")

    # Initialize A2A Client
    config = ClientConfig(
        streaming=True,
        httpx_client=httpx.AsyncClient(timeout=600),
    )

    try:
        resolver = A2ACardResolver(cast(httpx.AsyncClient, config.httpx_client), agent_url)
        card = await resolver.get_agent_card()
        # Ensure we use the exact URL we connected with (Docker/Localhost resolution)
        card.url = agent_url
        client = await ClientFactory.connect(card, client_config=config)
        log.info(f"Connected to agent: {card.name} v{card.version}")
    except Exception as e:
        log.error(f"Failed to connect to Hephaestus: {e}")
        msg = {"agent": "system", "message": f"Bridge Connection Error: {e}"}
        print(json.dumps(msg))  # noqa: T201 - IPC to Ren'Py subprocess
        sys.stdout.flush()
        return

    context_id = uuid4().hex
    log.info(f"Bridge ready. Context ID: {context_id}")

    # Main loop: Read line from stdin, send to agent, stream results to stdout
    while True:
        try:
            # Use run_in_executor for non-blocking read from blocking stdin
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                log.info("Stdin closed, exiting.")
                break

            line = line.strip()
            if not line:
                continue

            log.info(f"Received from Ren'Py: {line[:200]}")
            request = json.loads(line)

            # Handle resume action (sent after save/load reconnect)
            action = request.get("action", "message")

            # Handle player choice selection — sent when player picks from a
            # choice screen. The choice text is forwarded as a new user message.
            if action == "choice":
                choice_text = request.get("choice", "")
                if choice_text:
                    # Treat the chosen option as the player's next message
                    request = {
                        "action": "message",
                        "text": choice_text,
                        "context_id": request.get("context_id", ""),
                        "player_id": request.get("player_id", ""),
                    }
                    action = "message"
                    log.info(f"Choice selected: {choice_text!r}")
                else:
                    continue

            if action == "resume":
                resume_context = request.get("context_id")
                if resume_context:
                    context_id = resume_context
                    log.info(f"Resuming context: {context_id}")
                out = {"action": "status", "message": "The forge rekindles. Context restored."}
                print(json.dumps(out))  # noqa: T201 - IPC to Ren'Py subprocess
                sys.stdout.flush()
                continue

            user_text = request.get("text", "")
            if not user_text:
                log.warning("Empty message received from Ren'Py")
                continue

            # Use context_id from the message if provided (supports save/load slots)
            msg_context_id = request.get("context_id", "").strip()
            if msg_context_id:
                context_id = msg_context_id

            # Track player_id for fact storage (sent by script.rpy with every message)
            current_player_id = request.get("player_id", "").strip()

            # Track which agent is currently active — reset per request
            current_agent = "hephaestus"

            # Create A2A message
            message = Message(
                role=Role.user, parts=[Part(root=TextPart(text=user_text))], message_id=str(uuid4())
            )
            message.context_id = context_id

            # Stream response back to stdout as JSON lines
            found_artifact = False
            async for event in client.send_message(message):
                if isinstance(event, Message):
                    # Direct message response (rare in our streaming setup but possible)
                    text = "\n".join(p.root.text for p in event.parts if hasattr(p.root, "text"))
                    if text:
                        log.info(f"Sending direct response to Ren'Py: {text[:100]}...")
                        portrait_state = _infer_portrait_state(current_agent, text)
                        for beat in _paginate(text):
                            msg = {
                                "agent": current_agent,
                                "message": beat,
                                "portrait": portrait_state,
                            }
                            print(json.dumps(msg))  # noqa: T201 - IPC to Ren'Py subprocess
                            sys.stdout.flush()
                        found_artifact = True
                    continue

                # ClientEvent: tuple[Task, update | None]
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

                        # Step 1 — Infer active agent from status message content
                        lower = status_msg.lower()
                        for name in AGENT_NAMES:
                            if name in lower:
                                current_agent = name
                                break

                        log.info(f"Status update (agent={current_agent}): {status_msg[:100]}")

                        # Step 2 — Promote key pipeline events to dialogue beats;
                        # everything else stays as a lightweight thinking overlay
                        if any(kw in lower for kw in DIALOGUE_KEYWORDS):
                            out = {
                                "agent": "hephaestus",
                                "message": status_msg[:200],
                                "portrait": "neutral",
                            }
                            log.info(f"Promoting status to dialogue beat: {status_msg[:60]}")
                        else:
                            out = {"action": "status", "message": status_msg[:120]}

                        print(json.dumps(out))  # noqa: T201 - IPC to Ren'Py subprocess
                        sys.stdout.flush()

                    elif isinstance(update, TaskArtifactUpdateEvent):
                        if update.artifact and update.artifact.parts:
                            text = "\n".join(
                                p.root.text
                                for p in update.artifact.parts
                                if hasattr(p.root, "text")
                            )
                            if text:
                                log.info(
                                    f"Artifact received (agent={current_agent})! "
                                    f"Sending to Ren'Py: {text[:100]}..."
                                )
                                # Extract <FACT> tags (player personalization) and strip them
                                # from the displayed text before forwarding to Ren'Py.
                                text = process_agent_output(
                                    text, current_player_id, source_agent=current_agent
                                )
                                # Step 3 & 4 — Attribute to correct agent, paginate sentences
                                # Infer portrait state from first beat's content (full text context)
                                portrait_state = _infer_portrait_state(current_agent, text)
                                for beat in _paginate(text):
                                    msg = {
                                        "agent": current_agent,
                                        "message": beat,
                                        "portrait": portrait_state,
                                    }
                                    print(json.dumps(msg))  # noqa: T201 - IPC to Ren'Py subprocess
                                    sys.stdout.flush()
                                found_artifact = True

            if not found_artifact:
                log.warning("Pipeline finished without emitting an artifact.")
                msg = {
                    "agent": "system",
                    "message": "The pipeline completed but no response was generated.",
                }
                print(json.dumps(msg))  # noqa: T201 - IPC to Ren'Py subprocess
                sys.stdout.flush()

        except json.JSONDecodeError:
            log.error(f"Invalid JSON received from Ren'Py: {line}")
        except Exception as e:
            log.error(f"Error during message processing: {e}", exc_info=True)
            msg = {"agent": "system", "message": f"Processing Error: {e}"}
            print(json.dumps(msg))  # noqa: T201 - IPC to Ren'Py subprocess
            sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
