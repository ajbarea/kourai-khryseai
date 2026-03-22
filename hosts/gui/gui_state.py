"""Centralized mutable state for the Pygame GUI main loop.

Replaces scattered local variables and eliminates nonlocal declarations.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GUIState:
    """All mutable state that the main loop, queue handler, and event dispatcher share."""

    connected: bool = False
    current_agent: str = "hephaestus"
    last_agent: str = "hephaestus"
    result_agent: str = "hephaestus"
    typewriter_full_text: str = ""

    def switch_agent(self, new_agent: str) -> None:
        """Update agent tracking on handoff."""
        self.last_agent = self.current_agent
        self.current_agent = new_agent

    def track_specialist(self, agent: str) -> None:
        """Record which specialist produced the current result."""
        if agent != "hephaestus":
            self.result_agent = agent

    def reset_for_input(self, target: str | None = None) -> None:
        """Reset agent state when user submits new input."""
        agent = target or "hephaestus"
        self.current_agent = agent
        self.result_agent = agent
