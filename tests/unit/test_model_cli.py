"""Tests for the /model CLI slash command.

The data layer (``config.set_tier`` / ``get_tier``) is tested in
``test_config.py::TestTierMutation``. These tests cover the CLI handler
``_handle_model_command`` — output shape, tier-switch echo, error path
on unknown tier.
"""

from __future__ import annotations

import pytest

import kourai_common.config as config
from hosts.cli.commands import _handle_model_command


@pytest.fixture(autouse=True)
def _restore_tier(monkeypatch):
    monkeypatch.setattr("kourai_common.config.MODEL_TIER", "cheap")
    yield


@pytest.fixture
def echoed(monkeypatch):
    captured: list[str] = []
    monkeypatch.setattr(
        "hosts.cli.commands._echo",
        lambda text="", nl=True: captured.append(text),
    )
    return captured


def _persona(tier: str) -> str:
    """Mirrors hosts/cli/__main__.py::_tier_persona_name."""
    return {"cheap": "haiku", "standard": "sonnet", "smart": "opus"}.get(tier, tier)


class TestShowCurrent:
    """``/model`` with no arg prints provider, tier, model."""

    def test_bare_model_prints_three_rows(self, echoed):
        _handle_model_command("/model", _persona)
        joined = "\n".join(echoed)
        assert "Provider:" in joined
        assert "Tier:" in joined
        assert "Model:" in joined
        assert "cheap" in joined
        assert "haiku" in joined

    def test_alias_model_tier_works(self, echoed):
        """``/model_tier`` still goes through the same handler."""
        _handle_model_command("/model_tier", _persona)
        assert any("Tier:" in line for line in echoed)


class TestSwitchTier:
    """``/model <tier>`` mutates config and echoes the switch."""

    def test_switch_to_smart_mutates_state(self, echoed):
        _handle_model_command("/model smart", _persona)
        assert config.get_tier() == "smart"
        joined = "\n".join(echoed)
        assert "switched to smart" in joined
        assert "opus" in joined

    def test_switch_normalizes_case(self, echoed):
        _handle_model_command("/model STANDARD", _persona)
        assert config.get_tier() == "standard"

    def test_alias_model_tier_with_arg_switches(self, echoed):
        _handle_model_command("/model_tier smart", _persona)
        assert config.get_tier() == "smart"


class TestErrorPath:
    """Unknown tier echoes the error and leaves config untouched."""

    def test_unknown_tier_does_not_mutate(self, echoed):
        _handle_model_command("/model haiku", _persona)
        assert config.get_tier() == "cheap"
        joined = "\n".join(echoed)
        assert "unknown tier" in joined
