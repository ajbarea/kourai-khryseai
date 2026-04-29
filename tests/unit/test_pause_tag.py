"""``PAUSE: <kind> "<question>"`` token parser (M17 Phase 1)."""

from __future__ import annotations

from kourai_common.pause_tag import PauseTag, extract_pause_tag

SPEC_BODY = (
    "1. Summary — refactor the CSV exporter to stream chunked I/O.\n"
    "2. Files to Modify — src/export.py, tests/test_export.py.\n"
    "3. Implementation Steps — read with iterator, drop accumulator.\n"
)


class TestExtractPauseTag:
    def test_returns_none_when_no_tag(self):
        assert extract_pause_tag(SPEC_BODY) is None

    def test_parses_trailing_tag(self):
        text = SPEC_BODY + '\nPAUSE: coverage_target "What test coverage target should I plan for?"'
        tag = extract_pause_tag(text)
        assert tag == PauseTag(
            preference_kind="coverage_target",
            question="What test coverage target should I plan for?",
            clean_text=SPEC_BODY.rstrip(),
        )

    def test_clean_text_strips_only_the_pause_line(self):
        text = SPEC_BODY + '\nPAUSE: python_version "Python 3.12 or 3.13?"'
        tag = extract_pause_tag(text)
        assert tag is not None
        assert tag.clean_text == SPEC_BODY.rstrip()
        assert "PAUSE:" not in tag.clean_text

    def test_each_phase_one_kind_round_trips(self):
        for kind in (
            "coverage_target",
            "python_version",
            "style_rules",
            "commit_style",
            "test_framework",
        ):
            text = f'short spec\nPAUSE: {kind} "Question?"'
            tag = extract_pause_tag(text)
            assert tag is not None, f"failed to parse known kind {kind}"
            assert tag.preference_kind == kind

    def test_unknown_preference_kind_returns_none(self):
        text = 'spec\nPAUSE: favourite_colour "Blue?"'
        assert extract_pause_tag(text) is None

    def test_empty_question_returns_none(self):
        text = 'spec\nPAUSE: coverage_target ""'
        assert extract_pause_tag(text) is None

    def test_malformed_tag_returns_none(self):
        # Missing quotes around the question
        assert extract_pause_tag("spec\nPAUSE: coverage_target what?") is None
        # Missing kind word
        assert extract_pause_tag('spec\nPAUSE: "what?"') is None

    def test_tag_only_text(self):
        text = 'PAUSE: style_rules "Black or ruff format?"'
        tag = extract_pause_tag(text)
        assert tag is not None
        assert tag.preference_kind == "style_rules"
        assert tag.question == "Black or ruff format?"
        assert tag.clean_text == ""

    def test_question_keeps_punctuation_and_spaces(self):
        text = 'spec\nPAUSE: commit_style "Conventional Commits, gitmoji, or freeform?"'
        tag = extract_pause_tag(text)
        assert tag is not None
        assert tag.question == "Conventional Commits, gitmoji, or freeform?"
