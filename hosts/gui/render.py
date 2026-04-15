"""Render pipeline — composites all GUI layers to screen.

Each visual layer has its own draw call in explicit z-order: background →
particles → portrait → flash → banner → dialogue → border → quick actions →
input → debug log → scratchpad → overlays.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pygame

from .constants import DIALOGUE_X, INPUT_H, PORTRAIT_W
from .dialogue import draw_banner

if TYPE_CHECKING:
    from .alignment_gauges import AlignmentGaugePanel
    from .constants import Theme
    from .debug_log import DebugLog
    from .dialogue import DialogueHistory
    from .flash_effect import FlashEffect
    from .gossip_panel import GossipPanel
    from .gui_components_integration import GUIComponentsIntegration
    from .gui_state import GUIState
    from .input_bar import InputBar
    from .memory_viewer import MemoryViewerPanel
    from .onboarding_ui import OnboardingOverlay
    from .particles import ParticleSystem
    from .portrait import PortraitPanel
    from .quick_actions import QuickActionBar
    from .settings_overlay import SettingsOverlay

logger = logging.getLogger(__name__)


class RenderPipeline:
    """Composites all GUI layers to screen in the correct draw order."""

    def __init__(
        self,
        *,
        gui_integration: GUIComponentsIntegration,
        particles: ParticleSystem,
        portrait: PortraitPanel,
        flash: FlashEffect,
        history: DialogueHistory,
        input_bar: InputBar,
        quick_actions: QuickActionBar,
        debug_log: DebugLog,
        settings_overlay: SettingsOverlay,
        alignment_panel: AlignmentGaugePanel,
        gossip_panel: GossipPanel,
        memory_viewer: MemoryViewerPanel,
        onboarding: OnboardingOverlay,
        theme: Theme,
        agent_url: str,
    ) -> None:
        self.gui_integration = gui_integration
        self.particles = particles
        self.portrait = portrait
        self.flash = flash
        self.history = history
        self.input_bar = input_bar
        self.quick_actions = quick_actions
        self.debug_log = debug_log
        self.settings_overlay = settings_overlay
        self.alignment_panel = alignment_panel
        self.gossip_panel = gossip_panel
        self.memory_viewer = memory_viewer
        self.onboarding = onboarding
        self.theme = theme
        self.agent_url = agent_url

    def render(
        self,
        screen: pygame.Surface,
        state: GUIState,
        dialogue_rect: pygame.Rect,
    ) -> None:
        """Composite all layers to screen and flip."""
        try:
            screen_w, screen_h = screen.get_size()
            screen.fill(self.theme.dark_bg)

            # Background particles (full canvas)
            if not self.gui_integration.settings.get("reduce_motion", False):
                self.particles.draw(screen)

            # Left: portrait panel (with handoff flash)
            self.portrait.draw(screen)
            _, flash_alpha = self.flash.update(0.0)  # peek alpha without advancing time
            if flash_alpha > 0:
                flash_surf = pygame.Surface((PORTRAIT_W, screen_h), pygame.SRCALPHA)
                flash_surf.fill((255, 255, 255, flash_alpha))
                screen.blit(flash_surf, (0, 0))

            # Right: banner + dialogue history
            draw_banner(screen, state.connected, self.agent_url)
            self.history.draw(screen, dialogue_rect)

            # Right panel border
            pygame.draw.line(
                screen, self.theme.gold_dim, (DIALOGUE_X, 0), (DIALOGUE_X, screen_h - INPUT_H), 1
            )

            if not self.input_bar.processing:
                self.quick_actions.draw(screen, disabled=False)

            # Bottom: input
            self.input_bar.draw(screen)

            # Debug log panel (toggle in Settings > Gameplay)
            if self.gui_integration.settings.get("show_debug_logs", False):
                self.debug_log.draw(screen, dialogue_rect)

            # Scratchpad
            self.gui_integration.get_scratchpad().draw(screen, dialogue_rect)

            # Overlays (drawn last — on top of everything)
            self.settings_overlay.draw(screen)
            self.alignment_panel.draw(screen)
            self.gossip_panel.draw(screen)
            self.memory_viewer.draw(screen)
            self.onboarding.draw(screen)

            pygame.display.flip()
        except Exception as e:
            logger.exception("Exception during draw: %s", e)
