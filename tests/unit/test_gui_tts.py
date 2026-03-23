"""Tests for TTS GUI integration and TTS settings config.

Covers:
- hosts/gui/tts_gui_integration.py (_is_artifact_line, should_speak,
  extract_speakable, TTSGUIManager, TTSSettingsPanel)
- hosts/gui/tts_settings_config.py (TTSSettingsConfig)

"""

from __future__ import annotations

import json
import queue
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("pygame")

# ---------------------------------------------------------------------------
# Module-level mock for TTSEngine so we never import pygame/edge_tts
# ---------------------------------------------------------------------------

_MockTTSEngine = MagicMock


@pytest.fixture(autouse=True)
def _patch_tts_engine():
    """Replace TTSEngine with a lightweight mock across all tests."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.master_volume = 0.8
    mock_instance.enable_effects = True
    mock_cls.return_value = mock_instance

    with patch("hosts.gui.tts_gui_integration.TTSEngine", mock_cls):
        yield mock_cls, mock_instance


# ---------------------------------------------------------------------------
# Import SUT *after* the autouse fixture is declared so that the module-level
# import of TTSEngine inside tts_gui_integration is intercepted at use time.
# We import the module objects lazily inside each test class / function so the
# patch is active.
# ---------------------------------------------------------------------------


def _import_integration():
    from hosts.gui.tts_gui_integration import (
        TTSGUIManager,
        TTSSettingsPanel,
        _is_artifact_line,
        extract_speakable,
        should_speak,
    )

    return (
        _is_artifact_line,
        should_speak,
        extract_speakable,
        TTSGUIManager,
        TTSSettingsPanel,
    )


def _import_config():
    from hosts.gui.tts_settings_config import TTSSettingsConfig

    return TTSSettingsConfig


# ===================================================================
# 1. _is_artifact_line
# ===================================================================


class TestIsArtifactLine:
    """Verify that _is_artifact_line correctly classifies individual lines."""

    # -- Lines that ARE artifacts (should return True) --

    @pytest.mark.parametrize(
        "line",
        [
            "feat(auth): add login",
            "fix(core): resolve crash",
            "docs(readme): update install steps",
            "chore(deps): bump lodash",
            "refactor(api): simplify handler",
            "test(unit): add coverage",
            "perf(db): optimize query",
            "style(lint): reformat files",
            "ci(gh): add workflow",
            "build(docker): multi-stage",
        ],
        ids=[
            "feat-prefix",
            "fix-prefix",
            "docs-prefix",
            "chore-prefix",
            "refactor-prefix",
            "test-prefix",
            "perf-prefix",
            "style-prefix",
            "ci-prefix",
            "build-prefix",
        ],
    )
    def test_commit_prefixes(self, line: str) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line(line) is True

    @pytest.mark.parametrize(
        "line",
        [
            "- Added new feature",
            "- Fixed memory leak",
            "- Updated dependencies",
            "- Removed dead code",
            "- Renamed variables",
            "- Moved files to src/",
            "- Created migration script",
            "- Deleted temp files",
            "- Merged feature branch",
            "- Refactored handler logic",
            "- Implemented caching",
            "- Resolved merge conflict",
            "- Cleaned up imports",
            "- Improved performance",
            "- Verified test suite",
            "- Reverted last commit",
            "- Bumped version to 2.0",
            "- Replaced old API",
            "- Extracted helper function",
            "- Migrated to new schema",
            "- Enabled strict mode",
            "- Disabled debug logging",
            "- Configured CI pipeline",
            "- Wrapped error handler",
        ],
        ids=lambda line: line[2:].split()[0].lower(),
    )
    def test_commit_bullets(self, line: str) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line(line) is True

    def test_code_fence_python(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("```python") is True

    def test_code_fence_bare(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("```") is True

    def test_code_fence_indented(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("  ```js") is True

    def test_markdown_header(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("## Section") is True

    def test_markdown_header_h1(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("# Title") is True

    def test_markdown_header_h6(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("###### Deep heading") is True

    def test_divider_triple_dash(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("---") is True

    def test_divider_long(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("----------") is True

    def test_blockquote(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("> quote") is True

    def test_blockquote_nested(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("> > nested") is True

    def test_diff_added(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("+ added line") is True

    def test_diff_removed(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("- removed line") is True

    def test_diff_triple_plus(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("+++ b/file.py") is True

    def test_indented_code_spaces(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("    code_here()") is True

    def test_indented_code_tab(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("\tcode_here()") is True

    def test_files_line(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("Files: foo.py, bar.py") is True

    def test_non_prose_symbols(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("  |---|---| ") is True

    def test_empty_line(self) -> None:
        """Empty/whitespace-only lines match _NON_PROSE_RE."""
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("") is True

    def test_whitespace_only(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("   ") is True

    # -- Lines that are NOT artifacts (normal prose, should return False) --

    def test_normal_prose(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("The build completed successfully.") is False

    def test_conversational(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("I have finished refactoring the module.") is False

    def test_question(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("Would you like me to run the tests?") is False

    def test_short_sentence(self) -> None:
        _is_artifact_line, *_ = _import_integration()
        assert _is_artifact_line("Done.") is False


# ===================================================================
# 2. should_speak
# ===================================================================


class TestShouldSpeak:
    """Verify should_speak filtering logic."""

    def test_empty_string(self) -> None:
        _, should_speak, *_ = _import_integration()
        assert should_speak("") is False

    def test_whitespace_only(self) -> None:
        _, should_speak, *_ = _import_integration()
        assert should_speak("   \n  \n  ") is False

    def test_none_like_empty(self) -> None:
        """Falsy string."""
        _, should_speak, *_ = _import_integration()
        assert should_speak("") is False

    def test_all_artifact_text(self) -> None:
        """Text composed entirely of artifact lines should not be spoken."""
        _, should_speak, *_ = _import_integration()
        # Each line must individually match an artifact pattern
        text = "```python\n    pass\n```"
        assert should_speak(text) is False

    def test_all_commit_bullets(self) -> None:
        _, should_speak, *_ = _import_integration()
        text = "- Added feature\n- Fixed bug\n- Updated docs"
        assert should_speak(text) is False

    def test_mixed_text(self) -> None:
        """Mixed artifact + conversational should return True."""
        _, should_speak, *_ = _import_integration()
        text = "Here is what I did:\n- Added feature\n- Fixed bug\nLet me know if you need more."
        assert should_speak(text) is True

    def test_pure_conversational(self) -> None:
        _, should_speak, *_ = _import_integration()
        text = "I have completed the task. Everything looks good."
        assert should_speak(text) is True

    def test_single_prose_line(self) -> None:
        _, should_speak, *_ = _import_integration()
        assert should_speak("All tests pass.") is True

    def test_only_dividers_and_headers(self) -> None:
        _, should_speak, *_ = _import_integration()
        text = "## Results\n---\n> Note"
        assert should_speak(text) is False


# ===================================================================
# 3. extract_speakable
# ===================================================================


class TestExtractSpeakable:
    """Verify extract_speakable strips artifacts and respects limits."""

    def test_empty_string(self) -> None:
        *_, extract_speakable, _, _ = _import_integration()
        assert extract_speakable("") == ""

    def test_none_returns_empty(self) -> None:
        *_, extract_speakable, _, _ = _import_integration()
        assert extract_speakable("") == ""

    def test_code_blocks_stripped(self) -> None:
        """Fenced code blocks (and their contents) should be removed."""
        *_, extract_speakable, _, _ = _import_integration()
        text = "Here is the code:\n```python\ndef foo():\n    return 42\n```\nDone."
        result = extract_speakable(text)
        assert "def foo" not in result
        assert "Done." in result
        assert "Here is the code:" in result

    def test_commit_groups_stripped(self) -> None:
        *_, extract_speakable, _, _ = _import_integration()
        text = "Changes made:\nfeat(auth): add login\n- Added new feature\nAll done."
        result = extract_speakable(text)
        assert "feat(auth)" not in result
        assert "Added new feature" not in result
        assert "All done." in result

    def test_emotes_stripped(self) -> None:
        """Emote cues like *smiles* should be removed."""
        *_, extract_speakable, _, _ = _import_integration()
        text = "*adjusts glasses* I have completed the analysis."
        result = extract_speakable(text)
        assert "adjusts glasses" not in result
        assert "I have completed the analysis." in result

    def test_emote_only_line(self) -> None:
        """A line that is only an emote should result in nothing speakable from it."""
        *_, extract_speakable, _, _ = _import_integration()
        text = "*smiles warmly*"
        result = extract_speakable(text)
        assert result == ""

    def test_long_text_truncation(self) -> None:
        """Text > 500 chars should be truncated."""
        *_, extract_speakable, _, _ = _import_integration()
        # Build text that's well over 500 chars of pure prose
        sentence = "This is a moderately long sentence for testing purposes. "
        long_text = sentence * 20  # ~1140 chars
        result = extract_speakable(long_text)
        assert len(result) <= 500 + 5  # small margin for ellipsis

    def test_sentence_boundary_truncation(self) -> None:
        """Truncation should prefer sentence boundaries (period) when possible."""
        *_, extract_speakable, _, _ = _import_integration()
        # Create text with a period right before the 500-char mark
        base = "A" * 300 + ". " + "B" * 250  # ~552 chars, period at pos 300
        result = extract_speakable(base)
        # Should truncate at the period since 300 > 500//2 = 250
        assert result.endswith(".")

    def test_truncation_no_good_period(self) -> None:
        """When no period is past the halfway point, use ellipsis."""
        *_, extract_speakable, _, _ = _import_integration()
        # Period very early, rest is all letters
        base = "Hi. " + "X" * 600
        result = extract_speakable(base)
        # Period at pos 2, which is < 500//2 = 250, so ellipsis used
        assert result.endswith("\u2026")  # ellipsis character

    def test_multiple_code_blocks(self) -> None:
        *_, extract_speakable, _, _ = _import_integration()
        text = "First block:\n```\ncode1\n```\nMiddle prose.\n```\ncode2\n```\nEnd prose."
        result = extract_speakable(text)
        assert "code1" not in result
        assert "code2" not in result
        assert "Middle prose." in result
        assert "End prose." in result

    def test_custom_max_chars(self) -> None:
        *_, extract_speakable, _, _ = _import_integration()
        text = "Hello world. " * 50  # ~650 chars
        result = extract_speakable(text, max_chars=100)
        assert len(result) <= 105

    def test_markdown_headers_stripped(self) -> None:
        *_, extract_speakable, _, _ = _import_integration()
        text = "## Results\nEverything passed."
        result = extract_speakable(text)
        assert "## Results" not in result
        assert "Everything passed." in result

    def test_blockquotes_stripped(self) -> None:
        *_, extract_speakable, _, _ = _import_integration()
        text = "> Some quoted text\nMy response here."
        result = extract_speakable(text)
        assert "> Some quoted text" not in result
        assert "My response here." in result


# ===================================================================
# 4. TTSGUIManager
# ===================================================================


class TestTTSGUIManager:
    """Verify TTSGUIManager lifecycle, toggles, and delegation."""

    def _make_queue(self) -> queue.Queue:
        return queue.Queue()

    def test_init_tts_disabled(self, _patch_tts_engine) -> None:
        """With enable_tts=False, tts_engine should be None."""
        mock_cls, _ = _patch_tts_engine
        *_, TTSGUIManager, _ = _import_integration()

        mgr = TTSGUIManager(self._make_queue(), enable_tts=False)
        assert mgr.tts_engine is None
        assert mgr.enable_tts is False
        # TTSEngine constructor should NOT have been called for this manager
        # (though it may have been called in other tests)

    def test_init_tts_enabled(self, _patch_tts_engine) -> None:
        """With enable_tts=True, tts_engine should be a mock instance."""
        mock_cls, mock_instance = _patch_tts_engine
        *_, TTSGUIManager, _ = _import_integration()

        mgr = TTSGUIManager(self._make_queue(), enable_tts=True)
        assert mgr.tts_engine is not None
        assert mgr.enable_tts is True

    def test_init_stores_recv_q(self, _patch_tts_engine) -> None:
        *_, TTSGUIManager, _ = _import_integration()
        q = self._make_queue()
        mgr = TTSGUIManager(q, enable_tts=False)
        assert mgr.recv_q is q

    def test_init_creates_pacer(self, _patch_tts_engine) -> None:
        *_, TTSGUIManager, _ = _import_integration()
        from hosts.gui.dialogue_pacing import PacingMode

        mgr = TTSGUIManager(self._make_queue(), enable_tts=False, pacing_mode=PacingMode.FAST)
        assert mgr.pacer.config.mode == PacingMode.FAST

    def test_set_tts_enabled_toggle_on(self, _patch_tts_engine) -> None:
        """Toggling TTS on should create a TTSEngine."""
        mock_cls, _ = _patch_tts_engine
        *_, TTSGUIManager, _ = _import_integration()

        mgr = TTSGUIManager(self._make_queue(), enable_tts=False)
        assert mgr.tts_engine is None

        mgr.set_tts_enabled(True)
        assert mgr.enable_tts is True
        assert mgr.tts_engine is not None

    def test_set_tts_enabled_toggle_off(self, _patch_tts_engine) -> None:
        """Toggling TTS off should call stop() on the engine."""
        mock_cls, mock_instance = _patch_tts_engine
        *_, TTSGUIManager, _ = _import_integration()

        mgr = TTSGUIManager(self._make_queue(), enable_tts=True)
        mgr.set_tts_enabled(False)
        assert mgr.enable_tts is False
        # stop() should have been called on the engine
        mgr.tts_engine.stop.assert_called()

    def test_set_tts_enabled_noop_when_already_disabled(self, _patch_tts_engine) -> None:
        """Disabling when already disabled should be safe."""
        *_, TTSGUIManager, _ = _import_integration()
        mgr = TTSGUIManager(self._make_queue(), enable_tts=False)
        mgr.set_tts_enabled(False)  # no-op
        assert mgr.enable_tts is False

    def test_set_pacing_mode(self, _patch_tts_engine) -> None:
        *_, TTSGUIManager, _ = _import_integration()
        from hosts.gui.dialogue_pacing import PacingMode

        mgr = TTSGUIManager(self._make_queue(), enable_tts=False)
        mgr.set_pacing_mode(PacingMode.SLOW)
        assert mgr.pacer.config.mode == PacingMode.SLOW

    def test_set_pacing_mode_instant(self, _patch_tts_engine) -> None:
        *_, TTSGUIManager, _ = _import_integration()
        from hosts.gui.dialogue_pacing import PacingMode

        mgr = TTSGUIManager(self._make_queue(), enable_tts=False)
        mgr.set_pacing_mode(PacingMode.INSTANT)
        assert mgr.pacer.config.mode == PacingMode.INSTANT

    def test_set_current_agent(self, _patch_tts_engine) -> None:
        *_, TTSGUIManager, _ = _import_integration()
        mgr = TTSGUIManager(self._make_queue(), enable_tts=False)
        assert mgr._current_agent is None
        mgr.set_current_agent("metis")
        assert mgr._current_agent == "metis"

    def test_set_current_agent_overwrite(self, _patch_tts_engine) -> None:
        *_, TTSGUIManager, _ = _import_integration()
        mgr = TTSGUIManager(self._make_queue(), enable_tts=False)
        mgr.set_current_agent("metis")
        mgr.set_current_agent("kallos")
        assert mgr._current_agent == "kallos"

    def test_cleanup_with_engine(self, _patch_tts_engine) -> None:
        """cleanup() should stop and clean the engine."""
        mock_cls, mock_instance = _patch_tts_engine
        *_, TTSGUIManager, _ = _import_integration()

        mgr = TTSGUIManager(self._make_queue(), enable_tts=True)
        engine = mgr.tts_engine
        mgr.cleanup()
        engine.stop.assert_called()
        engine.cleanup.assert_called()

    def test_cleanup_without_engine(self, _patch_tts_engine) -> None:
        """cleanup() with no engine should not raise."""
        *_, TTSGUIManager, _ = _import_integration()
        mgr = TTSGUIManager(self._make_queue(), enable_tts=False)
        mgr.cleanup()  # should not raise

    @pytest.mark.asyncio
    async def test_process_dialogue_event_status(self, _patch_tts_engine) -> None:
        """Status events with text should trigger pacer + TTS."""
        mock_cls, mock_instance = _patch_tts_engine
        *_, TTSGUIManager, _ = _import_integration()

        mgr = TTSGUIManager(self._make_queue(), enable_tts=True)
        mgr.set_current_agent("hephaestus")

        with (
            patch.object(mgr.pacer, "wait_before_response") as mock_wait,
            patch.object(mgr, "_speak_async") as mock_speak,
        ):
            await mgr.process_dialogue_event({"type": "status", "text": "Processing..."})
            mock_wait.assert_awaited_once()
            mock_speak.assert_awaited_once_with("Processing...", "hephaestus")

    @pytest.mark.asyncio
    async def test_process_dialogue_event_result(self, _patch_tts_engine) -> None:
        """Result events with text should trigger pacer + TTS."""
        mock_cls, mock_instance = _patch_tts_engine
        *_, TTSGUIManager, _ = _import_integration()

        mgr = TTSGUIManager(self._make_queue(), enable_tts=True)
        mgr.set_current_agent("metis")

        with (
            patch.object(mgr.pacer, "wait_between_responses") as mock_wait,
            patch.object(mgr, "_speak_async") as mock_speak,
        ):
            await mgr.process_dialogue_event({"type": "result", "text": "Done."})
            mock_wait.assert_awaited_once()
            mock_speak.assert_awaited_once_with("Done.", "metis")

    @pytest.mark.asyncio
    async def test_process_dialogue_event_status_tts_disabled(self, _patch_tts_engine) -> None:
        """With TTS disabled, status events should not call _speak_async."""
        *_, TTSGUIManager, _ = _import_integration()

        mgr = TTSGUIManager(self._make_queue(), enable_tts=False)

        with (
            patch.object(mgr.pacer, "wait_before_response") as mock_wait,
            patch.object(mgr, "_speak_async") as mock_speak,
        ):
            await mgr.process_dialogue_event({"type": "status", "text": "Working..."})
            mock_wait.assert_awaited_once()
            mock_speak.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_process_dialogue_event_unknown_type(self, _patch_tts_engine) -> None:
        """Unknown event types should be silently ignored."""
        *_, TTSGUIManager, _ = _import_integration()
        mgr = TTSGUIManager(self._make_queue(), enable_tts=False)
        # Should not raise
        await mgr.process_dialogue_event({"type": "unknown", "text": "something"})

    @pytest.mark.asyncio
    async def test_process_dialogue_event_empty_text(self, _patch_tts_engine) -> None:
        """Status event with empty text should not trigger TTS."""
        *_, TTSGUIManager, _ = _import_integration()
        mgr = TTSGUIManager(self._make_queue(), enable_tts=True)

        with patch.object(mgr, "_speak_async") as mock_speak:
            await mgr.process_dialogue_event({"type": "status", "text": ""})
            mock_speak.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_speak_async_no_engine(self, _patch_tts_engine) -> None:
        """_speak_async with no engine should return without error."""
        *_, TTSGUIManager, _ = _import_integration()
        mgr = TTSGUIManager(self._make_queue(), enable_tts=False)
        await mgr._speak_async("hello")  # should not raise

    @pytest.mark.asyncio
    async def test_speak_async_calls_engine(self, _patch_tts_engine) -> None:
        """_speak_async should call speak_sync on the engine in an executor."""
        mock_cls, mock_instance = _patch_tts_engine
        *_, TTSGUIManager, _ = _import_integration()

        mgr = TTSGUIManager(self._make_queue(), enable_tts=True)
        engine = mgr.tts_engine

        await mgr._speak_async("hello", agent_name="kallos", speed=1.2, pitch=0.9)
        engine.speak_sync.assert_called_once_with("hello", "kallos", None, 1.2, 0.9)

    @pytest.mark.asyncio
    async def test_speak_async_handles_exception(self, _patch_tts_engine) -> None:
        """_speak_async should catch and log errors from the engine."""
        mock_cls, mock_instance = _patch_tts_engine
        *_, TTSGUIManager, _ = _import_integration()

        mgr = TTSGUIManager(self._make_queue(), enable_tts=True)
        mgr.tts_engine.speak_sync.side_effect = RuntimeError("audio failure")

        # Should not raise
        await mgr._speak_async("hello")


# ===================================================================
# 5. TTSSettingsPanel
# ===================================================================


class TestTTSSettingsPanel:
    """Verify TTSSettingsPanel get/apply operations."""

    def _make_manager(self, _patch_tts_engine) -> Any:
        mock_cls, mock_instance = _patch_tts_engine
        *_, TTSGUIManager, _ = _import_integration()
        return TTSGUIManager(queue.Queue(), enable_tts=True)

    def test_get_settings_dict_keys(self, _patch_tts_engine) -> None:
        *_, TTSSettingsPanel = _import_integration()
        mgr = self._make_manager(_patch_tts_engine)
        panel = TTSSettingsPanel(mgr)

        settings = panel.get_settings_dict()
        expected_keys = {
            "tts_enabled",
            "master_volume",
            "enable_effects",
            "pacing_mode",
            "thinking_pause",
            "thinking_pause_duration",
            "min_chars_per_second",
        }
        assert set(settings.keys()) == expected_keys

    def test_get_settings_dict_values_tts_enabled(self, _patch_tts_engine) -> None:
        *_, TTSSettingsPanel = _import_integration()
        mgr = self._make_manager(_patch_tts_engine)
        panel = TTSSettingsPanel(mgr)

        settings = panel.get_settings_dict()
        assert settings["tts_enabled"] is True

    def test_get_settings_dict_values_no_engine(self, _patch_tts_engine) -> None:
        """When tts_engine is None, defaults are returned for volume/effects."""
        _, _, _, TTSGUIManager, TTSSettingsPanel = _import_integration()
        mgr = TTSGUIManager(queue.Queue(), enable_tts=False)
        panel = TTSSettingsPanel(mgr)

        settings = panel.get_settings_dict()
        assert settings["master_volume"] == 0.8
        assert settings["enable_effects"] is True

    def test_get_settings_dict_pacing_mode(self, _patch_tts_engine) -> None:
        from hosts.gui.dialogue_pacing import PacingMode

        _, _, _, TTSGUIManager, TTSSettingsPanel = _import_integration()
        mgr = TTSGUIManager(queue.Queue(), enable_tts=False, pacing_mode=PacingMode.SLOW)
        panel = TTSSettingsPanel(mgr)

        settings = panel.get_settings_dict()
        assert settings["pacing_mode"] == "SLOW"

    def test_apply_settings_tts_enabled(self, _patch_tts_engine) -> None:
        *_, TTSSettingsPanel = _import_integration()
        mgr = self._make_manager(_patch_tts_engine)
        panel = TTSSettingsPanel(mgr)

        panel.apply_settings({"tts_enabled": False})
        assert mgr.enable_tts is False

    def test_apply_settings_master_volume(self, _patch_tts_engine) -> None:
        *_, TTSSettingsPanel = _import_integration()
        mgr = self._make_manager(_patch_tts_engine)
        panel = TTSSettingsPanel(mgr)

        panel.apply_settings({"master_volume": 0.5})
        mgr.tts_engine.set_master_volume.assert_called_with(0.5)

    def test_apply_settings_enable_effects(self, _patch_tts_engine) -> None:
        *_, TTSSettingsPanel = _import_integration()
        mgr = self._make_manager(_patch_tts_engine)
        panel = TTSSettingsPanel(mgr)

        panel.apply_settings({"enable_effects": False})
        assert mgr.tts_engine.enable_effects is False

    def test_apply_settings_pacing_mode(self, _patch_tts_engine) -> None:
        from hosts.gui.dialogue_pacing import PacingMode

        *_, TTSSettingsPanel = _import_integration()
        mgr = self._make_manager(_patch_tts_engine)
        panel = TTSSettingsPanel(mgr)

        panel.apply_settings({"pacing_mode": "SLOW"})
        assert mgr.pacer.config.mode == PacingMode.SLOW

    def test_apply_settings_invalid_pacing_mode(self, _patch_tts_engine) -> None:
        """Invalid pacing mode string should be silently ignored."""

        *_, TTSSettingsPanel = _import_integration()
        mgr = self._make_manager(_patch_tts_engine)
        panel = TTSSettingsPanel(mgr)

        original_mode = mgr.pacer.config.mode
        panel.apply_settings({"pacing_mode": "NONEXISTENT"})
        assert mgr.pacer.config.mode == original_mode

    def test_apply_settings_thinking_pause(self, _patch_tts_engine) -> None:
        *_, TTSSettingsPanel = _import_integration()
        mgr = self._make_manager(_patch_tts_engine)
        panel = TTSSettingsPanel(mgr)

        panel.apply_settings({"thinking_pause": False, "thinking_pause_duration": 1.0})
        assert mgr.pacer.config.enable_thinking_pause is False
        assert mgr.pacer.config.thinking_pause_duration == 1.0

    def test_apply_settings_thinking_pause_only_enabled(self, _patch_tts_engine) -> None:
        """Setting only thinking_pause without duration should use existing duration."""
        *_, TTSSettingsPanel = _import_integration()
        mgr = self._make_manager(_patch_tts_engine)
        panel = TTSSettingsPanel(mgr)

        original_duration = mgr.pacer.config.thinking_pause_duration
        panel.apply_settings({"thinking_pause": False})
        assert mgr.pacer.config.enable_thinking_pause is False
        assert mgr.pacer.config.thinking_pause_duration == original_duration

    def test_apply_settings_min_chars_per_second(self, _patch_tts_engine) -> None:
        *_, TTSSettingsPanel = _import_integration()
        mgr = self._make_manager(_patch_tts_engine)
        panel = TTSSettingsPanel(mgr)

        panel.apply_settings({"min_chars_per_second": 100.0})
        assert mgr.pacer.config.min_chars_per_second == 100.0

    def test_apply_settings_empty_dict(self, _patch_tts_engine) -> None:
        """Empty settings dict should be a no-op."""
        *_, TTSSettingsPanel = _import_integration()
        mgr = self._make_manager(_patch_tts_engine)
        panel = TTSSettingsPanel(mgr)
        panel.apply_settings({})  # should not raise

    def test_apply_settings_multiple_keys(self, _patch_tts_engine) -> None:
        """Multiple settings applied at once."""
        from hosts.gui.dialogue_pacing import PacingMode

        *_, TTSSettingsPanel = _import_integration()
        mgr = self._make_manager(_patch_tts_engine)
        panel = TTSSettingsPanel(mgr)

        panel.apply_settings(
            {
                "pacing_mode": "FAST",
                "thinking_pause": True,
                "thinking_pause_duration": 0.2,
                "min_chars_per_second": 75.0,
            }
        )
        assert mgr.pacer.config.mode == PacingMode.FAST
        assert mgr.pacer.config.enable_thinking_pause is True
        assert mgr.pacer.config.thinking_pause_duration == 0.2
        assert mgr.pacer.config.min_chars_per_second == 75.0


# ===================================================================
# 6. TTSSettingsConfig
# ===================================================================


class TestTTSSettingsConfig:
    """Verify TTSSettingsConfig persistence, get/set, and manager sync."""

    def test_init_creates_parent_dir(self) -> None:
        """Config init should create parent directories."""
        TTSSettingsConfig = _import_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "sub" / "deep" / "tts_settings.json"
            TTSSettingsConfig(config_path=nested)
            assert nested.parent.exists()

    def test_default_settings_no_file(self) -> None:
        """When config file doesn't exist, defaults should be loaded."""
        TTSSettingsConfig = _import_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            config = TTSSettingsConfig(config_path=path)
            assert config.settings == TTSSettingsConfig.DEFAULT_CONFIG

    def test_default_settings_are_copy(self) -> None:
        """Settings should be a copy, not a reference to DEFAULT_CONFIG."""
        TTSSettingsConfig = _import_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            config = TTSSettingsConfig(config_path=path)
            config.settings["tts_enabled"] = False
            assert TTSSettingsConfig.DEFAULT_CONFIG["tts_enabled"] is True

    def test_save_creates_json_file(self) -> None:
        """save() should write a valid JSON file."""
        TTSSettingsConfig = _import_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            config = TTSSettingsConfig(config_path=path)
            config.save()
            assert path.exists()
            with path.open() as f:
                data = json.load(f)
            assert data == config.settings

    def test_get_existing_key(self) -> None:
        TTSSettingsConfig = _import_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            config = TTSSettingsConfig(config_path=path)
            assert config.get("tts_enabled") is True

    def test_get_missing_key_default(self) -> None:
        TTSSettingsConfig = _import_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            config = TTSSettingsConfig(config_path=path)
            assert config.get("nonexistent", "fallback") == "fallback"

    def test_get_missing_key_none(self) -> None:
        TTSSettingsConfig = _import_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            config = TTSSettingsConfig(config_path=path)
            assert config.get("nonexistent") is None

    def test_set_new_key(self) -> None:
        TTSSettingsConfig = _import_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            config = TTSSettingsConfig(config_path=path)
            config.set("custom_key", 42)
            assert config.settings["custom_key"] == 42

    def test_set_overwrite(self) -> None:
        TTSSettingsConfig = _import_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            config = TTSSettingsConfig(config_path=path)
            config.set("tts_enabled", False)
            assert config.settings["tts_enabled"] is False

    def test_load_from_existing_file(self) -> None:
        """Loading from an existing JSON file should restore saved values."""
        TTSSettingsConfig = _import_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            custom_settings = {
                "tts_enabled": False,
                "pacing_mode": "SLOW",
                "thinking_pause_enabled": False,
                "thinking_pause_duration": 2.0,
                "min_chars_per_second": 100.0,
            }
            with path.open("w") as f:
                json.dump(custom_settings, f)

            config = TTSSettingsConfig(config_path=path)
            assert config.settings["tts_enabled"] is False
            assert config.settings["pacing_mode"] == "SLOW"
            assert config.settings["thinking_pause_enabled"] is False
            assert config.settings["thinking_pause_duration"] == 2.0
            assert config.settings["min_chars_per_second"] == 100.0

    def test_load_corrupt_file_falls_back(self) -> None:
        """Corrupt JSON should fall back to defaults."""
        TTSSettingsConfig = _import_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            with path.open("w") as f:
                f.write("{invalid json!!!")

            config = TTSSettingsConfig(config_path=path)
            assert config.settings == TTSSettingsConfig.DEFAULT_CONFIG

    def test_load_empty_file_falls_back(self) -> None:
        """Empty file should fall back to defaults."""
        TTSSettingsConfig = _import_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            path.touch()

            config = TTSSettingsConfig(config_path=path)
            assert config.settings == TTSSettingsConfig.DEFAULT_CONFIG

    def test_save_then_load_roundtrip(self) -> None:
        """Saved settings should be identical when reloaded."""
        TTSSettingsConfig = _import_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            config1 = TTSSettingsConfig(config_path=path)
            config1.set("pacing_mode", "FAST")
            config1.set("min_chars_per_second", 75.0)
            config1.save()

            config2 = TTSSettingsConfig(config_path=path)
            assert config2.settings["pacing_mode"] == "FAST"
            assert config2.settings["min_chars_per_second"] == 75.0

    def test_apply_to_manager(self, _patch_tts_engine) -> None:
        """apply_to_manager should push settings into the TTSGUIManager."""
        TTSSettingsConfig = _import_config()
        _, _, _, TTSGUIManager, _ = _import_integration()
        from hosts.gui.dialogue_pacing import PacingMode

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            config = TTSSettingsConfig(config_path=path)
            config.set("tts_enabled", True)
            config.set("pacing_mode", "SLOW")
            config.set("thinking_pause_enabled", True)
            config.set("thinking_pause_duration", 1.5)
            config.set("min_chars_per_second", 80.0)

            mgr = TTSGUIManager(queue.Queue(), enable_tts=False)
            config.apply_to_manager(mgr)

            assert mgr.enable_tts is True
            assert mgr.pacer.config.mode == PacingMode.SLOW
            assert mgr.pacer.config.enable_thinking_pause is True
            assert mgr.pacer.config.thinking_pause_duration == 1.5
            assert mgr.pacer.config.min_chars_per_second == 80.0

    def test_apply_to_manager_invalid_pacing_mode(self, _patch_tts_engine) -> None:
        """Invalid pacing mode in config should be silently skipped."""
        TTSSettingsConfig = _import_config()
        _, _, _, TTSGUIManager, _ = _import_integration()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            config = TTSSettingsConfig(config_path=path)
            config.set("pacing_mode", "TURBO_INVALID")

            mgr = TTSGUIManager(queue.Queue(), enable_tts=False)
            original_mode = mgr.pacer.config.mode
            config.apply_to_manager(mgr)
            assert mgr.pacer.config.mode == original_mode

    def test_apply_to_manager_partial_settings(self, _patch_tts_engine) -> None:
        """Settings with only some keys should only apply those keys."""
        TTSSettingsConfig = _import_config()
        _, _, _, TTSGUIManager, _ = _import_integration()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            # Write a file with only one key
            with path.open("w") as f:
                json.dump({"min_chars_per_second": 99.0}, f)

            config = TTSSettingsConfig(config_path=path)
            mgr = TTSGUIManager(queue.Queue(), enable_tts=False)
            config.apply_to_manager(mgr)
            assert mgr.pacer.config.min_chars_per_second == 99.0

    def test_update_from_manager(self, _patch_tts_engine) -> None:
        """update_from_manager should snapshot manager state into settings."""
        TTSSettingsConfig = _import_config()
        _, _, _, TTSGUIManager, _ = _import_integration()
        from hosts.gui.dialogue_pacing import PacingMode

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            config = TTSSettingsConfig(config_path=path)

            mgr = TTSGUIManager(queue.Queue(), enable_tts=True)
            mgr.set_pacing_mode(PacingMode.FAST)
            mgr.pacer.config.min_chars_per_second = 120.0
            mgr.pacer.config.enable_thinking_pause = False
            mgr.pacer.config.thinking_pause_duration = 0.3

            config.update_from_manager(mgr)

            assert config.settings["tts_enabled"] is True
            assert config.settings["pacing_mode"] == "FAST"
            assert config.settings["min_chars_per_second"] == 120.0
            assert config.settings["thinking_pause_enabled"] is False
            assert config.settings["thinking_pause_duration"] == 0.3

    def test_update_then_save_then_load(self, _patch_tts_engine) -> None:
        """Full roundtrip: update from manager -> save -> load -> verify."""
        TTSSettingsConfig = _import_config()
        _, _, _, TTSGUIManager, _ = _import_integration()
        from hosts.gui.dialogue_pacing import PacingMode

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"

            # Setup manager with specific state
            mgr = TTSGUIManager(queue.Queue(), enable_tts=True)
            mgr.set_pacing_mode(PacingMode.SLOW)
            mgr.pacer.config.min_chars_per_second = 200.0

            # Snapshot and save
            config1 = TTSSettingsConfig(config_path=path)
            config1.update_from_manager(mgr)
            config1.save()

            # Reload and verify
            config2 = TTSSettingsConfig(config_path=path)
            assert config2.settings["pacing_mode"] == "SLOW"
            assert config2.settings["min_chars_per_second"] == 200.0

    def test_reset_to_defaults(self) -> None:
        """reset_to_defaults should restore DEFAULT_CONFIG and save."""
        TTSSettingsConfig = _import_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            config = TTSSettingsConfig(config_path=path)
            config.set("tts_enabled", False)
            config.set("pacing_mode", "SLOW")
            config.set("custom_extra", "value")
            config.save()

            config.reset_to_defaults()
            assert config.settings == TTSSettingsConfig.DEFAULT_CONFIG
            assert "custom_extra" not in config.settings

            # File should also be updated
            with path.open() as f:
                saved = json.load(f)
            assert saved == TTSSettingsConfig.DEFAULT_CONFIG

    def test_reset_to_defaults_is_copy(self) -> None:
        """After reset, modifying settings should not affect DEFAULT_CONFIG."""
        TTSSettingsConfig = _import_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tts_settings.json"
            config = TTSSettingsConfig(config_path=path)
            config.reset_to_defaults()
            config.settings["tts_enabled"] = False
            assert TTSSettingsConfig.DEFAULT_CONFIG["tts_enabled"] is True

    def test_config_path_default(self) -> None:
        """When no config_path given, uses ~/.kourai/tts_settings.json."""
        TTSSettingsConfig = _import_config()
        with patch.object(Path, "mkdir"):
            config = TTSSettingsConfig.__new__(TTSSettingsConfig)
            config.config_path = None
            # Just verify the default path logic exists in __init__
            Path.home() / ".kourai" / "tts_settings.json"
            # Instantiate properly to check
            with (
                tempfile.TemporaryDirectory() as tmpdir,
                patch("pathlib.Path.home", return_value=Path(tmpdir)),
            ):
                config = TTSSettingsConfig()
                assert config.config_path == Path(tmpdir) / ".kourai" / "tts_settings.json"
