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

# Short pipeline-chatter patterns that are system messages, not dialogue
import re as _re
import signal
import sys
import threading
import time

import pygame
from PIL import Image as PILImage

from .alignment_gauges import AlignmentGaugePanel
from .alignment_theme import compute_alignment_palette
from .audio_manager import AudioManager
from .client import GuiClient
from .constants import BANNER_TOTAL_H, DIALOGUE_H, DIALOGUE_W, DIALOGUE_X, INPUT_H, H, W, theme
from .dialogue import DialogueEntry, DialogueHistory, draw_banner
from .dialogue_pacing import PacingMode
from .flash_effect import FlashEffect
from .gossip_panel import GossipPanel
from .gui_components_integration import GUIComponentsIntegration
from .input_bar import InputBar
from .loading_screen import run_loading_screen
from .maidens import (
    AGENTS,
    HANDOFF_GENERIC,
    HANDOFF_LINES,
    VICTORY_LINES,
    detect_agent,
    get_avatar_path,
)
from .memory_viewer import MemoryViewerPanel
from .onboarding_ui import OnboardingOverlay
from .particles import ParticleSystem
from .portrait import PortraitPanel
from .profile_select import run_profile_select
from .quick_actions import QuickActionBar
from .settings_ui import SettingsOverlay
from .tts_gui_integration import TTSGUIManager, extract_speakable
from .typewriter import TypewriterManager

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
    _queues: dict[str, queue.Queue | None] = {"send_q": None}

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

    # --- Ambient forge audio starts immediately (before any loading) ---
    audio_manager = AudioManager()
    audio_manager.play_ambient()

    # --- Loaded subsystems (populated by the generator, used after) ---
    _loaded: dict = {}

    def _load_subsystems():
        """Generator that initializes all GUI subsystems one step at a time.

        Yields (progress, description) tuples.  Each ``next()`` call does
        one unit of work on the main thread (safe for Surface creation).
        """
        total_steps = 14
        step = 0

        # 1. GUI integration (settings, font scaler, etc.)
        step += 1
        gui_integration = GUIComponentsIntegration(None)
        _loaded["gui_integration"] = gui_integration
        yield step / total_steps, "Loading settings…"

        # 2. Wire audio volumes from saved settings
        step += 1
        audio_manager.set_music_volume(gui_integration.settings.get("music_volume", 0.5))
        audio_manager.set_ambient_volume(gui_integration.settings.get("ambient_volume", 0.5))
        audio_manager.set_voice_volume(gui_integration.settings.get("voice_volume", 1.0))
        audio_manager.set_sfx_volume(gui_integration.settings.get("sfx_volume", 0.8))
        yield step / total_steps, "Configuring audio…"

        # 3. Settings overlay
        step += 1
        _loaded["settings_overlay"] = SettingsOverlay(W, H, gui_integration, audio_manager)
        yield step / total_steps, "Building settings UI…"

        # 4. Alignment gauge panel
        step += 1
        _loaded["alignment_panel"] = AlignmentGaugePanel(W, H)
        yield step / total_steps, "Forging alignment gauges…"

        # 5. Gossip side panel
        step += 1
        _loaded["gossip_panel"] = GossipPanel(W, H)
        yield step / total_steps, "Opening gossip channels…"

        # 6. Onboarding overlay
        step += 1
        _loaded["onboarding"] = OnboardingOverlay(W, H)
        yield step / total_steps, "Preparing introductions…"

        # 7. Memory viewer panel
        step += 1
        _loaded["memory_viewer"] = MemoryViewerPanel(W, H)
        yield step / total_steps, "Cataloging memories…"

        # 8. Particle system
        step += 1
        _loaded["particles"] = ParticleSystem()
        yield step / total_steps, "Igniting forge embers…"

        # 9. Portrait panel + avatar pre-cache
        step += 1
        portrait = PortraitPanel()
        heph_quotes = AGENTS["hephaestus"].get("user_quotes", [])
        portrait.current_quote = random.choice(heph_quotes) if heph_quotes else ""
        _loaded["portrait"] = portrait
        yield step / total_steps, "Summoning the maidens…"

        # 10. Dialogue history + input bar + effects
        step += 1
        _loaded["history"] = DialogueHistory()
        _loaded["input_bar"] = InputBar()
        reduce_motion = gui_integration.settings.get("reduce_motion", False)
        _loaded["typewriter"] = TypewriterManager(motion_sensitivity_enabled=reduce_motion)
        _loaded["flash"] = FlashEffect()
        yield step / total_steps, "Preparing the forge…"

        # 11. Quick actions
        step += 1
        _loaded["quick_actions"] = QuickActionBar()
        yield step / total_steps, "Forging quick actions…"

        # 12. A2A client thread
        step += 1
        send_q: queue.Queue[tuple[str, str] | None] = queue.Queue()
        recv_q: queue.Queue[dict] = queue.Queue()
        _queues["send_q"] = send_q
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
        _loaded["send_q"] = send_q
        _loaded["recv_q"] = recv_q
        yield step / total_steps, "Connecting to Hephaestus…"

        # 13. Audio ready (music deferred until user presses start)
        step += 1
        yield step / total_steps, "Tuning the forge…"

        # 14. TTS manager
        step += 1
        tts_manager = TTSGUIManager(recv_q, enable_tts=True, pacing_mode=PacingMode.NORMAL)
        tts_manager.set_current_agent("hephaestus")
        _loaded["tts_manager"] = tts_manager
        yield step / total_steps, "Ready"

    # --- Run the title / loading screen ---
    if not run_loading_screen(screen, clock, _load_subsystems()):
        # User closed during loading
        with contextlib.suppress(Exception):
            audio_manager.cleanup()
        with contextlib.suppress(Exception):
            pygame.quit()
        sys.exit(0)

    # --- Music fades in slowly after the player presses start ---
    audio_manager.fade_to_music("assets/audio/music/sithuaye-2016.ogg", fade_ms=6000)

    # --- Profile selection screen ---
    # Show profile select after title screen; runs its own event loop
    _selected_profile = None
    _run_onboarding = False
    try:
        from kourai_common.player import (
            list_profiles,
            needs_onboarding,
            set_active_profile,
        )

        profiles = list_profiles()
        if needs_onboarding():
            # No profiles exist — go straight to onboarding
            _run_onboarding = True
        elif len(profiles) == 1:
            # Single profile — auto-select it
            _selected_profile = profiles[0]
            set_active_profile(_selected_profile["player_id"])
        else:
            # Multiple profiles — show selection screen
            result = run_profile_select(screen, clock, profiles)
            if result is False:
                # User quit
                with contextlib.suppress(Exception):
                    audio_manager.cleanup()
                with contextlib.suppress(Exception):
                    pygame.quit()
                sys.exit(0)
            elif result is None:
                # New Game
                _run_onboarding = True
            else:
                _selected_profile = result
                set_active_profile(_selected_profile["player_id"])
    except Exception:
        pass  # Player module not available — skip

    # --- Unpack loaded subsystems ---
    gui_integration: GUIComponentsIntegration = _loaded["gui_integration"]
    settings_overlay: SettingsOverlay = _loaded["settings_overlay"]
    alignment_panel: AlignmentGaugePanel = _loaded["alignment_panel"]
    gossip_panel: GossipPanel = _loaded["gossip_panel"]
    onboarding: OnboardingOverlay = _loaded["onboarding"]
    memory_viewer: MemoryViewerPanel = _loaded["memory_viewer"]
    particles: ParticleSystem = _loaded["particles"]
    portrait: PortraitPanel = _loaded["portrait"]
    history: DialogueHistory = _loaded["history"]
    input_bar: InputBar = _loaded["input_bar"]
    typewriter: TypewriterManager = _loaded["typewriter"]
    flash: FlashEffect = _loaded["flash"]
    send_q: queue.Queue[tuple[str, str] | None] = _loaded["send_q"]
    recv_q: queue.Queue[dict] = _loaded["recv_q"]
    tts_manager: TTSGUIManager = _loaded["tts_manager"]
    quick_actions: QuickActionBar = _loaded["quick_actions"]

    # --- Initial layout ---
    dialogue_rect = pygame.Rect(DIALOGUE_X, BANNER_TOTAL_H, DIALOGUE_W, DIALOGUE_H - BANNER_TOTAL_H)

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

    # --- State ---
    connected = False
    current_agent = "hephaestus"
    last_agent = "hephaestus"
    _typewriter_full_text = ""  # full text for the active typewriter entry
    _alignment_refresh_timer = 0.0  # Refresh alignment from profile every 10s

    # --- Trigger onboarding if needed (New Game or first run) ---
    if _run_onboarding:
        onboarding.start()

    def _add_with_typewriter(entry: DialogueEntry) -> None:
        """Add a dialogue entry, animating it with the typewriter effect."""
        nonlocal _typewriter_full_text
        _typewriter_full_text = entry.text
        if not entry.is_system and not entry.is_user:
            entry.text = ""  # start empty; typewriter fills it in
            history.add(entry)
            typewriter.start(_typewriter_full_text)
        else:
            history.add(entry)

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
                _add_with_typewriter(
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
                    _add_with_typewriter(DialogueEntry(agent or current_agent, question))
                    history.scroll_to_bottom()
                    # Speak the question aloud
                    speaking_agent = agent or current_agent
                    if tts_manager.tts_engine:
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
                            _add_with_typewriter(DialogueEntry(current_agent, handoff_line))

                        portrait.switch_to(agent)
                        flash.trigger()
                        # Update quote for new agent
                        agent_quotes = AGENTS.get(agent, {}).get("quotes", [])
                        portrait.current_quote = random.choice(agent_quotes) if agent_quotes else ""
                        current_agent = agent
                        last_agent = agent
                        tts_manager.set_current_agent(agent)

                    # Classify: pipeline chatter → system, dialogue → normal
                    is_sys = _is_system_status(text)
                    entry = DialogueEntry(agent, text, is_system=is_sys)
                    if is_sys:
                        history.add(entry)
                    else:
                        _add_with_typewriter(entry)
                else:
                    is_sys = _is_system_status(text)
                    entry = DialogueEntry(current_agent, text, is_system=is_sys)
                    if is_sys:
                        history.add(entry)
                    else:
                        _add_with_typewriter(entry)

                history.scroll_to_bottom()

            elif etype == "result":
                text = event["text"]
                _add_with_typewriter(DialogueEntry(last_agent, text, is_result=True))
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
                    _add_with_typewriter(DialogueEntry(last_agent, victory_text))
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
        for pg_event in pygame.event.get():
            # Onboarding overlay consumes ALL events while active
            if onboarding.active:
                onboarding.handle_event(pg_event)
                # Check if onboarding just completed
                result = onboarding.get_result()
                if result:
                    try:
                        from kourai_common.player import PlayerProfile, set_active_profile

                        profile = PlayerProfile()
                        profile.display_name = result["display_name"]
                        profile.tts_name = result["tts_name"]
                        profile.title = result["title"]
                        profile.role = result["role"]
                        profile.pronouns = result["pronouns"]
                        profile.save()
                        set_active_profile(profile.player_id)
                        alignment_panel.update_values(
                            profile.sovereignty, profile.devotion, profile.role
                        )
                    except Exception:
                        pass
                continue

            if settings_overlay.handle_event(pg_event):
                continue
            if memory_viewer.handle_event(pg_event):
                continue
            if alignment_panel.handle_event(pg_event):
                continue
            if gossip_panel.handle_event(pg_event):
                continue

            if pg_event.type == pygame.QUIT:
                _shutdown_flag["running"] = False
                send_q.put(None)  # shutdown client

            elif pg_event.type == pygame.KEYDOWN:
                if pg_event.key == pygame.K_ESCAPE:
                    settings_overlay.toggle()
                elif pg_event.key == pygame.K_F2:
                    alignment_panel.toggle()
                elif pg_event.key == pygame.K_F3:
                    if gossip_panel.active:
                        gossip_panel.dismiss()
                    else:
                        gossip_panel.active = True
                elif pg_event.key == pygame.K_F4:
                    memory_viewer.toggle()
                elif typewriter.active and not typewriter.is_complete():
                    # Any key skips the typewriter to show full text
                    typewriter.skip()
                    history.update_last_text(typewriter.get_displayed_text())
                else:
                    submitted = input_bar.handle_key(pg_event)
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

            elif pg_event.type == pygame.TEXTINPUT:
                if not input_bar.processing:
                    input_bar.handle_textinput(pg_event)

            elif pg_event.type == pygame.MOUSEWHEEL:
                history.scroll(-pg_event.y * 40)

            elif pg_event.type == pygame.MOUSEMOTION:
                quick_actions.update(pg_event.pos)

            elif pg_event.type == pygame.MOUSEBUTTONDOWN and pg_event.button == 1:
                if not input_bar.processing:
                    action = quick_actions.handle_click(pg_event.pos)
                    if action:
                        history.add(DialogueEntry("user", action.display_text, is_user=True))
                        payload = f"{action.display_text}\n\n{action.hidden_prompt}"
                        send_q.put((action.agent, payload))
                        portrait.switch_to(action.agent)
                        current_agent = action.agent
                        input_bar.processing = True
                        agent_quotes = AGENTS.get(action.agent, {}).get("user_quotes", [])
                        portrait.current_quote = (
                            random.choice(agent_quotes) if agent_quotes else ""
                        )

                clicked_agent = history.handle_click(pg_event.pos, dialogue_rect)
                if clicked_agent and clicked_agent in AGENTS:
                    portrait.switch_to(clicked_agent)
                    current_agent = clicked_agent
                    agent_quotes = AGENTS.get(clicked_agent, {}).get("quotes", [])
                    portrait.current_quote = random.choice(agent_quotes) if agent_quotes else ""

            elif pg_event.type == pygame.MOUSEBUTTONDOWN and pg_event.button == 3:
                clicked_text = history.handle_right_click(pg_event.pos, dialogue_rect)
                if clicked_text:
                    try:
                        pygame.scrap.put_text(clicked_text)
                    except Exception as e:
                        print(f"Clipboard error: {e}")

            elif pg_event.type == pygame.VIDEORESIZE:
                # Update layout for new window size
                screen_w, screen_h = pg_event.size
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
        alignment_panel.update(dt)
        gossip_panel.update(dt)
        onboarding.update(dt)
        memory_viewer.update(dt)

        # Apply alignment-based visual theming (blended with high-contrast)
        if not gui_integration.settings.get("high_contrast", False):
            _alignment_refresh_timer += dt
            if _alignment_refresh_timer >= 10.0:
                _alignment_refresh_timer = 0.0
                try:
                    from kourai_common.player import PlayerProfile

                    _p = PlayerProfile.load()
                    if _p:
                        alignment_panel.update_values(_p.sovereignty, _p.devotion, _p.role)
                except Exception:
                    pass
            alignment_palette = compute_alignment_palette(
                alignment_panel.sovereignty, alignment_panel.devotion
            )
            theme.apply_palette(alignment_palette)
        else:
            # High-contrast overrides alignment theming
            theme.apply_palette(gui_integration.high_contrast.get_color_palette())

        # Sync reduce_motion to typewriter
        typewriter.set_motion_sensitivity(gui_integration.settings.get("reduce_motion", False))

        # Advance typewriter and feed partial text into the last dialogue entry
        if typewriter.active:
            displayed = typewriter.update(dt)
            history.update_last_text(displayed)

        # Advance portrait flash effect
        flash.update(dt)

        if not gui_integration.settings.get("reduce_motion", False):
            particles.update(dt)

        portrait.update(dt)
        input_bar.update(dt)

        # --- Draw ---
        screen.fill(theme.dark_bg)

        # Background particles (full canvas)
        if not gui_integration.settings.get("reduce_motion", False):
            particles.draw(screen)

        # Left: portrait panel (with handoff flash)
        _, flash_alpha = flash.update(0.0)  # peek alpha without advancing time
        portrait.draw(screen, flash_alpha=flash_alpha)

        # Right: banner + dialogue history
        draw_banner(screen, connected, agent_url or "")
        history.draw(screen, dialogue_rect)

        # Right panel border
        pygame.draw.line(screen, theme.gold_dim, (DIALOGUE_X, 0), (DIALOGUE_X, H - INPUT_H), 1)

        # Bottom: input
        input_bar.draw(screen)

        # Quick action pills (above input bar)
        if not input_bar.processing:
            quick_actions.draw(screen, disabled=False)
        else:
            quick_actions.draw(screen, disabled=True)

        # Overlay
        settings_overlay.draw(screen)

        # Alignment gauge (overlay on top-left)
        alignment_panel.draw(screen)

        # Gossip side panel (overlay on right)
        gossip_panel.draw(screen)

        # Memory viewer (full overlay)
        memory_viewer.draw(screen)

        # Onboarding overlay (blocks everything when active)
        onboarding.draw(screen)

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
