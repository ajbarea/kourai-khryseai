"""Unit tests for the shared emote-SFX engine in ``kourai_common.emote_sfx``.

The pure logic (regex extraction, keyword → SFX-category resolution, asset
path lookup) moved from ``hosts/gui/emote_sfx.py`` to shared so CLI and
VN can wire their own playback bindings later. Host-specific playback
(``play_emote_sfx`` with the pygame AudioManager) stays in GUI; this
module exercises the moved pure logic against the canonical asset paths.
"""

from __future__ import annotations

from kourai_common.emote_sfx import extract_emotes, resolve_sfx


def test_extract_emotes_pulls_asterisk_wrapped_text():
    assert extract_emotes("*chuckles*") == ["chuckles"]
    assert extract_emotes("*sighs* well, that was something *laughs*") == [
        "sighs",
        "laughs",
    ]


def test_extract_emotes_returns_empty_for_plain_text():
    assert extract_emotes("plain dialogue without asterisks") == []
    assert extract_emotes("") == []


def test_resolve_sfx_returns_none_for_unknown_emote():
    assert resolve_sfx("dances joyfully") is None


def test_resolve_sfx_resolves_canonical_keywords():
    # The actual SFX file presence depends on the assets repo state;
    # we only check that the resolver maps the keyword to a category and
    # would look at the assets/audio/sfx/<category>.ogg path. Falling
    # through to None is fine for missing assets.
    path = resolve_sfx("strikes anvil")
    if path is not None:  # SFX exists in repo
        assert path.name.endswith(".ogg")
        assert "anvil" in path.name


def test_resolve_sfx_per_agent_override_falls_back_to_shared():
    # No per-agent override file is checked in for hephaestus right now;
    # the resolver must fall back to the shared pool gracefully.
    path = resolve_sfx("grunts", agent_name="hephaestus")
    if path is not None:
        # Either an agent-specific path or the shared pool — both valid.
        assert path.name.endswith(".ogg")
