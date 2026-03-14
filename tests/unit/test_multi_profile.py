"""Tests for multi-profile support, cinematic loading phases, and profile select logic."""

from __future__ import annotations

import json

import pytest


class TestMultiProfileBackend:
    """Test multi-profile CRUD, switching, listing, migration."""

    @pytest.fixture(autouse=True)
    def _setup_dirs(self, tmp_path, monkeypatch):
        """Redirect all profile storage to a temp directory."""
        import kourai_common.player as player_mod

        self.player_dir = tmp_path / ".kourai_khryseai"
        self.profiles_dir = self.player_dir / "profiles"
        self.active_file = self.player_dir / "active_profile.txt"
        self.legacy_file = self.player_dir / "player.json"

        monkeypatch.setattr(player_mod, "PLAYER_DIR", self.player_dir)
        monkeypatch.setattr(player_mod, "PROFILES_DIR", self.profiles_dir)
        monkeypatch.setattr(player_mod, "ACTIVE_PROFILE_FILE", self.active_file)
        monkeypatch.setattr(player_mod, "_LEGACY_PLAYER_FILE", self.legacy_file)

    def test_save_creates_profile_in_profiles_dir(self):
        from kourai_common.player import PlayerProfile

        p = PlayerProfile(display_name="AJ", role="divine")
        p.save()

        profile_path = self.profiles_dir / f"{p.player_id}.json"
        assert profile_path.exists()
        data = json.loads(profile_path.read_text())
        assert data["display_name"] == "AJ"
        assert data["role"] == "divine"

    def test_load_by_id(self):
        from kourai_common.player import PlayerProfile

        p = PlayerProfile(display_name="TestUser")
        p.save()

        loaded = PlayerProfile.load(p.player_id)
        assert loaded is not None
        assert loaded.display_name == "TestUser"
        assert loaded.player_id == p.player_id

    def test_load_active_profile(self):
        from kourai_common.player import PlayerProfile, set_active_profile

        p = PlayerProfile(display_name="ActiveUser")
        p.save()
        set_active_profile(p.player_id)

        loaded = PlayerProfile.load()
        assert loaded is not None
        assert loaded.display_name == "ActiveUser"

    def test_load_returns_none_when_no_profiles(self):
        from kourai_common.player import PlayerProfile

        assert PlayerProfile.load() is None

    def test_list_profiles_empty(self):
        from kourai_common.player import list_profiles

        assert list_profiles() == []

    def test_list_profiles_multiple(self):
        from kourai_common.player import (
            PlayerProfile,
            list_profiles,
            set_active_profile,
        )

        p1 = PlayerProfile(display_name="Player1", role="divine", sovereignty=80)
        p1.save()
        p2 = PlayerProfile(display_name="Player2", role="mortal", devotion=60)
        p2.save()
        set_active_profile(p1.player_id)

        profiles = list_profiles()
        assert len(profiles) == 2

        names = {p["display_name"] for p in profiles}
        assert names == {"Player1", "Player2"}

        active_profiles = [p for p in profiles if p["is_active"]]
        assert len(active_profiles) == 1
        assert active_profiles[0]["display_name"] == "Player1"

    def test_switch_profile(self):
        from kourai_common.player import (
            PlayerProfile,
            get_active_profile_id,
            set_active_profile,
            switch_profile,
        )

        p1 = PlayerProfile(display_name="First")
        p1.save()
        p2 = PlayerProfile(display_name="Second")
        p2.save()
        set_active_profile(p1.player_id)

        result = switch_profile(p2.player_id)
        assert result is not None
        assert result.display_name == "Second"
        assert get_active_profile_id() == p2.player_id

    def test_delete_profile(self):
        from kourai_common.player import PlayerProfile, delete_profile, list_profiles

        p = PlayerProfile(display_name="ToDelete")
        p.save()

        assert delete_profile(p.player_id) is True
        assert list_profiles() == []

    def test_delete_active_profile_clears_active(self):
        from kourai_common.player import (
            PlayerProfile,
            delete_profile,
            get_active_profile_id,
            set_active_profile,
        )

        p = PlayerProfile(display_name="Active")
        p.save()
        set_active_profile(p.player_id)

        delete_profile(p.player_id)
        assert get_active_profile_id() is None

    def test_delete_nonexistent_returns_false(self):
        from kourai_common.player import delete_profile

        assert delete_profile("nonexistent_id") is False

    def test_needs_onboarding_when_no_profiles(self):
        from kourai_common.player import needs_onboarding

        assert needs_onboarding() is True

    def test_needs_onboarding_false_when_profiles_exist(self):
        from kourai_common.player import PlayerProfile, needs_onboarding

        p = PlayerProfile(display_name="Someone")
        p.save()
        assert needs_onboarding() is False

    def test_legacy_migration(self):
        """Test that a legacy player.json gets migrated to profiles/."""
        from kourai_common.player import PlayerProfile

        # Write a legacy profile
        self.player_dir.mkdir(parents=True, exist_ok=True)
        legacy_data = {
            "player_id": "legacy123",
            "display_name": "LegacyPlayer",
            "role": "mortal",
            "sovereignty": 42,
            "devotion": 58,
        }
        self.legacy_file.write_text(json.dumps(legacy_data))

        # Load should find and migrate it
        loaded = PlayerProfile.load()
        assert loaded is not None
        assert loaded.display_name == "LegacyPlayer"
        assert loaded.sovereignty == 42

        # Should now exist in profiles/
        migrated_path = self.profiles_dir / "legacy123.json"
        assert migrated_path.exists()

        # Legacy file should be renamed
        assert not self.legacy_file.exists()
        assert self.legacy_file.with_suffix(".json.migrated").exists()

    def test_profile_data_in_list(self):
        """Verify list_profiles returns all expected fields."""
        from kourai_common.player import (
            PlayerProfile,
            list_profiles,
            set_active_profile,
        )

        p = PlayerProfile(
            display_name="FullProfile",
            role="devoted",
            title="The Beloved",
            pronouns="she/her",
            sovereignty=30,
            devotion=85,
            total_sessions=42,
        )
        p.save()
        set_active_profile(p.player_id)

        profiles = list_profiles()
        assert len(profiles) == 1
        prof = profiles[0]
        assert prof["display_name"] == "FullProfile"
        assert prof["role"] == "devoted"
        assert prof["title"] == "The Beloved"
        assert prof["pronouns"] == "she/her"
        assert prof["sovereignty"] == 30
        assert prof["devotion"] == 85
        assert prof["total_sessions"] == 42
        assert prof["is_active"] is True


class TestCinematicPhases:
    """Test loading screen phase constants and timing logic."""

    def test_phases_are_sequential(self):
        from hosts.gui.loading_screen import (
            PHASE_CARD_1,
            PHASE_CARD_2,
            PHASE_FADE_OUT,
            PHASE_READY,
            PHASE_SPLASH,
        )

        assert PHASE_CARD_1 < PHASE_CARD_2 < PHASE_SPLASH < PHASE_READY < PHASE_FADE_OUT

    def test_card_timing_constants(self):
        from hosts.gui.loading_screen import _CARD_FADE_IN, _CARD_FADE_OUT, _CARD_HOLD

        # Cards should have reasonable timing
        assert _CARD_FADE_IN > 0
        assert _CARD_HOLD > 0
        assert _CARD_FADE_OUT > 0
        total = _CARD_FADE_IN + _CARD_HOLD + _CARD_FADE_OUT
        assert 2.0 < total < 6.0  # Reasonable range for a cinematic card


class TestProfileSelectScreen:
    """Test profile select logic (non-rendering)."""

    def test_card_rect_positioning(self):
        """Test that card rects are within screen bounds."""
        from hosts.gui.profile_select import _card_rect

        rect = _card_rect(1280, 720, 0, 0, 3)
        assert rect is not None
        assert rect.x > 0
        assert rect.y > 0
        assert rect.right < 1280
        assert rect.bottom < 720

    def test_card_rect_scroll_hides_offscreen(self):
        from hosts.gui.profile_select import _card_rect

        # With scroll_offset=2, index 0 and 1 should be hidden
        assert _card_rect(1280, 720, 0, 2, 10) is None
        assert _card_rect(1280, 720, 1, 2, 10) is None
        # Index 2 should now be visible (visible_idx = 0)
        assert _card_rect(1280, 720, 2, 2, 10) is not None

    def test_new_game_rect_below_cards(self):
        from hosts.gui.profile_select import _card_rect, _new_game_rect

        last_card = _card_rect(1280, 720, 2, 0, 3)
        ng_rect = _new_game_rect(1280, 720, 3, 0)
        assert last_card is not None
        assert ng_rect.y > last_card.bottom

    def test_confirm_delete_rect_centered(self):
        from hosts.gui.profile_select import _confirm_delete_rect

        rect = _confirm_delete_rect(1280, 720)
        center_x = rect.x + rect.width // 2
        center_y = rect.y + rect.height // 2
        assert abs(center_x - 640) < 2
        assert abs(center_y - 360) < 2
