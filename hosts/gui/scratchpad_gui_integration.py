"""Integration of the Scratchpad with the main GUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .scratchpad import Scratchpad

if TYPE_CHECKING:
    import pygame


class ScratchpadGUIIntegration:
    """Manages integration of the scratchpad with the main GUI."""

    def __init__(self, gui_instance) -> None:
        """Initialize integration with GUI instance."""
        self.gui = gui_instance
        self.scratchpad = Scratchpad()

    def add_plan(self, text: str, agent: str) -> None:
        """Add a plan to the selected agent's scratchpad."""
        self.scratchpad.append(agent, text)

    def set_active_agent(self, agent: str) -> None:
        """Switch the view to the specified agent."""
        self.scratchpad.set_agent(agent)

    def toggle(self) -> None:
        """Toggle the visibility of the scratchpad."""
        self.scratchpad.toggle()

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Process mouse events. Returns True if event was consumed."""
        return self.scratchpad.handle_event(event)

    def draw(self, screen: pygame.Surface, target_rect: pygame.Rect) -> None:
        """Draw the scratchpad."""
        self.scratchpad.draw(screen, target_rect)
