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

import contextlib
import logging
import signal
import sys
from pathlib import Path
from typing import Any

import pygame
from PIL import Image as PILImage

from kourai_common.audio_env import configure_sdl_audio_driver

from .audio_manager import AudioManager
from .constants import (
    DIALOGUE_X,
    INPUT_H,
    theme,
)
from .display_manager import DisplayManager
from .gui_state import GUIState
from .loading_screen import run_loading_screen
from .maidens import get_avatar_path
from .profile_select import run_profile_select
from .pygame_event_handler import PygameEventDispatcher
from .queue_event_handler import QueueEventHandler
from .render import RenderPipeline
from .settings import SettingsManager
from .subsystem_loader import Subsystems, load_subsystems
from .theme_manager import ThemeManager

logger = logging.getLogger(__name__)


def _configure_gui_logging() -> None:
    """Console + file logging for the GUI host.

    Console stays quiet (WARNING) except for display diagnostics.
    Everything goes to logs/gui.log via the shared logging setup.
    """
    from kourai_common.log import setup_logging

    setup_logging("gui", level="DEBUG")
    # Console stays quiet; file gets everything
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    logging.getLogger("hosts.gui").setLevel(logging.DEBUG)
    logging.getLogger("hosts.gui.display_modes").setLevel(logging.DEBUG)
    logging.getLogger("hosts.gui.settings_ui").setLevel(logging.DEBUG)
    logging.getLogger("hosts.gui.subsystem_loader").setLevel(logging.DEBUG)


# ---------------------------------------------------------------------------
# Main GUI entry point
# ---------------------------------------------------------------------------
def main(agent_url: str | None = None) -> None:
    _configure_gui_logging()
    configure_sdl_audio_driver()

    # Setup shutdown flag and signal handlers for graceful Ctrl+C shutdown
    _shutdown_flag = {"running": True}
    _queues: dict[str, Any] = {"send_q": None}

    def _signal_handler(signum: int, frame) -> None:
        _shutdown_flag["running"] = False
        # Signal the client to shut down
        try:
            if _queues["send_q"] is not None:
                _queues["send_q"].put(None)
        except Exception:
            logger.debug("Error putting None into send_q during shutdown")

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
            logger.debug("Failed to set window icon")

    settings_path = Path.home() / ".kourai_khryseai" / "settings.json"
    startup_settings = SettingsManager(settings_path)

    display = DisplayManager(startup_settings)
    screen = display.screen
    clock = pygame.time.Clock()

    # --- Ambient forge audio starts immediately (before any loading) ---
    audio_manager = AudioManager()
    ambient_path = (
        Path(__file__).parent.parent.parent / "assets" / "audio" / "ambient" / "forge_loop.ogg"
    )
    if ambient_path.exists():
        audio_manager.play_ambient(str(ambient_path))
    else:
        logger.warning(f"Ambient audio not found: {ambient_path}")

    # --- Load subsystems during the loading screen ---
    _subsystems_box: list[Subsystems] = []

    def _loading_wrapper():
        """Wrap the typed loader so run_loading_screen can consume it."""
        try:
            logger.debug("Starting subsystem loader wrapper")
            result = yield from load_subsystems(
                screen.get_size(),
                settings_path,
                audio_manager,
                agent_url,
                _queues,
            )
            logger.debug("Subsystem loader wrapper complete")
            _subsystems_box.append(result)
        except Exception as e:
            logger.exception(f"Critical error during subsystem loading: {e}")
            raise

    try:
        logger.debug("Running loading screen")
        success = run_loading_screen(screen, clock, _loading_wrapper())
        logger.debug(f"Loading screen result: {success}")
        if not success:
            # User closed during loading
            logger.info("User closed during loading screen")
            with contextlib.suppress(Exception):
                audio_manager.cleanup()
            with contextlib.suppress(Exception):
                pygame.quit()
            sys.exit(0)
    except Exception as e:
        logger.exception(f"Fatal error during loading: {e}")
        with contextlib.suppress(Exception):
            audio_manager.cleanup()
        with contextlib.suppress(Exception):
            pygame.quit()
        raise

    # --- Music fades in after loading (non-blocking — background thread) ---
    music_dir = Path(__file__).parent.parent.parent / "assets" / "audio" / "music"
    try:
        audio_manager.load_playlist(str(music_dir))
        logger.debug(f"Loaded music playlist from {music_dir}")
    except Exception as e:
        logger.warning(f"Could not load music playlist: {e}")
    audio_manager.play_playlist()
    logger.debug("Music playlist started (background thread)")

    # --- Profile selection screen ---
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
            _run_onboarding = True
        elif len(profiles) == 1:
            _selected_profile = profiles[0]
            set_active_profile(_selected_profile["player_id"])
        else:
            result = run_profile_select(screen, clock, profiles)
            if result is False:
                with contextlib.suppress(Exception):
                    audio_manager.cleanup()
                with contextlib.suppress(Exception):
                    pygame.quit()
                sys.exit(0)
            elif result is None:
                _run_onboarding = True
            else:
                _selected_profile = result
                set_active_profile(_selected_profile["player_id"])
    except Exception:
        logger.debug("Player profile module unavailable or failed to load")

    # --- Unpack loaded subsystems (typed dataclass) ---
    sub = _subsystems_box[0]
    gui_integration = sub.gui_integration
    settings_overlay = sub.settings_overlay
    alignment_panel = sub.alignment_panel
    gossip_panel = sub.gossip_panel
    onboarding = sub.onboarding
    memory_viewer = sub.memory_viewer
    particles = sub.particles
    portrait = sub.portrait
    history = sub.history
    debug_log = sub.debug_log
    input_bar = sub.input_bar
    typewriter = sub.typewriter
    flash = sub.flash
    quick_actions = sub.quick_actions
    send_q = sub.send_q
    recv_q = sub.recv_q
    tts_manager = sub.tts_manager

    dialogue_rect = pygame.Rect(DIALOGUE_X, 34, 0, 0)

    def sync_layout(screen_w: int, screen_h: int) -> None:
        dialogue_rect.width = max(screen_w - DIALOGUE_X, 0)
        dialogue_rect.height = max(screen_h - INPUT_H - dialogue_rect.y, 0)
        settings_overlay.update_layout(screen_w, screen_h)
        alignment_panel.update_layout(screen_w, screen_h)
        gossip_panel.update_layout(screen_w, screen_h)
        onboarding.update_layout(screen_w, screen_h)
        memory_viewer.update_layout(screen_w, screen_h)

    def apply_display_mode(mode: str) -> None:
        display.apply_mode(mode, gui_integration.settings)
        sync_layout(*display.screen.get_size())

    settings_overlay.set_display_mode_callback(apply_display_mode)

    def on_quit() -> None:
        _shutdown_flag["running"] = False
        send_q.put(None)  # shutdown client

    settings_overlay.set_quit_callback(on_quit)
    sync_layout(*screen.get_size())

    # --- State ---
    state = GUIState()
    resize_events = {pygame.VIDEORESIZE}
    for event_name in ("WINDOWRESIZED", "WINDOWSIZECHANGED"):
        resize_event = getattr(pygame, event_name, None)
        if resize_event is not None:
            resize_events.add(resize_event)

    queue_handler = QueueEventHandler(
        state=state,
        history=history,
        portrait=portrait,
        input_bar=input_bar,
        typewriter=typewriter,
        flash=flash,
        tts_manager=tts_manager,
        gui_integration=gui_integration,
        audio_manager=audio_manager,
        debug_log=debug_log,
    )

    event_dispatcher = PygameEventDispatcher(
        state,
        onboarding=onboarding,
        settings_overlay=settings_overlay,
        memory_viewer=memory_viewer,
        alignment_panel=alignment_panel,
        gossip_panel=gossip_panel,
        gui_integration=gui_integration,
        input_bar=input_bar,
        typewriter=typewriter,
        history=history,
        portrait=portrait,
        quick_actions=quick_actions,
        debug_log=debug_log,
        display=display,
        audio_manager=audio_manager,
        send_q=send_q,
        dialogue_rect=dialogue_rect,
        resize_events=resize_events,
        on_quit=on_quit,
        sync_layout=sync_layout,
    )

    theme_mgr = ThemeManager(alignment_panel, gui_integration, theme)

    renderer = RenderPipeline(
        gui_integration=gui_integration,
        particles=particles,
        portrait=portrait,
        flash=flash,
        history=history,
        input_bar=input_bar,
        quick_actions=quick_actions,
        debug_log=debug_log,
        settings_overlay=settings_overlay,
        alignment_panel=alignment_panel,
        gossip_panel=gossip_panel,
        memory_viewer=memory_viewer,
        onboarding=onboarding,
        theme=theme,
        agent_url=agent_url or "",
    )

    # --- Trigger onboarding if needed (New Game or first run) ---
    if _run_onboarding:
        onboarding.start()

    while _shutdown_flag["running"]:
        dt = clock.tick(60) / 1000.0

        # --- Process recv_q events ---
        try:
            while not recv_q.empty():
                queue_handler.process_event(recv_q.get_nowait())
        except Exception as e:
            logger.exception(f"Exception processing recv_q event: {e}")

        # --- Pygame events ---
        try:
            events = pygame.event.get()
        except Exception as e:
            logger.exception(f"Exception getting pygame events: {e}")
            events = []

        for event in events:
            try:
                event_dispatcher.dispatch(event)
            except Exception as e:
                logger.exception(f"Exception handling pygame event: {e}")

        # Refresh screen reference after possible resize or display mode change
        screen = display.screen

        # --- Updates ---
        try:
            settings_overlay.update(dt)
            alignment_panel.update(dt)
            gossip_panel.update(dt)
            onboarding.update(dt)
            memory_viewer.update(dt)
        except Exception as e:
            logger.exception(f"Exception updating overlays: {e}")

        # Sync history settings
        try:
            history.show_timestamps = gui_integration.settings.get("show_timestamps", True)
            history.show_metadata = gui_integration.settings.get("show_metadata", True)
            history.timestamp_format = gui_integration.settings.get("timestamp_format", "24h")
        except Exception as e:
            logger.exception(f"Error syncing history settings: {e}")

        # Alignment-based visual theming (or high-contrast override)
        theme_mgr.update(dt)

        # Sync reduce_motion to typewriter
        try:
            typewriter.set_motion_sensitivity(gui_integration.settings.get("reduce_motion", False))
        except Exception as e:
            logger.exception(f"Error syncing reduce_motion: {e}")

        # Advance typewriter and feed partial text into the last dialogue entry
        try:
            if typewriter.active:
                displayed = typewriter.update(dt)
                history.update_last_text(displayed)
        except Exception as e:
            logger.exception(f"Error updating typewriter: {e}")

        # Advance portrait flash effect
        try:
            flash.update(dt)
        except Exception as e:
            logger.exception(f"Error updating flash: {e}")

        screen_w, screen_h = screen.get_size()

        # Particle and portrait updates
        try:
            if not gui_integration.settings.get("reduce_motion", False):
                particles.update(dt, screen_w, screen_h)
            portrait.update(dt)
            input_bar.update(dt)
        except Exception as e:
            logger.exception(f"Error in particle/portrait/input updates: {e}")

        # --- Draw ---
        renderer.render(screen, state, dialogue_rect)

    # Cleanup (graceful shutdown on Ctrl+C)
    with contextlib.suppress(Exception):
        display.save_state(gui_integration.settings)
        gui_integration.save_all_settings()
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
