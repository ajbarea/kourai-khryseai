"""Subsystem loader — initializes all GUI subsystems during the loading screen.

Yields (progress, description) tuples so the loading screen can animate.
Returns a typed Subsystems dataclass instead of a raw dict.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import secrets
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .alignment_gauges import AlignmentGaugePanel
from .client import GuiClient
from .debug_log import DebugLog
from .dialogue import DialogueHistory
from .dialogue_pacing import PacingMode
from .flash_effect import FlashEffect
from .gossip_panel import GossipPanel
from .gui_components_integration import GUIComponentsIntegration
from .input_bar import InputBar
from .maidens import AGENTS
from .memory_viewer import MemoryViewerPanel
from .onboarding_ui import OnboardingOverlay
from .particles import ParticleSystem
from .portrait import PortraitPanel
from .quick_actions import QuickActionBar
from .settings_overlay import SettingsOverlay
from .tts_gui_integration import TTSGUIManager
from .typewriter import TypewriterManager

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from kourai_common.audio import AudioManager

logger = logging.getLogger(__name__)


@dataclass
class Subsystems:
    """All initialized GUI subsystems — typed alternative to a raw dict."""

    gui_integration: GUIComponentsIntegration
    settings_overlay: SettingsOverlay
    alignment_panel: AlignmentGaugePanel
    gossip_panel: GossipPanel
    onboarding: OnboardingOverlay
    memory_viewer: MemoryViewerPanel
    particles: ParticleSystem
    portrait: PortraitPanel
    history: DialogueHistory
    debug_log: DebugLog
    input_bar: InputBar
    typewriter: TypewriterManager
    flash: FlashEffect
    quick_actions: QuickActionBar
    send_q: queue.Queue[tuple[str, str] | None]
    recv_q: queue.Queue[dict]
    tts_manager: TTSGUIManager


def load_subsystems(
    screen_size: tuple[int, int],
    settings_path: Path,
    audio_manager: AudioManager,
    agent_url: str | None,
    queues_hook: dict,
) -> Generator[tuple[float, str], None, Subsystems]:
    """Generator that initializes all GUI subsystems one step at a time.

    Yields (progress, description) tuples. Each ``next()`` call does
    one unit of work on the main thread (safe for Surface creation).

    After the generator is exhausted, call ``.value`` on the StopIteration
    to get the Subsystems dataclass, or use the helper ``run_loader()``.

    Args:
        screen_size: Current screen (width, height).
        settings_path: Path to settings JSON file.
        audio_manager: Already-initialized audio manager.
        agent_url: Hephaestus agent URL (or None for default).
        queues_hook: Mutable dict to expose send_q for signal handler access.
    """
    total_steps = 14
    step = 0
    screen_w, screen_h = screen_size
    logger.debug(f"Starting subsystem load: {screen_w}x{screen_h}")

    # 1. GUI integration (settings, font scaler, etc.)
    step += 1
    try:
        logger.debug("Initializing GUI components integration...")
        gui_integration = GUIComponentsIntegration(None, settings_path)
        logger.debug("GUI integration OK")
    except Exception:
        logger.exception("Failed to initialize GUI integration")
        raise
    yield step / total_steps, "Loading settings…"

    # 2. Wire audio volumes from saved settings
    step += 1
    try:
        logger.debug("Configuring audio volumes...")
        audio_manager.set_music_volume(gui_integration.settings.get("music_volume", 0.5))
        audio_manager.set_ambient_volume(gui_integration.settings.get("ambient_volume", 0.5))
        audio_manager.set_voice_volume(gui_integration.settings.get("voice_volume", 1.0))
        audio_manager.set_sfx_volume(gui_integration.settings.get("sfx_volume", 0.8))
        logger.debug("Audio volumes OK")
    except Exception:
        logger.exception("Failed to configure audio")
        raise
    yield step / total_steps, "Configuring audio…"

    # 3. Settings overlay
    step += 1
    try:
        logger.debug("Creating settings overlay...")
        settings_overlay = SettingsOverlay(screen_w, screen_h, gui_integration, audio_manager)
        logger.debug("Settings overlay OK")
    except Exception:
        logger.exception("Failed to create settings overlay")
        raise
    yield step / total_steps, "Building settings UI…"

    # 4. Alignment gauge panel
    step += 1
    try:
        logger.debug("Creating alignment panel...")
        alignment_panel = AlignmentGaugePanel(screen_w, screen_h)
        logger.debug("Alignment panel OK")
    except Exception:
        logger.exception("Failed to create alignment panel")
        raise
    yield step / total_steps, "Forging alignment gauges…"

    # 5. Gossip side panel
    step += 1
    try:
        logger.debug("Creating gossip panel...")
        gossip_panel = GossipPanel(screen_w, screen_h)
        logger.debug("Gossip panel OK")
    except Exception:
        logger.exception("Failed to create gossip panel")
        raise
    yield step / total_steps, "Opening gossip channels…"

    # 6. Onboarding overlay
    step += 1
    try:
        logger.debug("Creating onboarding overlay...")
        onboarding = OnboardingOverlay(screen_w, screen_h)
        logger.debug("Onboarding overlay OK")
    except Exception:
        logger.exception("Failed to create onboarding overlay")
        raise
    yield step / total_steps, "Preparing introductions…"

    # 7. Memory viewer panel
    step += 1
    try:
        logger.debug("Creating memory viewer...")
        memory_viewer = MemoryViewerPanel(screen_w, screen_h)
        logger.debug("Memory viewer OK")
    except Exception:
        logger.exception("Failed to create memory viewer")
        raise
    yield step / total_steps, "Cataloging memories…"

    # 8. Particle system
    step += 1
    try:
        logger.debug("Creating particle system...")
        particles = ParticleSystem()
        logger.debug("Particle system OK")
    except Exception:
        logger.exception("Failed to create particle system")
        raise
    yield step / total_steps, "Igniting forge embers…"

    # 9. Portrait panel + avatar pre-cache
    step += 1
    try:
        logger.debug("Creating portrait panel...")
        portrait = PortraitPanel()
        heph_quotes = AGENTS["hephaestus"].get("user_quotes", [])
        portrait.current_quote = secrets.choice(heph_quotes) if heph_quotes else ""
        logger.debug("Portrait panel OK")
    except Exception:
        logger.exception("Failed to create portrait panel")
        raise
    yield step / total_steps, "Summoning the maidens…"

    # 10. Dialogue history + input bar + effects + debug log
    step += 1
    try:
        logger.debug("Creating dialogue, input, and effects...")
        history = DialogueHistory()
        input_bar = InputBar()
        debug_log = DebugLog()
        reduce_motion = gui_integration.settings.get("reduce_motion", False)
        typewriter = TypewriterManager(motion_sensitivity_enabled=reduce_motion)
        flash = FlashEffect()
        logger.debug("Dialogue/input/effects OK")
    except Exception:
        logger.exception("Failed to create dialogue/input/effects")
        raise
    yield step / total_steps, "Preparing the forge…"

    # 11. Quick actions
    step += 1
    try:
        logger.debug("Creating quick actions...")
        quick_actions = QuickActionBar()
        logger.debug("Quick actions OK")
    except Exception:
        logger.exception("Failed to create quick actions")
        raise
    yield step / total_steps, "Forging quick actions…"

    # 12. A2A client thread
    step += 1
    try:
        logger.debug(f"Starting A2A client (agent_url={agent_url})...")
        send_q: queue.Queue[tuple[str, str] | None] = queue.Queue()
        recv_q: queue.Queue[dict] = queue.Queue()
        queues_hook["send_q"] = send_q
        client = GuiClient(send_q, recv_q, agent_url)

        def _run_client() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                logger.debug("A2A client event loop starting")
                loop.run_until_complete(client.run())
            except Exception:
                logger.exception("A2A client error")
            finally:
                loop.close()

        _thread = threading.Thread(target=_run_client, daemon=True)
        _thread.start()
        logger.debug("A2A client thread OK")
    except Exception:
        logger.exception("Failed to start A2A client")
        raise
    yield step / total_steps, "Connecting to Hephaestus…"

    # 13. Audio ready (music deferred until player presses start)
    step += 1
    try:
        logger.debug("Audio ready")
    except Exception:
        logger.exception("Audio ready check failed")
        raise
    yield step / total_steps, "Tuning the forge…"

    # 14. TTS manager
    step += 1
    try:
        logger.debug("Creating TTS manager...")
        tts_manager = TTSGUIManager(recv_q, enable_tts=True, pacing_mode=PacingMode.NORMAL)
        tts_manager.set_current_agent("hephaestus")
        logger.debug("TTS manager OK")
    except Exception:
        logger.exception("Failed to create TTS manager")
        raise
    yield step / total_steps, "Ready"

    # Return the typed result via StopIteration.value
    logger.debug("All subsystems loaded successfully")
    return Subsystems(
        gui_integration=gui_integration,
        settings_overlay=settings_overlay,
        alignment_panel=alignment_panel,
        gossip_panel=gossip_panel,
        onboarding=onboarding,
        memory_viewer=memory_viewer,
        particles=particles,
        portrait=portrait,
        history=history,
        debug_log=debug_log,
        input_bar=input_bar,
        typewriter=typewriter,
        flash=flash,
        quick_actions=quick_actions,
        send_q=send_q,
        recv_q=recv_q,
        tts_manager=tts_manager,
    )


def run_loader(
    screen_size: tuple[int, int],
    settings_path: Path,
    audio_manager: AudioManager,
    agent_url: str | None,
    queues_hook: dict,
) -> Generator[tuple[float, str], None, Subsystems]:
    """Create the loader generator. The caller iterates it for the loading
    screen, then retrieves the Subsystems from the final StopIteration."""
    return load_subsystems(screen_size, settings_path, audio_manager, agent_url, queues_hook)
