"""Dialogue pacing controller — thinking pauses + per-mode response delays.

Pure timing logic with no GUI state dependencies; CLI and GUI share the
same ``PacingMode`` contract via this module.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import Enum


class PacingMode(Enum):
    """Dialogue pacing modes."""

    INSTANT = 0.0  # No delay
    FAST = 0.5  # Quick responses
    NORMAL = 1.5  # Natural conversation
    SLOW = 3.0  # Dramatic, light-novel style
    CUSTOM = -1  # User-defined


@dataclass
class PacingConfig:
    """Configuration for dialogue pacing."""

    mode: PacingMode = PacingMode.NORMAL
    custom_delay: float = 1.5  # Used if mode is CUSTOM
    min_chars_per_second: float = 50.0  # Reading speed
    enable_thinking_pause: bool = True  # Pause before response
    thinking_pause_duration: float = 0.5  # Seconds


class DialoguePacer:
    """Controls the timing of dialogue display and speech."""

    def __init__(self, config: PacingConfig | None = None):
        self.config = config or PacingConfig()
        self._last_response_time = time.monotonic()

    def get_delay_before_response(self) -> float:
        """Delay before showing agent response (thinking pause), seconds."""
        if not self.config.enable_thinking_pause:
            return 0.0
        return self.config.thinking_pause_duration

    def get_delay_between_responses(self) -> float:
        """Delay between consecutive agent responses, seconds."""
        mode = self.config.mode
        if mode == PacingMode.INSTANT:
            return 0.0
        if mode == PacingMode.FAST:
            return 0.5
        if mode == PacingMode.NORMAL:
            return 1.5
        if mode == PacingMode.SLOW:
            return 3.0
        return self.config.custom_delay

    def get_character_display_duration(self, text: str) -> float:
        """Time text should take to display/read, seconds."""
        char_count = len(text)
        return char_count / self.config.min_chars_per_second

    async def wait_before_response(self) -> None:
        delay = self.get_delay_before_response()
        if delay > 0:
            await asyncio.sleep(delay)

    async def wait_between_responses(self) -> None:
        delay = self.get_delay_between_responses()
        if delay > 0:
            await asyncio.sleep(delay)

    async def wait_for_display(self, text: str) -> None:
        duration = self.get_character_display_duration(text)
        if duration > 0:
            await asyncio.sleep(duration)

    def set_mode(self, mode: PacingMode, custom_delay: float | None = None) -> None:
        self.config.mode = mode
        if custom_delay is not None:
            self.config.custom_delay = custom_delay

    def set_thinking_pause(self, enabled: bool, duration: float | None = None) -> None:
        self.config.enable_thinking_pause = enabled
        if duration is not None:
            self.config.thinking_pause_duration = duration


__all__ = ["DialoguePacer", "PacingConfig", "PacingMode"]
