"""VN Bridge Entry Point — translates between stdin/stdout JSON and A2A agents.

This allows the Ren'Py VN Host to talk to the agent swarm without
needing to manage HTTP connections or ports directly.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import cast
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TaskArtifactUpdateEvent, TaskStatusUpdateEvent, TextPart

from kourai_common.config import get_agent_url

# Configure logging to both stderr and a file
PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "bridge_agents.log"


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
            user_text = request.get("text", "")

            if not user_text:
                log.warning("Empty message received from Ren'Py")
                continue

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
                        msg = {"agent": "hephaestus", "message": text, "portrait": "neutral"}
                        print(json.dumps(msg))  # noqa: T201 - IPC to Ren'Py subprocess
                        sys.stdout.flush()
                        found_artifact = True
                    continue

                # ClientEvent: tuple[Task, update | None]
                if isinstance(event, tuple):
                    task, update = event

                    if isinstance(update, TaskStatusUpdateEvent):
                        # Forward status updates to Ren'Py for "Thinking" UI
                        status_msg = ""
                        if update.status.message and hasattr(update.status.message, "parts"):
                            status_msg = "\n".join(
                                p.root.text
                                for p in update.status.message.parts
                                if hasattr(p.root, "text")
                            )

                        if status_msg:
                            log.info(f"Status update: {status_msg[:100]}")
                            # Forward to Ren'Py so the thinking screen can show live progress
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
                                log.info(f"Artifact received! Sending to Ren'Py: {text[:100]}...")
                                # Send final message to Ren'Py
                                msg = {
                                    "agent": "hephaestus",
                                    "message": text,
                                    "portrait": "neutral",
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
