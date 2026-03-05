"""Kourai Khryseai — Pygame GUI client.

Full-resolution anime portrait dialogue window. JRPG/mecha comms aesthetic.
No kaomoji. The golden maidens speak for themselves.

Layout (1280×720):
  Left (320px)  — portrait panel: avatar + agent name + title
  Right (960px) — dialogue history (scrollable) + active dialogue box
  Bottom (80px) — text input bar, spans full width

Usage:
  make gui
  uv run python -m hosts.gui [--agent URL]
"""

from __future__ import annotations

import asyncio
import contextlib
import queue
import random
import signal
import sys
import threading
import time

import pygame
from PIL import Image as PILImage

from .audio_manager import AudioManager
from .client import GuiClient
from .constants import (
    DIALOGUE_H,
    DIALOGUE_W,
    DIALOGUE_X,
    INPUT_H,
    H,
    W,
)
from .dialogue import DialogueEntry, DialogueHistory, draw_banner
from .dialogue_pacing import PacingMode
from .gui_components_integration import GUIComponentsIntegration
from .input_bar import InputBar
from .maidens import (
    AGENTS,
    HANDOFF_GENERIC,
    HANDOFF_LINES,
    VICTORY_LINES,
    detect_agent,
    get_avatar_path,
)
from .particles import ParticleSystem
from .portrait import PortraitPanel
from .settings_ui import SettingsOverlay
from .tts_gui_integration import TTSGUIManager, extract_speakable

# Short pipeline-chatter patterns that are system messages, not dialogue
import re as _re

_SYSTEM_STATUS_RE = _re.compile(
    r"^(?:Analyzing|Processing|Running|Building|Compiling|Testing|Checking|"
    r"Routing|Delegating|Preparing|Loading|Connecting|Waiting|Scanning|"
    r"Fetching|Generating|Deploying|Resolving|Verifying)\b",
    _re.IGNORECASE,
)


def _is_system_status(text: str) -> bool:
    """Return True if text looks like transient pipeline chatter."""
    stripped = text.strip()
    if len(stripped) > 80:
        return False
    if "?" in stripped:
        return False
    if "INPUT_REQUIRED:" in stripped:
        return False
    return bool(_SYSTEM_STATUS_RE.match(stripped))


# ---------------------------------------------------------------------------
# Main GUI entry point
# ---------------------------------------------------------------------------
def main(agent_url: str | None = None) -> None:
    # Setup shutdown flag and signal handlers for graceful Ctrl+C shutdown
    _shutdown_flag = {"running": True}
    _queues = {"send_q": None}

    def _signal_handler(signum: int, frame) -> None:
        _shutdown_flag["running"] = False
        # Signal the client to shut down
        try:
            if _queues["send_q"] is not None:
                _queues["send_q"].put(None)
        except Exception:
            pass

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    pygame.init()
    pygame.display.set_caption("Kourai Khryseai — Golden Maidens")

    # Try to set a nice window icon (hephaestus avatar)
    icon_path = get_avatar_path("hephaestus")
    if icon_path:
        try:
            icon_img = PILImage.open(icon_path).convert("RGBA").resize((32, 32))
            icon_surf = pygame.image.frombytes(icon_img.tobytes(), (32, 32), "RGBA")
            pygame.display.set_icon(icon_surf)
        except Exception:
            pass

    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
    clock = pygame.time.Clock()

    # --- Subsystems ---
    gui_integration = GUIComponentsIntegration(None)

    # --- Audio Manager (must be created before SettingsOverlay for slider wiring) ---
    audio_manager = AudioManager()
    audio_manager.set_music_volume(gui_integration.settings.get("music_volume", 0.5))
    audio_manager.set_ambient_volume(gui_integration.settings.get("ambient_volume", 0.5))
    audio_manager.set_voice_volume(gui_integration.settings.get("voice_volume", 1.0))
    audio_manager.set_sfx_volume(gui_integration.settings.get("sfx_volume", 0.8))

    settings_overlay = SettingsOverlay(W, H, gui_integration, audio_manager)

    particles = ParticleSystem()
    portrait = PortraitPanel()
    history = DialogueHistory()
    input_bar = InputBar()

    # Set initial Hephaestus quote
    heph_quotes = AGENTS["hephaestus"].get("user_quotes", [])
    portrait.current_quote = random.choice(heph_quotes) if heph_quotes else ""

    # --- Fullscreen state ---
    is_fullscreen = gui_integration.settings.get("fullscreen", False)

    if is_fullscreen:
        pygame.display.toggle_fullscreen()

    def toggle_fullscreen(enable: bool) -> None:
        nonlocal is_fullscreen, dialogue_rect, settings_overlay
        is_fullscreen = enable
        pygame.display.toggle_fullscreen()

        # Small delay to let pygame update the display
        time.sleep(0.1)

        # Get the actual screen size after toggle
        screen_w, screen_h = screen.get_size()
        dialogue_rect.width = screen_w - DIALOGUE_X
        dialogue_rect.height = screen_h - INPUT_H

        # Update settings overlay dimensions
        settings_overlay.screen_w = screen_w
        settings_overlay.screen_h = screen_h
        settings_overlay.panel_rect.centerx = screen_w // 2
        settings_overlay.panel_rect.centery = screen_h // 2

    settings_overlay.set_fullscreen_callback(toggle_fullscreen)

    def on_quit() -> None:
        _shutdown_flag["running"] = False
        send_q.put(None)  # shutdown client

    settings_overlay.set_quit_callback(on_quit)

    # --- A2A client in background thread ---
    send_q: queue.Queue[tuple[str, str] | None] = queue.Queue()
    recv_q: queue.Queue[dict] = queue.Queue()
    _queues["send_q"] = send_q  # Store for signal handler
    client = GuiClient(send_q, recv_q, agent_url)

    def _run_client() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(client.run())
        finally:
            loop.close()

    _thread = threading.Thread(target=_run_client, daemon=True)
    _thread.start()

    # --- Start audio playback ---
    audio_manager.play_ambient()
    audio_manager.play_music("assets/audio/music/SithuAye-2016.ogg")

    # --- TTS Manager ---
    tts_manager = TTSGUIManager(recv_q, enable_tts=True, pacing_mode=PacingMode.NORMAL)
    tts_manager.set_current_agent("hephaestus")

    # --- State ---
    connected = False
    current_agent = "hephaestus"
    last_agent = "hephaestus"

    dialogue_rect = pygame.Rect(DIALOGUE_X, 34, DIALOGUE_W, DIALOGUE_H - 34)

    while _shutdown_flag["running"]:
        dt = clock.tick(60) / 1000.0

        # --- Process recv_q events ---
        while not recv_q.empty():
            event = recv_q.get_nowait()
            etype = event.get("type")

            if etype == "connected":
                connected = True
                # System toast for connection status
                history.add(
                    DialogueEntry(
                        "hephaestus",
                        f"Connected to {event.get('name', 'Hephaestus')}",
                        is_system=True,
                    )
                )
                # Character greeting as dialogue
                history.add(
                    DialogueEntry(
                        "hephaestus",
                        "The forge is hot. What are we building?",
                    )
                )
                history.scroll_to_bottom()

            elif etype == "disconnected":
                connected = False

            elif etype == "status":
                raw = event["text"]
                agent, text = detect_agent(raw)
                if not text:
                    continue

                if "INPUT_REQUIRED:" in text:
                    parts = text.split("INPUT_REQUIRED:", 1)
                    question = parts[1].strip()
                    input_bar.waiting_for_agent = agent or current_agent
                    input_bar.processing = False
                    history.add(DialogueEntry(agent or current_agent, question))
                    history.scroll_to_bottom()
                    # Speak the question aloud
                    speaking_agent = agent or current_agent
                    threading.Thread(
                        target=tts_manager.tts_engine.speak_sync,
                        args=(question,),
                        kwargs={"agent_name": speaking_agent},
                        daemon=True,
                    ).start()
                    continue

                if agent:
                    # Detect agent switch
                    if agent != current_agent:
                        # Handoff chatter from outgoing agent
                        key = (current_agent, agent)
                        lines = HANDOFF_LINES.get(key) or HANDOFF_GENERIC.get(current_agent)
                        if lines:
                            handoff_line = random.choice(lines)
                            history.add(DialogueEntry(current_agent, handoff_line))

                        portrait.switch_to(agent)
                        # Update quote for new agent
                        agent_quotes = AGENTS.get(agent, {}).get("quotes", [])
                        portrait.current_quote = random.choice(agent_quotes) if agent_quotes else ""
                        current_agent = agent
                        last_agent = agent
                        tts_manager.set_current_agent(agent)

                    # Classify: pipeline chatter → system, dialogue → normal
                    is_sys = _is_system_status(text)
                    history.add(DialogueEntry(agent, text, is_system=is_sys))
                else:
                    is_sys = _is_system_status(text)
                    history.add(DialogueEntry(current_agent, text, is_system=is_sys))

                history.scroll_to_bottom()

            elif etype == "result":
                text = event["text"]
                history.add(DialogueEntry(last_agent, text, is_result=True))
                history.scroll_to_bottom()
                # Speak only the conversational portions (skip commit groups, code, etc.)
                speakable = extract_speakable(text)
                if speakable and tts_manager.enable_tts and tts_manager.tts_engine:
                    threading.Thread(
                        target=tts_manager.tts_engine.speak_sync,
                        args=(speakable,),
                        kwargs={"agent_name": last_agent},
                        daemon=True,
                    ).start()

            elif etype == "complete":
                elapsed = event.get("elapsed", 0.0)
                input_bar.processing = False

                # Victory line as dialogue
                vlines = VICTORY_LINES.get(last_agent, [])
                if vlines:
                    victory_text = random.choice(vlines)
                    history.add(DialogueEntry(last_agent, victory_text))
                    # Speak just the personality line
                    if tts_manager.enable_tts and tts_manager.tts_engine:
                        threading.Thread(
                            target=tts_manager.tts_engine.speak_sync,
                            args=(victory_text,),
                            kwargs={"agent_name": last_agent},
                            daemon=True,
                        ).start()

                # Elapsed time as system toast
                history.add(
                    DialogueEntry(last_agent, f"✦ Completed in {elapsed:.1f}s", is_system=True)
                )

                history.scroll_to_bottom()

            elif etype == "error":
                history.add(DialogueEntry("hephaestus", event["text"], is_error=True))
                input_bar.processing = False
                history.scroll_to_bottom()

        # --- Pygame events ---
        for event in pygame.event.get():
            if settings_overlay.handle_event(event):
                continue

            if event.type == pygame.QUIT:
                _shutdown_flag["running"] = False
                send_q.put(None)  # shutdown client

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    settings_overlay.toggle()
                else:
                    submitted = input_bar.handle_key(event)
                    if submitted:
                        # Show user bubble
                        history.add(DialogueEntry("user", submitted, is_user=True))
                        history.scroll_to_bottom()
                        # Send to pipeline
                        send_q.put((input_bar.waiting_for_agent or current_agent, submitted))
                        input_bar.processing = True

                        # Reset to Hephaestus for the incoming pipeline
                        portrait.switch_to(input_bar.waiting_for_agent or "hephaestus")
                        current_agent = input_bar.waiting_for_agent or "hephaestus"
                        input_bar.waiting_for_agent = None

                        agent_quotes = AGENTS[current_agent].get("user_quotes", [])
                        portrait.current_quote = random.choice(agent_quotes) if agent_quotes else ""

            elif event.type == pygame.TEXTINPUT:
                if not input_bar.processing:
                    input_bar.handle_textinput(event)

            elif event.type == pygame.MOUSEWHEEL:
                history.scroll(-event.y * 40)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked_agent = history.handle_click(event.pos, dialogue_rect)
                if clicked_agent and clicked_agent in AGENTS:
                    portrait.switch_to(clicked_agent)
                    current_agent = clicked_agent
                    agent_quotes = AGENTS.get(clicked_agent, {}).get("quotes", [])
                    portrait.current_quote = random.choice(agent_quotes) if agent_quotes else ""

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                clicked_text = history.handle_right_click(event.pos, dialogue_rect)
                if clicked_text:
                    try:
                        pygame.scrap.put_text(clicked_text)
                    except Exception as e:
                        print(f"Clipboard error: {e}")

            elif event.type == pygame.VIDEORESIZE:
                # Update layout for new window size
                screen_w, screen_h = event.size
                dialogue_rect.width = screen_w - DIALOGUE_X
                dialogue_rect.height = screen_h - INPUT_H

                # Update settings overlay dimensions
                settings_overlay.screen_w = screen_w
                settings_overlay.screen_h = screen_h
                settings_overlay.panel_rect.centerx = screen_w // 2
                settings_overlay.panel_rect.centery = screen_h // 2

        # --- Updates ---
        gui_integration.update(dt)
        settings_overlay.update(dt)

        # Map dynamic high-contrast colors to the constants module
        # WHY: high-contrast mode needs to override the default palette at runtime
        import hosts.gui.constants as _c

        palette = gui_integration.high_contrast.get_color_palette()
        _c.DARK_BG = palette.get("background", (12, 10, 8))
        _c.PANEL_BG = palette.get("bubble_bg", (18, 14, 10))
        _c.GOLD = palette.get("gold", (218, 165, 32))
        _c.GOLD_BRIGHT = palette.get("gold", (255, 215, 0))
        _c.GOLD_DIM = palette.get("gold_dim", (140, 105, 20))
        _c.WHITE = palette.get("text", (240, 235, 225))
        _c.DIM_WHITE = palette.get("scrollbar", (160, 155, 145))
        _c.INPUT_BG = palette.get("bubble_bg", (20, 16, 12))
        _c.SCROLLBAR = palette.get("scrollbar", (50, 40, 25))
        _c.ERROR_RED = palette.get("error_red", (200, 80, 60))

        if not gui_integration.settings.get("reduce_motion", False):
            particles.update(dt)

        portrait.update(dt)
        input_bar.update(dt)

        # --- Draw ---
        screen.fill(_c.DARK_BG)

        # Background particles (full canvas)
        if not gui_integration.settings.get("reduce_motion", False):
            particles.draw(screen)

        # Left: portrait panel
        portrait.draw(screen)

        # Right: banner + dialogue history
        draw_banner(screen, connected, agent_url or "")
        history.draw(screen, dialogue_rect)

        # Right panel border
        pygame.draw.line(screen, _c.GOLD_DIM, (DIALOGUE_X, 0), (DIALOGUE_X, H - INPUT_H), 1)

        # Bottom: input
        input_bar.draw(screen)

        # Overlay
        settings_overlay.draw(screen)

        pygame.display.flip()

    # Cleanup (graceful shutdown on Ctrl+C)
    with contextlib.suppress(Exception):
        audio_manager.cleanup()
    with contextlib.suppress(Exception):
        tts_manager.cleanup()
    with contextlib.suppress(Exception):
        pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Kourai Khryseai — Pygame GUI")
    parser.add_argument("--agent", default=None, help="Hephaestus agent URL")
    args = parser.parse_args()
    main(agent_url=args.agent)
