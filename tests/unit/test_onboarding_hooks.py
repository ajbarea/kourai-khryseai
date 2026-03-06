"""Tests for CLI onboarding and post-task hooks."""

import sqlite3

import pytest

from kourai_common.player import (
    PlayerProfile,
    _ensure_player_tables,
    get_affinity,
    get_player_memories,
)

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    """Isolated DB for every test."""
    db_path = tmp_path / "test_memory.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            context_id TEXT, agent_name TEXT, idx INTEGER,
            role TEXT, content TEXT, summarized BOOLEAN DEFAULT 0,
            PRIMARY KEY (context_id, agent_name, idx)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_states (
            context_id TEXT, agent_name TEXT, state_json TEXT,
            PRIMARY KEY (context_id, agent_name)
        )
        """
    )
    conn.commit()

    import kourai_common.player as player_mod

    player_mod._tables_initialized = False
    _ensure_player_tables(conn)
    monkeypatch.setattr(player_mod, "_get_player_db", lambda: conn)
    monkeypatch.setattr(player_mod, "PLAYER_DIR", tmp_path)
    monkeypatch.setattr(player_mod, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(player_mod, "ACTIVE_PROFILE_FILE", tmp_path / "active_profile.txt")
    monkeypatch.setattr(player_mod, "_LEGACY_PLAYER_FILE", tmp_path / "player.json")

    # Reset profile cache
    player_mod._profile_cache = None
    player_mod._profile_cache_ts = 0.0

    yield conn
    conn.close()


# ── CLI Onboarding Tests ───────────────────────────────────────────────


class TestOnboarding:
    def test_needs_onboarding_when_no_profile(self, tmp_path, monkeypatch):
        monkeypatch.setattr("kourai_common.player.PROFILES_DIR", tmp_path / "profiles")
        monkeypatch.setattr(
            "kourai_common.player.ACTIVE_PROFILE_FILE", tmp_path / "active_profile.txt"
        )
        monkeypatch.setattr("kourai_common.player._LEGACY_PLAYER_FILE", tmp_path / "player.json")
        from hosts.cli.onboarding import needs_onboarding

        assert needs_onboarding() is True

    def test_needs_onboarding_false_when_profile_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr("kourai_common.player.PROFILES_DIR", tmp_path / "profiles")
        monkeypatch.setattr(
            "kourai_common.player.ACTIVE_PROFILE_FILE", tmp_path / "active_profile.txt"
        )
        monkeypatch.setattr("kourai_common.player._LEGACY_PLAYER_FILE", tmp_path / "player.json")
        monkeypatch.setattr("kourai_common.player.PLAYER_DIR", tmp_path)
        profile = PlayerProfile(display_name="AJ")
        profile.save()

        from kourai_common.player import set_active_profile

        set_active_profile(profile.player_id)

        from hosts.cli.onboarding import needs_onboarding

        assert needs_onboarding() is False

    def test_run_onboarding_creates_profile(self, tmp_path, monkeypatch):
        monkeypatch.setattr("kourai_common.player.PROFILES_DIR", tmp_path / "profiles")
        monkeypatch.setattr(
            "kourai_common.player.ACTIVE_PROFILE_FILE", tmp_path / "active_profile.txt"
        )
        monkeypatch.setattr("kourai_common.player._LEGACY_PLAYER_FILE", tmp_path / "player.json")
        monkeypatch.setattr("kourai_common.player.PLAYER_DIR", tmp_path)

        from hosts.cli.onboarding import run_onboarding

        # Simulate user input: name, tts_name (enter=same), title, role=1, pronouns=1
        inputs = iter(["TestPlayer", "", "The Tester", "1", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        profile = run_onboarding()
        assert profile.display_name == "TestPlayer"
        assert profile.tts_name == "TestPlayer"  # Same as display when enter pressed
        assert profile.title == "The Tester"
        assert profile.role == "divine"  # First option
        assert profile.pronouns == "he/him"  # First option

        # Verify saved to disk
        loaded = PlayerProfile.load()
        assert loaded is not None
        assert loaded.display_name == "TestPlayer"

    def test_increment_session(self, tmp_path, monkeypatch):
        monkeypatch.setattr("kourai_common.player.PROFILES_DIR", tmp_path / "profiles")
        monkeypatch.setattr(
            "kourai_common.player.ACTIVE_PROFILE_FILE", tmp_path / "active_profile.txt"
        )
        monkeypatch.setattr("kourai_common.player._LEGACY_PLAYER_FILE", tmp_path / "player.json")
        monkeypatch.setattr("kourai_common.player.PLAYER_DIR", tmp_path)
        profile = PlayerProfile(display_name="AJ", total_sessions=5)
        profile.save()

        from kourai_common.player import set_active_profile

        set_active_profile(profile.player_id)

        from hosts.cli.onboarding import increment_session

        increment_session()
        loaded = PlayerProfile.load()
        assert loaded.total_sessions == 6


# ── Affinity Tracking Tests ────────────────────────────────────────────


class TestAffinityTracking:
    def test_track_interaction_updates_affinity(self):
        from kourai_common.hooks import track_interaction

        profile = PlayerProfile(display_name="AJ", sovereignty=50, devotion=50)
        track_interaction(profile.player_id, "metis", profile=profile, success=True)

        aff = get_affinity(profile.player_id, "metis")
        assert aff["affinity_score"] > 0
        assert aff["interaction_count"] == 1

    def test_track_failure_gives_less_affinity(self):
        from kourai_common.hooks import track_interaction

        profile = PlayerProfile(display_name="AJ")
        track_interaction(profile.player_id, "techne", profile=profile, success=True)
        success_score = get_affinity(profile.player_id, "techne")["affinity_score"]

        profile2 = PlayerProfile(display_name="AJ")
        track_interaction(profile2.player_id, "kallos", profile=profile2, success=False)
        fail_score = get_affinity(profile2.player_id, "kallos")["affinity_score"]

        assert success_score > fail_score

    def test_track_noop_without_player_id(self):
        from kourai_common.hooks import track_interaction

        # Should not raise
        track_interaction("", "metis")

    def test_alignment_multiplier_applied(self):
        from kourai_common.hooks import track_interaction

        # Kallos prefers devotion
        profile_devoted = PlayerProfile(display_name="A", sovereignty=0, devotion=100)
        track_interaction(profile_devoted.player_id, "kallos", profile=profile_devoted)
        dev_score = get_affinity(profile_devoted.player_id, "kallos")["affinity_score"]

        # vs sovereignty-heavy player
        profile_sov = PlayerProfile(display_name="B", sovereignty=100, devotion=0)
        track_interaction(profile_sov.player_id, "kallos", profile=profile_sov)
        sov_score = get_affinity(profile_sov.player_id, "kallos")["affinity_score"]

        assert dev_score > sov_score


# ── Memory Extraction Tests ────────────────────────────────────────────


class TestMemoryExtraction:
    def test_extracts_preference_from_user_input(self):
        from kourai_common.hooks import extract_memories_from_interaction

        profile = PlayerProfile(display_name="AJ")
        mids = extract_memories_from_interaction(
            profile.player_id,
            "techne",
            "I prefer using dark mode for everything in my editor",
            "Sure, I'll update the theme.",
        )
        assert len(mids) >= 1
        mems = get_player_memories(profile.player_id, agent_name="techne")
        assert any("dark mode" in m["content"] for m in mems)

    def test_extracts_achievement_from_output(self):
        from kourai_common.hooks import extract_memories_from_interaction

        profile = PlayerProfile(display_name="AJ")
        mids = extract_memories_from_interaction(
            profile.player_id,
            "dokimasia",
            "Run the tests please",
            "All 42 tests passed!",
        )
        assert len(mids) >= 1
        mems = get_player_memories(profile.player_id, agent_name="dokimasia")
        assert any(m["category"] == "achievement" for m in mems)

    def test_no_extraction_from_empty_input(self):
        from kourai_common.hooks import extract_memories_from_interaction

        mids = extract_memories_from_interaction("pid", "metis", "", "output")
        assert mids == []

    def test_no_extraction_without_player_id(self):
        from kourai_common.hooks import extract_memories_from_interaction

        mids = extract_memories_from_interaction("", "metis", "I like X", "ok")
        assert mids == []
