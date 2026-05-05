"""Typewriter effect manager for character-by-character text display.

Manages character-by-character text display with delta time for consistent
animation speed regardless of frame rate. Supports skip functionality,
speed settings (10ms to 100ms), pause/resume, and motion sensitivity.
"""

from __future__ import annotations


class TypewriterManager:
    """Manages character-by-character text display with delta time.

    Displays text one character at a time using delta time for consistent
    animation speed regardless of frame rate. Supports skip, pause/resume,
    and motion sensitivity settings.

    Attributes:
        min_speed_ms: Minimum speed in milliseconds per character (default 10).
        max_speed_ms: Maximum speed in milliseconds per character (default 100).
        current_speed_ms: Current speed setting in milliseconds per character.
        active: Whether the typewriter effect is currently active.
        paused: Whether the typewriter effect is currently paused.
        current_text: The full text being displayed.
        displayed_chars: Number of characters currently displayed.
        motion_sensitivity_enabled: Whether motion sensitivity is enabled.
    """

    def __init__(
        self,
        min_speed_ms: int = 10,
        max_speed_ms: int = 100,
        motion_sensitivity_enabled: bool = False,
    ) -> None:
        """Initialize TypewriterManager.

        Args:
            min_speed_ms: Minimum speed in milliseconds per character.
            max_speed_ms: Maximum speed in milliseconds per character.
            motion_sensitivity_enabled: Whether motion sensitivity is enabled.
        """
        self.min_speed_ms = min_speed_ms
        self.max_speed_ms = max_speed_ms
        self.current_speed_ms = 30  # Default speed
        self.active = False
        self.paused = False
        self.current_text = ""
        self.displayed_chars = 0
        self.motion_sensitivity_enabled = motion_sensitivity_enabled
        self._timer = 0.0  # Accumulated time in milliseconds
        self._skip_requested = False
        # M20 sub-task 2 (Tier 1 word-paced mode): when True, dt-based
        # advance is disabled and the cursor only moves when
        # advance_word() is called from the TTS engine's on_word
        # trampoline. _word_end_indices maps word ordinal → end
        # character position in current_text (set by start_word_paced).
        self._word_paced = False
        self._word_end_indices: list[int] = []
        self._words_revealed = 0
        # M20 sub-task 2 polish: while True, get_displayed_text /
        # update return a single-ellipsis placeholder so the dialogue
        # panel shows the player visible feedback during the
        # ~3s Kokoro synthesis-wait window before the first on_word
        # callback fires. Cleared on first advance_word, on
        # flush_remaining / reset, or by clear_pending_audio().
        self._pending_audio = False

    def start(self, text: str, speed_ms: int | None = None) -> None:
        """Start typewriter effect for text.

        Begins displaying the given text character-by-character using the
        specified speed or the current speed setting.

        Args:
            text: The text to display.
            speed_ms: Speed in milliseconds per character. If None, uses current_speed_ms.
        """
        self.current_text = text
        self.displayed_chars = 0
        self._timer = 0.0
        self._skip_requested = False
        self.paused = False
        self.active = True
        self._word_paced = False
        self._word_end_indices = []
        self._words_revealed = 0
        self._pending_audio = False

        if speed_ms is not None:
            # Clamp speed to valid range
            self.current_speed_ms = max(self.min_speed_ms, min(speed_ms, self.max_speed_ms))

        # If motion sensitivity is enabled, skip the effect entirely
        if self.motion_sensitivity_enabled:
            self.displayed_chars = len(self.current_text)
            self.active = False

    def start_word_paced(self, text: str) -> None:
        """Start typewriter in M20 sub-task 2 Tier 1 word-paced mode.

        The cursor stays at 0 until :meth:`advance_word` is called (by
        the TTS engine's ``on_word`` trampoline). Each call advances
        the cursor to the end of the next source-text word + any
        trailing whitespace. Falls back to the time-based pace if
        advance_word never fires (engine error, audio unavailable) —
        callers should drive a Tier-2 finally block to flush the
        remaining text in that case.

        Motion sensitivity still skips the animation entirely.
        """
        self.current_text = text
        self.displayed_chars = 0
        self._timer = 0.0
        self._skip_requested = False
        self.paused = False
        self.active = True
        self._word_paced = True
        self._word_end_indices = _compute_word_end_indices(text)
        self._words_revealed = 0
        self._pending_audio = False

        if self.motion_sensitivity_enabled:
            self.displayed_chars = len(self.current_text)
            self.active = False
            return

    def advance_word(self) -> None:
        """Reveal the next source-text word in word-paced mode.

        No-op if not in word-paced mode, if the typewriter is paused,
        or if all words are already revealed. Idempotent at the end of
        text — extra TTS on_word fires past the source-word count are
        safely ignored. Clears the pending-audio placeholder on the
        first fire (audio has clearly started).
        """
        if not self._word_paced or self.paused or not self.active:
            return
        if self._words_revealed >= len(self._word_end_indices):
            return
        end_idx = self._word_end_indices[self._words_revealed]
        # Include trailing whitespace so the cursor lands at the start
        # of the NEXT word, not on the space after the previous one.
        while end_idx < len(self.current_text) and self.current_text[end_idx].isspace():
            end_idx += 1
        self.displayed_chars = end_idx
        self._words_revealed += 1
        self._pending_audio = False
        if self.displayed_chars >= len(self.current_text):
            self.active = False
            self.displayed_chars = len(self.current_text)

    def flush_remaining(self) -> None:
        """Reveal the rest of the text immediately.

        Called from the TTS finally block when audio playback ends
        before all words fired (synthesis error, end-of-audio fallback).
        Mirrors the CLI's deferred-render fallback so dialogue is never
        partially-revealed forever.
        """
        if not self.active:
            return
        self.displayed_chars = len(self.current_text)
        self.active = False
        self._pending_audio = False

    def set_pending_audio(self) -> None:
        """Render a single-ellipsis placeholder until the first
        ``advance_word`` fires (or ``clear_pending_audio`` is called).

        No-op outside word-paced mode, when the typewriter is inactive,
        when motion-sensitivity already revealed the full text, or when
        the cursor has already moved past zero (race / late call —
        never mask real text with a placeholder).
        """
        if not self._word_paced or not self.active:
            return
        if self.motion_sensitivity_enabled:
            return
        if self.displayed_chars > 0:
            return
        self._pending_audio = True

    def clear_pending_audio(self) -> None:
        """Drop the synthesis-indicator placeholder.

        Called from the TTS engine's ``on_audio_start`` trampoline so
        the dialogue body returns to its real state (still empty if no
        word has fired yet) the moment the engine begins playback.
        """
        self._pending_audio = False

    def update(self, dt: float) -> str:
        """Update effect using delta time and return current displayed text.

        Advances the typewriter effect by the given delta time and returns
        the currently displayed text. Uses delta time for consistent animation
        speed regardless of frame rate.

        Args:
            dt: Delta time in seconds since last update.

        Returns:
            The currently displayed text (partial or full).
        """
        if not self.active or self.paused:
            if self._pending_audio and self.displayed_chars == 0:
                return "…"
            return self.current_text[: self.displayed_chars]

        # M20 sub-task 2 Tier 1: word-paced mode ignores dt — the cursor
        # only moves when advance_word() fires from the TTS trampoline.
        if self._word_paced:
            if self._pending_audio and self.displayed_chars == 0:
                return "…"
            return self.current_text[: self.displayed_chars]

        # Convert dt from seconds to milliseconds
        dt_ms = dt * 1000.0
        self._timer += dt_ms

        # Calculate how many characters should be displayed
        chars_to_display = int(self._timer / self.current_speed_ms)

        # Update displayed characters
        self.displayed_chars = min(chars_to_display, len(self.current_text))

        # Check if effect is complete
        if self.displayed_chars >= len(self.current_text):
            self.active = False
            self.displayed_chars = len(self.current_text)

        return self.current_text[: self.displayed_chars]

    def skip(self) -> None:
        """Skip to full text immediately.

        Immediately displays the full text and marks the effect as complete.
        """
        if self.active:
            self.displayed_chars = len(self.current_text)
            self.active = False
            self._skip_requested = True

    def is_complete(self) -> bool:
        """Check if effect has finished.

        Returns:
            True if the effect has finished displaying all characters, False otherwise.
        """
        return not self.active

    def pause(self) -> None:
        """Pause the effect.

        Pauses the typewriter effect without resetting progress. The effect
        can be resumed with resume().
        """
        if self.active:
            self.paused = True

    def resume(self) -> None:
        """Resume the effect.

        Resumes a paused typewriter effect from where it was paused.
        """
        if self.active and self.paused:
            self.paused = False

    def set_motion_sensitivity(self, enabled: bool) -> None:
        """Set motion sensitivity setting.

        When enabled, the typewriter effect is disabled and text is displayed
        immediately to accommodate users with motion sensitivity preferences.

        Args:
            enabled: Whether motion sensitivity is enabled.
        """
        self.motion_sensitivity_enabled = enabled

    def set_speed(self, speed_ms: int) -> None:
        """Set the typewriter speed.

        Sets the speed for new typewriter effects. The speed is clamped to
        the valid range [min_speed_ms, max_speed_ms].

        Args:
            speed_ms: Speed in milliseconds per character.
        """
        self.current_speed_ms = max(self.min_speed_ms, min(speed_ms, self.max_speed_ms))

    def get_displayed_text(self) -> str:
        """Get the currently displayed text.

        Returns:
            The text that should currently be displayed.
        """
        if self._pending_audio and self.displayed_chars == 0:
            return "…"
        return self.current_text[: self.displayed_chars]

    def reset(self) -> None:
        """Reset the typewriter effect.

        Stops the effect and resets all state to initial values.
        """
        self.active = False
        self.paused = False
        self.current_text = ""
        self.displayed_chars = 0
        self._timer = 0.0
        self._skip_requested = False
        self._word_paced = False
        self._word_end_indices = []
        self._words_revealed = 0
        self._pending_audio = False


def _compute_word_end_indices(text: str) -> list[int]:
    """Build the char-position list of word boundaries for word-paced mode.

    Returns the index immediately after each whitespace-delimited word.
    Used by :meth:`TypewriterManager.start_word_paced` so each
    ``advance_word`` call lands the cursor at end-of-current-word.

    Empty / whitespace-only input → empty list (no words to advance).
    """
    indices: list[int] = []
    in_word = False
    for j, c in enumerate(text):
        if c.isspace():
            if in_word:
                indices.append(j)
                in_word = False
        else:
            in_word = True
    if in_word:
        indices.append(len(text))
    return indices
