"""M10 — speech-vs-action rendering convention.

Cross-cuts every host. Asserts:

- ``UNIVERSAL_RULES`` contains the speech-vs-action rule (so all 9
  specialists carrying ``build_system_prompt()`` output pick it up).
- Hephaestus's hand-rolled ``ROUTING_PROMPT`` carries the same rule and
  every ``HEPH_HANDOFFS`` line is wrapped in double quotes — handoff
  lines are dialogue per the ROADMAP M10 Talking-vs-Working table.
- The CLI ``_comms_window`` italicises lines that begin with ``"`` and
  leaves status lines plain.
- The GUI's ``_is_quoted_dialogue`` helper detects the same convention
  and ``_draw_line_with_emotes`` accepts an ``oblique`` keyword.
- The VN's Ren'Py ``Character()`` definitions never carry the literal
  ``what_prefix='"'`` — the name plaque already signals the speaker
  Hades-style and quoting is decided per-line by agent output.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.hephaestus.agent import HEPH_HANDOFFS, ROUTING_PROMPT, get_heph_narration
from hosts.cli.rendering import _comms_window
from hosts.cli.styling import _ITALIC
from kourai_common.prompts import UNIVERSAL_RULES, build_system_prompt

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestUniversalRule:
    """The rule lives in UNIVERSAL_RULES so all 9 specialists inherit it."""

    def test_universal_rules_contains_speech_vs_action(self):
        assert "SPEECH VS ACTION" in UNIVERSAL_RULES

    def test_universal_rules_explains_quoted_lines(self):
        assert "double quotes" in UNIVERSAL_RULES
        assert "italic" in UNIVERSAL_RULES.lower()

    @pytest.mark.parametrize(
        "agent_name,role",
        [
            ("Metis", "planning specialist"),
            ("Techne", "coding specialist"),
            ("Kallos", "style specialist"),
            ("Dokimasia", "testing specialist"),
            ("Mneme", "commit message specialist"),
        ],
    )
    def test_built_specialist_prompt_carries_rule(self, agent_name, role):
        prompt = build_system_prompt(
            agent_name=agent_name,
            role=role,
            personality="placeholder",
            specific_instructions="placeholder",
        )
        assert "SPEECH VS ACTION" in prompt


class TestHephaestusRoutingPrompt:
    """Hephaestus is hand-rolled and needs its own copy of the convention."""

    def test_routing_prompt_mentions_speech_vs_action(self):
        assert "SPEECH VS ACTION" in ROUTING_PROMPT

    def test_routing_prompt_chat_example_is_quoted(self):
        # The CHAT: example renders as Hephaestus speaking — must be quoted.
        assert 'CHAT: "The forge is always hot.' in ROUTING_PROMPT

    def test_routing_prompt_ask_user_example_is_quoted(self):
        assert 'ASK_USER: "Should the CSV export' in ROUTING_PROMPT


class TestHephaestusHandoffs:
    """Every HEPH_HANDOFFS value is dialogue and must be quote-wrapped so
    the host's speech-vs-action italic convention fires.
    """

    def test_all_handoff_lines_open_with_quote(self):
        offenders = [
            (agent, line)
            for agent, lines in HEPH_HANDOFFS.items()
            for line in lines
            if not line.startswith('"')
        ]
        assert offenders == [], f"unquoted handoff lines: {offenders}"

    def test_all_handoff_lines_close_with_quote(self):
        offenders = [
            (agent, line)
            for agent, lines in HEPH_HANDOFFS.items()
            for line in lines
            if not line.endswith('"')
        ]
        assert offenders == [], f"handoff lines missing closing quote: {offenders}"

    def test_get_heph_narration_returns_quoted_line_for_known_agent(self):
        line = get_heph_narration("metis")
        assert line.startswith('"') and line.endswith('"')

    def test_get_heph_narration_returns_quoted_line_for_unknown_agent(self):
        # The fallback must obey the convention too.
        line = get_heph_narration("zzz_not_an_agent")
        assert line.startswith('"') and line.endswith('"')


class TestCommsWindowItalic:
    """The CLI flips italic on/off based on whether the dialogue is quoted."""

    def test_quoted_dialogue_renders_italic(self):
        rendered = _comms_window("hephaestus", '"The forge is hot."')
        assert _ITALIC in rendered

    def test_unquoted_status_does_not_render_italic(self):
        rendered = _comms_window("hephaestus", "Running pytest --tb=short")
        assert _ITALIC not in rendered

    def test_whisper_quoted_dialogue_keeps_italic(self):
        # Outgoing maiden's parting whisper is dialogue — dim AND italic.
        rendered = _comms_window("techne", '"My turn next time."', style="whisper")
        assert _ITALIC in rendered

    def test_whisper_unquoted_skips_italic(self):
        rendered = _comms_window("techne", "compiling fixtures", style="whisper")
        assert _ITALIC not in rendered


class TestCommsWindowStripsSsml:
    """`_comms_window` is the universal display chokepoint — every
    dialogue source (HEPH_HANDOFFS, HANDOFF_LINES, VICTORY_LINES, future
    LLM SSML) hits it eventually. Strip here means callers can stay
    SSML-agnostic.
    """

    def test_speak_wrapped_dialogue_renders_clean_text(self):
        rendered = _comms_window(
            "hephaestus",
            '<speak>"The bronze must be heated <break time="200ms"/>until it sings."</speak>',
        )
        assert "<speak>" not in rendered
        assert "<break" not in rendered
        # Quote convention preserved post-strip → italic styling fires.
        assert _ITALIC in rendered
        # Break collapses to single space.
        assert '"The bronze must be heated until it sings."' in rendered

    def test_plain_text_dialogue_unchanged(self):
        # Fast path — strip is idempotent on plain text.
        plain_rendered = _comms_window("hephaestus", '"The forge is hot."')
        assert '"The forge is hot."' in plain_rendered
        assert _ITALIC in plain_rendered


class TestMaidenifyStatusStripsSsml:
    """M18 Phase 2: producer dialogue arrives as SSML; the host display
    boundary strips so the player sees clean text. The TTS engine still
    receives raw SSML upstream of this so prosody can be used by future
    SSML-native engines (M6 ElevenLabs).
    """

    def test_ssml_dialogue_renders_stripped_and_italic(self):
        from hosts.cli import events

        # Reset the module-level _last_seen_agent so handoff chatter
        # doesn't fire mid-test and pollute the assertion.
        events._last_seen_agent = None
        ssml = '\U0001f525 <speak>"Metis! Draw up the plans. <break time="200ms"/>And no improvising."</speak>'

        formatted, agent = events._maidenify_status(ssml)
        assert agent == "hephaestus"
        # No raw SSML tags survive into the rendered comms window.
        assert "<speak>" not in formatted and "<break" not in formatted
        # Quote convention preserved → italic styling kicks in.
        assert _ITALIC in formatted
        # Break collapses to a single space, content reads naturally.
        assert '"Metis! Draw up the plans. And no improvising."' in formatted


class TestGuiIsQuotedDialogue:
    """The GUI's per-line predicate matches the same convention."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ('"The forge is hot."', True),
            ('  "leading whitespace allowed."', True),
            ("running pytest", False),
            ("[1/4] Techne completed", False),
            ("", False),
            ('"', True),  # degenerate but still opens with a quote
        ],
    )
    def test_predicate(self, text, expected):
        # Imported lazily because the host module depends on pygame init.
        pygame = pytest.importorskip("pygame")  # noqa: F841
        from hosts.gui.dialogue import _is_quoted_dialogue

        assert _is_quoted_dialogue(text) is expected

    def test_draw_line_accepts_oblique_kwarg(self):
        """Regression guard for the kwarg signature.

        ``_draw_line_with_emotes`` is the per-line renderer; the new
        ``oblique`` keyword is what flips synthesised italic on. The
        signature check stays cheap (no pygame surface needed) and
        catches accidental kwarg renames during refactors.
        """
        pytest.importorskip("pygame")
        from inspect import signature

        from hosts.gui.dialogue import DialogueHistory

        sig = signature(DialogueHistory._draw_line_with_emotes)
        assert "oblique" in sig.parameters
        assert sig.parameters["oblique"].default is False


class TestVnNoBlanketQuoting:
    """Every Ren'Py ``Character()`` lets agent output decide quoting."""

    def test_vn_scripts_have_no_what_prefix(self):
        vn_dir = REPO_ROOT / "hosts" / "vn" / "kourai_vn" / "game"
        offenders = []
        for rpy in vn_dir.rglob("*.rpy"):
            text = rpy.read_text(encoding="utf-8")
            if "what_prefix" in text or "what_suffix" in text:
                offenders.append(str(rpy.relative_to(REPO_ROOT)))
        assert offenders == [], (
            f"Ren'Py files still blanket-quote dialogue via Character(...): {offenders}"
        )
