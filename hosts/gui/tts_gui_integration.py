"""Integration of TTS and dialogue pacing into the GUI.

Handles voice playback, pacing, and agent personality in the main dialogue loop.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

from .dialogue_pacing import DialoguePacer, PacingConfig, PacingMode
from .tts_engine import TTSEngine
from .tts_settings_config import TTSSettingsConfig

if TYPE_CHECKING:
    from kourai_common.tts_backend import TTSBackend

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import queue as _queue
    import threading

# ---------------------------------------------------------------------------
# Speech filtering — skip artifacts, commit messages, code, etc.
# ---------------------------------------------------------------------------

# Commit-message header prefixes (conventional commits)
_COMMIT_PREFIX_RE = re.compile(
    r"^\s*(?:feat|fix|docs|chore|refactor|test|perf|style|ci|build)\s*[\(\(]",
    re.IGNORECASE,
)
# Commit bullet points: "- Added ...", "- Fixed ...", etc.
_COMMIT_BULLET_RE = re.compile(
    r"^\s*-\s+(?:Added|Fixed|Updated|Removed|Renamed|Moved|Created|Deleted|Merged|"
    r"Refactored|Implemented|Resolved|Cleaned|Improved|Verified|Reverted|Bumped|"
    r"Replaced|Extracted|Migrated|Enabled|Disabled|Configured|Wrapped)\b",
    re.IGNORECASE,
)
# File-list lines: "Files: foo.py, bar.py"
_FILES_LINE_RE = re.compile(r"^\s*Files:\s", re.IGNORECASE)
# Fenced code block markers
_CODE_FENCE_RE = re.compile(r"^\s*```")
# Markdown headers
_MD_HEADER_RE = re.compile(r"^\s*#{1,6}\s")
# Section dividers
_DIVIDER_RE = re.compile(r"^\s*-{3,}\s*$")
# Blockquotes / GH alerts
_BLOCKQUOTE_RE = re.compile(r"^\s*>")
# Lines that are mostly non-word chars (tables, ascii art, paths, etc.)
_NON_PROSE_RE = re.compile(r"^[\s\W]*$")
# Diff-style lines
_DIFF_RE = re.compile(r"^\s*[+\-]{1,3}\s")
# Indented code (4+ spaces or tab)
_INDENTED_CODE_RE = re.compile(r"^(?:\t|    )\S")


def _is_artifact_line(line: str) -> bool:
    """Return True if a single line looks like an artifact rather than speech."""
    return bool(
        _COMMIT_PREFIX_RE.match(line)
        or _COMMIT_BULLET_RE.match(line)
        or _FILES_LINE_RE.match(line)
        or _CODE_FENCE_RE.match(line)
        or _MD_HEADER_RE.match(line)
        or _DIVIDER_RE.match(line)
        or _BLOCKQUOTE_RE.match(line)
        or _NON_PROSE_RE.match(line)
        or _DIFF_RE.match(line)
        or _INDENTED_CODE_RE.match(line)
    )


def should_speak(text: str) -> bool:
    """Return True if *any* line in `text` is conversational (not an artifact).

    Use for short status messages — if the entire text is artifact
    content, skip TTS.
    """
    if not text or not text.strip():
        return False
    return any(not _is_artifact_line(line) for line in text.splitlines() if line.strip())


_EMOTE_RE = re.compile(r"\*[^*]+\*")


def extract_speakable(text: str, max_chars: int = 500) -> str:
    """Return only the conversational (non-artifact) portions of `text`.

    For long result blocks, this strips out commit groups, code blocks,
    file lists, emote cues (*action*), etc. and returns a trimmed version
    suitable for TTS. Caps output at `max_chars` to avoid extremely long speech.
    """
    if not text:
        return ""

    speakable_lines: list[str] = []
    inside_code_block = False

    for line in text.splitlines():
        # Track fenced code blocks so we skip everything inside them
        if _CODE_FENCE_RE.match(line):
            inside_code_block = not inside_code_block
            continue
        if inside_code_block:
            continue

        if line.strip() and not _is_artifact_line(line):
            # Strip emote cues — these trigger SFX via emote_sfx.py, not speech
            cleaned = _EMOTE_RE.sub("", line).strip()
            if cleaned:
                speakable_lines.append(cleaned)

    result = " ".join(speakable_lines)
    if len(result) > max_chars:
        # Truncate at last sentence boundary within limit
        truncated = result[:max_chars]
        last_period = truncated.rfind(".")
        if last_period > max_chars // 2:
            result = truncated[: last_period + 1]
        else:
            result = truncated.rstrip() + "…"

    return result


class TTSGUIManager:
    """Manages TTS playback and dialogue pacing in the GUI."""

    def __init__(
        self,
        recv_q: _queue.Queue[dict],
        enable_tts: bool = True,
        pacing_mode: PacingMode = PacingMode.NORMAL,
        config: TTSSettingsConfig | None = None,
    ):
        """Initialize the TTS GUI manager.

        Args:
            recv_q: Queue for GUI events (from client).
            enable_tts: Whether to enable text-to-speech.
            pacing_mode: Initial dialogue pacing mode.
            config: TTS settings config (uses default if None).
        """
        self.recv_q = recv_q
        self.enable_tts = enable_tts
        self.config = config or TTSSettingsConfig()
        self.backend = self._create_backend_from_settings()
        self.tts_engine = TTSEngine(backend=self.backend) if enable_tts else None
        self.pacer = DialoguePacer(PacingConfig(mode=pacing_mode))
        self._tts_thread: threading.Thread | None = None
        self._current_agent: str | None = None
        logger.info(
            f"TTSGUIManager initialized: enable_tts={enable_tts}, pacing_mode={pacing_mode.name}, "
            f"backend={type(self.backend).__name__ if self.backend else 'None'}"
        )

    def _create_backend_from_settings(self) -> TTSBackend | None:
        """Create TTS backend based on settings.

        Returns:
            TTSBackend instance (Kokoro preferred, edge-tts fallback) or None if disabled.
        """
        backend_name = self.config.get("tts_backend", "kokoro")

        if backend_name == "disabled":
            logger.info("TTS backend set to 'disabled'")
            return None

        if backend_name == "edge":
            try:
                from kourai_common.tts_edge import EdgeTTSBackend

                logger.info("Using Edge-TTS backend")
                return EdgeTTSBackend()
            except ImportError:
                logger.error("Edge-TTS not installed")
                return None

        # Default to Kokoro, fall back to edge-tts
        try:
            from kourai_common.tts_kokoro import KokoroBackend

            logger.info("Using Kokoro-82M backend")
            return KokoroBackend()
        except ImportError:
            logger.warning("Kokoro not available, falling back to edge-tts")
            try:
                from kourai_common.tts_edge import EdgeTTSBackend

                return EdgeTTSBackend()
            except ImportError:
                logger.error("Neither Kokoro nor edge-tts available")
                return None

    def set_backend(self, backend_name: str) -> None:
        """Switch to a different TTS backend at runtime.

        Args:
            backend_name: "kokoro", "edge", or "disabled".
        """
        if backend_name not in ("kokoro", "edge", "disabled"):
            logger.warning(f"Invalid backend name: {backend_name}")
            return

        self.config.set("tts_backend", backend_name)
        self.config.save()
        old_backend = type(self.backend).__name__ if self.backend else "None"

        self.backend = self._create_backend_from_settings()

        if self.tts_engine:
            self.tts_engine.backend = self.backend

        new_backend = type(self.backend).__name__ if self.backend else "None"
        logger.info(f"TTS backend switched: {old_backend} → {new_backend}")

    def set_tts_enabled(self, enabled: bool) -> None:
        """Enable or disable TTS."""
        self.enable_tts = enabled
        if enabled and self.tts_engine is None:
            self.backend = self._create_backend_from_settings()
            self.tts_engine = TTSEngine(backend=self.backend)
            logger.info("TTS enabled")
        elif not enabled and self.tts_engine:
            self.tts_engine.stop()
            logger.info("TTS disabled")

    def set_pacing_mode(self, mode: PacingMode) -> None:
        """Change dialogue pacing mode."""
        self.pacer.set_mode(mode)
        logger.debug(f"Pacing mode changed to {mode.name}")

    def set_current_agent(self, agent_name: str) -> None:
        """Set the current speaking agent."""
        self._current_agent = agent_name
        logger.debug(f"Current agent set to {agent_name}")

    async def process_dialogue_event(self, event: dict) -> None:
        """Process a dialogue event with TTS and pacing.

        Args:
            event: Event dict from client (status, result, etc).
        """
        event_type = event.get("type")
        logger.debug(f"Processing dialogue event: type={event_type}")

        if event_type == "status":
            # Agent is thinking/processing
            text = event.get("text", "")
            if text:
                logger.debug(f"Status event with text: {text[:50]}...")
                await self.pacer.wait_before_response()
                if self.enable_tts and self.tts_engine:
                    await self._speak_async(text, self._current_agent)

        elif event_type == "result":
            # Final response
            text = event.get("text", "")
            if text:
                logger.debug(f"Result event with text: {text[:50]}...")
                await self.pacer.wait_between_responses()
                if self.enable_tts and self.tts_engine:
                    await self._speak_async(text, self._current_agent)

    async def _speak_async(
        self,
        text: str,
        agent_name: str | None = None,
        speed: float | None = None,
        pitch: float | None = None,
    ) -> None:
        """Speak text asynchronously in a thread pool.

        Args:
            text: Text to speak.
            agent_name: Agent name for voice selection.
            speed: Voice speed override.
            pitch: Voice pitch override.
        """
        if not self.tts_engine:
            logger.warning("TTS engine not initialized, skipping _speak_async")
            return

        logger.info(f"_speak_async: agent={agent_name}, text_len={len(text)}")
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                self.tts_engine.speak_sync,
                text,
                agent_name,
                None,  # voice_key (use auto-detection)
                speed,
                pitch,
            )
        except Exception as e:
            logger.error(f"_speak_async error: {e}", exc_info=True)

    def cleanup(self) -> None:
        """Clean up TTS resources."""
        logger.info("TTSGUIManager cleanup")
        if self.tts_engine:
            self.tts_engine.stop()
            self.tts_engine.cleanup()


class TTSSettingsPanel:
    """UI panel for TTS and pacing settings."""

    def __init__(self, manager: TTSGUIManager):
        """Initialize settings panel.

        Args:
            manager: TTSGUIManager instance to control.
        """
        self.manager = manager

    def get_settings_dict(self) -> dict:
        """Get current TTS settings as dict."""
        return {
            "tts_enabled": self.manager.enable_tts,
            "master_volume": self.manager.tts_engine.master_volume
            if self.manager.tts_engine
            else 0.8,
            "enable_effects": self.manager.tts_engine.enable_effects
            if self.manager.tts_engine
            else True,
            "pacing_mode": self.manager.pacer.config.mode.name,
            "thinking_pause": self.manager.pacer.config.enable_thinking_pause,
            "thinking_pause_duration": self.manager.pacer.config.thinking_pause_duration,
            "min_chars_per_second": self.manager.pacer.config.min_chars_per_second,
        }

    def apply_settings(self, settings: dict) -> None:
        """Apply TTS settings from dict.

        Args:
            settings: Settings dict with keys like 'tts_enabled', 'master_volume', etc.
        """
        if "tts_enabled" in settings:
            self.manager.set_tts_enabled(settings["tts_enabled"])

        if "master_volume" in settings and self.manager.tts_engine:
            self.manager.tts_engine.set_master_volume(settings["master_volume"])

        if "enable_effects" in settings and self.manager.tts_engine:
            self.manager.tts_engine.enable_effects = settings["enable_effects"]

        if "pacing_mode" in settings:
            mode_name = settings["pacing_mode"]
            try:
                mode = PacingMode[mode_name]
                self.manager.set_pacing_mode(mode)
            except KeyError:
                pass

        if "thinking_pause" in settings or "thinking_pause_duration" in settings:
            enabled = settings.get(
                "thinking_pause", self.manager.pacer.config.enable_thinking_pause
            )
            duration = settings.get(
                "thinking_pause_duration", self.manager.pacer.config.thinking_pause_duration
            )
            self.manager.pacer.set_thinking_pause(enabled, duration)

        if "min_chars_per_second" in settings:
            self.manager.pacer.config.min_chars_per_second = settings["min_chars_per_second"]
