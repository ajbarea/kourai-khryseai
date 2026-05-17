"""Structural validation for the voice-examples few-shot character system.

Each agent has a ``voice_examples.md`` file next to its ``agent.py``. The file
is loaded at module import via ``kourai_common.prompts.load_voice_examples``
and injected into the agent's system prompt as a few-shot dialogue block.

These tests assert structural presence (file exists, prompt has the tag,
example count is in the 2026 best-practice range) without asserting on
specific dialogue lines — voice content evolves, structure shouldn't.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "agents"

# The 10 character agents. vn_bridge is a transport, not a character.
CHARACTER_AGENTS = (
    "aidos",
    "aletheia",
    "cupid",
    "dokimasia",
    "hephaestus",
    "kallos",
    "metis",
    "mneme",
    "puck",
    "techne",
)


def _voice_examples_path(agent: str) -> Path:
    return AGENTS_DIR / agent / "voice_examples.md"


def test_every_character_agent_has_voice_examples_file():
    """Each of the 10 character agents ships a voice_examples.md."""
    missing = [a for a in CHARACTER_AGENTS if not _voice_examples_path(a).is_file()]
    assert not missing, f"agents missing voice_examples.md: {missing}"


def test_voice_examples_have_xml_tag_and_example_blocks():
    """Each file wraps content in <voice_examples> and contains >=4 <example> blocks."""
    for agent in CHARACTER_AGENTS:
        text = _voice_examples_path(agent).read_text(encoding="utf-8")
        assert "<voice_examples>" in text, f"{agent}: missing <voice_examples> wrapper"
        assert "</voice_examples>" in text, f"{agent}: missing closing </voice_examples>"
        example_count = text.count("<example>")
        # 2026 best practice: 3-5 examples per character. Floor at 4.
        assert example_count >= 4, (
            f"{agent}: has {example_count} <example> blocks, expected >= 4 "
            "(per 2026 few-shot best practice — 3 is the floor, 4-5 is the sweet spot)"
        )


def test_voice_examples_label_themselves_as_voice_reference():
    """Each file says 'voice reference' to signal generalize-don't-copy intent."""
    for agent in CHARACTER_AGENTS:
        text = _voice_examples_path(agent).read_text(encoding="utf-8").lower()
        assert "voice reference" in text, (
            f"{agent}: voice_examples.md should label itself a 'voice reference' "
            "so the model generalizes rhythm rather than copying lines verbatim"
        )


def test_metis_prompt_injects_voice_examples():
    """build_system_prompt() integration — Metis as the representative case."""
    from agents.metis.agent import SYSTEM_PROMPT

    assert "<voice_examples>" in SYSTEM_PROMPT
    assert SYSTEM_PROMPT.count("<example>") >= 4


def test_hephaestus_routing_prompt_appends_voice_examples():
    """Hephaestus uses a separate ROUTING_PROMPT f-string, not build_system_prompt."""
    from agents.hephaestus.agent import ROUTING_PROMPT

    assert "<voice_examples>" in ROUTING_PROMPT
    assert ROUTING_PROMPT.count("<example>") >= 4
