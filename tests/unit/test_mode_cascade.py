"""Mode cascade — `apply_mode_cascade` writes the seven Puck-tutorial
settings to PlayerProfile.preferences + CLISettings in one pass.

Spec: docs/architecture/puck-first-run-tutorial.md Section 3.

Settings split across two stores by existing architecture:
- PlayerProfile.preferences (player-level): experience_mode,
  metrics_tracking_enabled, affinity_tracking_enabled,
  romance_nudges_enabled, gossip_nudges_enabled
- CLISettings (host-level): romance_enabled, gossip_enabled,
  metrics_tracking_enabled, romance_nudges_enabled, gossip_nudges_enabled

The metrics/nudges keys appear in BOTH stores by design — profile is
player-level source-of-truth, CLISettings is the host-active cache that
existing code reads from. The cascade writes both for consistency.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def _isolated_stores(tmp_path, monkeypatch):
    """Redirect both settings stores to a fresh tmp_path.

    PlayerProfile persists under `~/.kourai_khryseai/profiles/`;
    CLISettings persists at `<repo>/.cache/cli_settings.json`. Patch
    both to per-test temp paths so tests start clean and don't leak
    into the live install. Mirrors the pattern in
    `tests/unit/test_onboarding_hooks.py::_isolate_db`.
    """
    import kourai_common.player as player_mod

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    active_profile_file = tmp_path / "active_profile.txt"
    settings_path = tmp_path / "cli_settings.json"

    monkeypatch.setattr(player_mod, "PLAYER_DIR", tmp_path)
    monkeypatch.setattr(player_mod, "PROFILES_DIR", profiles_dir)
    monkeypatch.setattr(player_mod, "ACTIVE_PROFILE_FILE", active_profile_file)
    monkeypatch.setattr(player_mod, "_LEGACY_PLAYER_FILE", tmp_path / "player.json")
    # Reset the profile cache the shim module keeps to avoid cross-talk.
    if hasattr(player_mod, "_profile_cache"):
        player_mod._profile_cache = None
    if hasattr(player_mod, "_profile_cache_ts"):
        player_mod._profile_cache_ts = 0.0

    monkeypatch.setattr("hosts.cli.settings._SETTINGS_FILE", settings_path)

    yield active_profile_file, settings_path


def test_focused_cascade_writes_all_seven_to_focused_values(_isolated_stores):
    from hosts.cli.mode_cascade import apply_mode_cascade
    from hosts.cli.settings import CLISettings
    from kourai_common.player_profile import PlayerProfile

    PlayerProfile().save()  # baseline empty profile

    apply_mode_cascade("focused")

    profile = PlayerProfile.load()
    settings = CLISettings.load()
    # PlayerProfile.preferences side
    assert profile is not None
    assert profile.preferences["experience_mode"] == "focused"
    assert profile.preferences["metrics_tracking_enabled"] is False
    assert profile.preferences["affinity_tracking_enabled"] is False
    assert profile.preferences["romance_nudges_enabled"] is False
    assert profile.preferences["gossip_nudges_enabled"] is False
    # CLISettings side
    assert settings.romance_enabled is False
    assert settings.gossip_enabled is False
    assert settings.metrics_tracking_enabled is False
    assert settings.romance_nudges_enabled is False
    assert settings.gossip_nudges_enabled is False


def test_gamified_cascade_writes_all_seven_to_gamified_values(_isolated_stores):
    from hosts.cli.mode_cascade import apply_mode_cascade
    from hosts.cli.settings import CLISettings
    from kourai_common.player_profile import PlayerProfile

    PlayerProfile().save()

    apply_mode_cascade("gamified")

    profile = PlayerProfile.load()
    settings = CLISettings.load()
    assert profile is not None
    assert profile.preferences["experience_mode"] == "gamified"
    assert profile.preferences["metrics_tracking_enabled"] is True
    assert profile.preferences["affinity_tracking_enabled"] is True
    assert profile.preferences["romance_nudges_enabled"] is True
    assert profile.preferences["gossip_nudges_enabled"] is True
    # romance_enabled stays False in BOTH paths per spec — Cupid is a
    # separate two-step opt-in, not piggy-backed on the mode cascade.
    assert settings.romance_enabled is False
    assert settings.gossip_enabled is True
    assert settings.metrics_tracking_enabled is True
    assert settings.romance_nudges_enabled is True
    assert settings.gossip_nudges_enabled is True


def test_cascade_is_idempotent(_isolated_stores):
    """Re-applying the same mode produces identical state — both
    stores' loaded values match before and after."""
    from hosts.cli.mode_cascade import apply_mode_cascade
    from hosts.cli.settings import CLISettings
    from kourai_common.player_profile import PlayerProfile

    PlayerProfile().save()

    apply_mode_cascade("gamified")
    first_prefs = dict(PlayerProfile.load().preferences)  # type: ignore[union-attr]
    first_settings = CLISettings.load()

    apply_mode_cascade("gamified")
    second_prefs = dict(PlayerProfile.load().preferences)  # type: ignore[union-attr]
    second_settings = CLISettings.load()

    cascade_keys = {
        "experience_mode",
        "metrics_tracking_enabled",
        "affinity_tracking_enabled",
        "romance_nudges_enabled",
        "gossip_nudges_enabled",
    }
    assert {k: first_prefs[k] for k in cascade_keys} == {k: second_prefs[k] for k in cascade_keys}
    for field in (
        "romance_enabled",
        "gossip_enabled",
        "metrics_tracking_enabled",
        "romance_nudges_enabled",
        "gossip_nudges_enabled",
    ):
        assert getattr(first_settings, field) == getattr(second_settings, field)


def test_cascade_overrides_individual_toggles(_isolated_stores):
    """The cascade is opinionated — it overrides individual settings
    a player may have toggled independently. Flipping focused → gamified
    after the player had turned metrics OFF still ends gamified-default
    (metrics ON). This is the spec's "single source of truth" behavior;
    callers are responsible for warning players if they want the
    individual-respecting variant."""
    from hosts.cli.mode_cascade import apply_mode_cascade
    from hosts.cli.settings import CLISettings
    from kourai_common.player_profile import PlayerProfile

    profile = PlayerProfile()
    profile.preferences["metrics_tracking_enabled"] = False
    profile.save()
    settings = CLISettings()
    settings.metrics_tracking_enabled = False
    settings.gossip_enabled = False
    settings.save()

    apply_mode_cascade("gamified")

    new_profile = PlayerProfile.load()
    new_settings = CLISettings.load()
    assert new_profile is not None
    assert new_profile.preferences["metrics_tracking_enabled"] is True
    assert new_settings.metrics_tracking_enabled is True
    assert new_settings.gossip_enabled is True


def test_cascade_preserves_unrelated_preferences(_isolated_stores):
    """Cascade touches only the seven cascade keys. Other preference
    bucket entries (display_name analog, virtue_tracking_enabled,
    custom keys) survive intact."""
    from hosts.cli.mode_cascade import apply_mode_cascade
    from kourai_common.player_profile import PlayerProfile

    profile = PlayerProfile(display_name="AJ")
    profile.preferences["virtue_tracking_enabled"] = True
    profile.preferences["custom_player_key"] = "preserved"
    profile.save()

    apply_mode_cascade("focused")

    new_profile = PlayerProfile.load()
    assert new_profile is not None
    assert new_profile.display_name == "AJ"  # core fields untouched
    assert new_profile.preferences["virtue_tracking_enabled"] is True
    assert new_profile.preferences["custom_player_key"] == "preserved"


def test_cascade_rejects_unknown_mode(_isolated_stores):
    from hosts.cli.mode_cascade import apply_mode_cascade

    with pytest.raises(ValueError, match="unknown mode"):
        apply_mode_cascade("hardcore")  # type: ignore[arg-type]


def test_cascade_no_op_when_no_active_profile(_isolated_stores, capsys):
    """No PlayerProfile on disk → CLISettings still gets written.

    Edge case for very first-launch where /settings might be invoked
    before onboarding (shouldn't happen in normal flow but the helper
    must not crash if it does)."""
    from hosts.cli.mode_cascade import apply_mode_cascade
    from hosts.cli.settings import CLISettings

    apply_mode_cascade("focused")  # no profile on disk

    settings = CLISettings.load()
    assert settings.gossip_enabled is False
    assert settings.metrics_tracking_enabled is False


def test_current_mode_reads_from_profile(_isolated_stores):
    from hosts.cli.mode_cascade import current_mode
    from kourai_common.player_profile import PlayerProfile

    profile = PlayerProfile()
    profile.preferences["experience_mode"] = "focused"
    profile.save()

    assert current_mode() == "focused"


def test_current_mode_defaults_to_gamified_when_unset(_isolated_stores):
    """Spec default is gamified — matches existing onboarding's
    keep-Puck = default behavior."""
    from hosts.cli.mode_cascade import current_mode
    from kourai_common.player_profile import PlayerProfile

    PlayerProfile().save()  # profile exists but no experience_mode key

    assert current_mode() == "gamified"


def test_current_mode_defaults_to_gamified_when_no_profile(_isolated_stores):
    from hosts.cli.mode_cascade import current_mode

    # No profile on disk at all.
    assert current_mode() == "gamified"


def test_current_mode_normalizes_unknown_strings_to_gamified(_isolated_stores):
    """Forward-compat: an old profile with a deprecated mode value
    shouldn't break — fall back to gamified rather than crash."""
    from hosts.cli.mode_cascade import current_mode
    from kourai_common.player_profile import PlayerProfile

    profile = PlayerProfile()
    profile.preferences["experience_mode"] = "hardcore"  # not in spec
    profile.save()

    assert current_mode() == "gamified"
