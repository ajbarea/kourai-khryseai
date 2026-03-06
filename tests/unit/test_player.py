"""Tests for the player identity, memory, and alignment system."""

import sqlite3
from unittest.mock import patch

import pytest

from kourai_common.player import (
    PlayerProfile,
    _ensure_player_tables,
    add_player_memory,
    advance_romance,
    build_player_context,
    decay_memories,
    delete_player_memory,
    export_player_data,
    get_affinity,
    get_affinity_tier,
    get_all_affinities,
    get_player_memories,
    import_player_data,
    retrieve_relevant_memories,
    transfer_gossip_memories,
    update_affinity,
    wipe_player_memories,
)

# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    """Use an in-memory SQLite DB for every test, fully isolated."""
    db_path = tmp_path / "test_memory.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)

    # Create base tables (normally done by memory._get_db)
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

    # Ensure player tables are created on this connection
    import kourai_common.player as player_mod

    player_mod._tables_initialized = False
    _ensure_player_tables(conn)

    # Patch _get_player_db to return our test connection
    monkeypatch.setattr(player_mod, "_get_player_db", lambda: conn)

    yield conn
    conn.close()


@pytest.fixture
def profile():
    """A test player profile."""
    return PlayerProfile(
        display_name="AJ",
        tts_name="ay jay",
        title="The Architect",
        role="divine",
        pronouns="he/him",
    )


# ── PlayerProfile Tests ────────────────────────────────────────────────


class TestPlayerProfile:
    def test_creates_with_uuid(self):
        p = PlayerProfile()
        assert len(p.player_id) == 32  # hex UUID

    def test_creates_with_timestamp(self):
        p = PlayerProfile()
        assert p.created_at != ""

    def test_archetype_professional(self):
        p = PlayerProfile(sovereignty=10, devotion=10)
        assert p.archetype == "professional"

    def test_archetype_tyrant(self):
        p = PlayerProfile(sovereignty=70, devotion=10)
        assert p.archetype == "tyrant"

    def test_archetype_patron(self):
        p = PlayerProfile(sovereignty=10, devotion=70)
        assert p.archetype == "patron"

    def test_archetype_commander(self):
        p = PlayerProfile(sovereignty=70, devotion=70)
        assert p.archetype == "commander"

    def test_is_commander_requires_80(self):
        p = PlayerProfile(sovereignty=79, devotion=80)
        assert not p.is_commander
        p.sovereignty = 80
        assert p.is_commander

    def test_add_sovereignty_clamped(self):
        p = PlayerProfile(sovereignty=95)
        p.add_sovereignty(10)
        assert p.sovereignty == 100
        p.add_sovereignty(-200)
        assert p.sovereignty == 0

    def test_add_devotion_clamped(self):
        p = PlayerProfile(devotion=5)
        p.add_devotion(-10)
        assert p.devotion == 0
        p.add_devotion(150)
        assert p.devotion == 100

    def test_alignment_compatibility_kallos_high_devotion(self):
        """Kallos strongly prefers devotion — high devotion should give > 1.0 multiplier."""
        p = PlayerProfile(sovereignty=10, devotion=90)
        mult = p.alignment_compatibility("kallos")
        assert mult > 1.0

    def test_alignment_compatibility_kallos_high_sovereignty(self):
        """Kallos dislikes sovereignty — high sovereignty should reduce multiplier."""
        p = PlayerProfile(sovereignty=90, devotion=10)
        mult = p.alignment_compatibility("kallos")
        assert mult < 1.0

    def test_alignment_compatibility_unknown_agent(self):
        p = PlayerProfile(sovereignty=50, devotion=50)
        assert p.alignment_compatibility("unknown") == 1.0

    def test_serialization_roundtrip(self):
        p = PlayerProfile(
            display_name="Test",
            sovereignty=42,
            devotion=78,
            romance_targets=["metis"],
        )
        data = p.to_dict()
        p2 = PlayerProfile.from_dict(data)
        assert p2.display_name == "Test"
        assert p2.sovereignty == 42
        assert p2.devotion == 78
        assert p2.romance_targets == ["metis"]

    def test_from_dict_ignores_unknown_fields(self):
        data = {"display_name": "X", "unknown_field": "should be ignored"}
        p = PlayerProfile.from_dict(data)
        assert p.display_name == "X"

    def test_save_and_load(self, tmp_path):
        with (
            patch("kourai_common.player.PLAYER_FILE", tmp_path / "player.json"),
            patch("kourai_common.player.PLAYER_DIR", tmp_path),
        ):
            p = PlayerProfile(display_name="SaveTest", sovereignty=55)
            p.save()

            loaded = PlayerProfile.load()
            assert loaded is not None
            assert loaded.display_name == "SaveTest"
            assert loaded.sovereignty == 55

    def test_load_returns_none_when_missing(self, tmp_path):
        with patch("kourai_common.player.PLAYER_FILE", tmp_path / "nonexistent.json"):
            assert PlayerProfile.load() is None

    def test_load_or_default(self, tmp_path):
        with patch("kourai_common.player.PLAYER_FILE", tmp_path / "nonexistent.json"):
            p = PlayerProfile.load_or_default()
            assert p.display_name == ""


# ── Memory CRUD Tests ──────────────────────────────────────────────────


class TestPlayerMemory:
    def test_add_and_retrieve(self, profile):
        mid = add_player_memory(
            profile.player_id, "Prefers dark themes", "preference", agent_name="kallos"
        )
        assert len(mid) == 32

        memories = get_player_memories(profile.player_id, agent_name="kallos")
        assert len(memories) == 1
        assert memories[0]["content"] == "Prefers dark themes"
        assert memories[0]["category"] == "preference"

    def test_shared_memory_visible_to_all(self, profile):
        add_player_memory(profile.player_id, "Player name is AJ", "fact", agent_name=None)

        # Should be visible when querying for any agent (include_shared=True)
        for agent in ["metis", "techne", "kallos"]:
            memories = get_player_memories(profile.player_id, agent_name=agent)
            assert len(memories) == 1

    def test_private_memory_not_visible_to_others(self, profile):
        add_player_memory(profile.player_id, "Secret observation", "moment", agent_name="metis")

        # Metis sees it
        assert len(get_player_memories(profile.player_id, agent_name="metis")) == 1

        # Techne doesn't (only shared memories, which there are none)
        techne_mems = get_player_memories(
            profile.player_id, agent_name="techne", include_shared=False
        )
        assert len(techne_mems) == 0

    def test_filter_by_category(self, profile):
        add_player_memory(profile.player_id, "Fact 1", "fact")
        add_player_memory(profile.player_id, "Pref 1", "preference")

        facts = get_player_memories(profile.player_id, category="fact")
        assert len(facts) == 1
        assert facts[0]["category"] == "fact"

    def test_delete_memory(self, profile):
        mid = add_player_memory(profile.player_id, "To delete", "fact")
        delete_player_memory(mid)
        assert len(get_player_memories(profile.player_id)) == 0

    def test_wipe_all(self, profile):
        add_player_memory(profile.player_id, "Mem 1", "fact")
        add_player_memory(profile.player_id, "Mem 2", "preference")
        update_affinity(profile.player_id, "metis", 0.5)

        wipe_player_memories(profile.player_id)
        assert len(get_player_memories(profile.player_id)) == 0
        assert get_affinity(profile.player_id, "metis")["affinity_score"] == 0.0

    def test_retrieve_relevant_scores_by_importance(self, profile):
        add_player_memory(profile.player_id, "Low importance", "fact", importance=0.1)
        add_player_memory(profile.player_id, "High importance", "fact", importance=0.9)

        top = retrieve_relevant_memories(profile.player_id, "metis", top_k=1)
        assert len(top) == 1
        assert top[0]["content"] == "High importance"


# ── Gossip Transfer Tests ──────────────────────────────────────────────


class TestGossipTransfer:
    def test_transfer_copies_to_recipients(self, profile):
        mid = add_player_memory(
            profile.player_id, "AJ codes at midnight", "pattern", agent_name="techne"
        )

        count = transfer_gossip_memories("techne", ["metis", "kallos"], [mid])
        assert count == 2

        # Both recipients now have it
        for agent in ["metis", "kallos"]:
            mems = get_player_memories(profile.player_id, agent_name=agent, include_shared=False)
            assert any(m["content"] == "AJ codes at midnight" for m in mems)
            assert any(m["source"] == "gossip:techne" for m in mems)

    def test_transfer_no_duplicates(self, profile):
        mid = add_player_memory(profile.player_id, "Same memory", "fact", agent_name="techne")

        transfer_gossip_memories("techne", ["metis"], [mid])
        transfer_gossip_memories("techne", ["metis"], [mid])  # Second time

        mems = get_player_memories(profile.player_id, agent_name="metis", include_shared=False)
        matching = [m for m in mems if m["content"] == "Same memory"]
        assert len(matching) == 1  # Not duplicated


# ── Affinity Tests ──────────────────────────────────────────────────────


class TestAffinity:
    def test_default_affinity(self, profile):
        aff = get_affinity(profile.player_id, "metis")
        assert aff["affinity_score"] == 0.0
        assert aff["interaction_count"] == 0
        assert aff["romance_stage"] == "none"

    def test_update_affinity(self, profile):
        new = update_affinity(profile.player_id, "metis", 0.3)
        assert new == pytest.approx(0.3)

        aff = get_affinity(profile.player_id, "metis")
        assert aff["interaction_count"] == 1

    def test_affinity_with_alignment_multiplier(self, profile):
        # Kallos loves devotion
        profile.devotion = 90
        mult = profile.alignment_compatibility("kallos")
        new = update_affinity(profile.player_id, "kallos", 0.1, alignment_multiplier=mult)
        assert new > 0.1  # Multiplier boosted it

    def test_affinity_clamped(self, profile):
        update_affinity(profile.player_id, "metis", 2.0)  # Over max
        aff = get_affinity(profile.player_id, "metis")
        assert aff["affinity_score"] <= 1.0

    def test_get_all_affinities(self, profile):
        update_affinity(profile.player_id, "metis", 0.3)
        update_affinity(profile.player_id, "techne", 0.5)

        all_aff = get_all_affinities(profile.player_id)
        assert "metis" in all_aff
        assert "techne" in all_aff

    def test_affinity_tiers(self):
        assert get_affinity_tier(0.0) == 0  # Stranger
        assert get_affinity_tier(0.15) == 1  # Acquaintance
        assert get_affinity_tier(0.4) == 2  # Companion
        assert get_affinity_tier(0.7) == 3  # Bonded


# ── Romance Tests ───────────────────────────────────────────────────────


class TestRomance:
    def test_advance_requires_high_affinity(self, profile):
        update_affinity(profile.player_id, "metis", 0.3)
        result = advance_romance(profile.player_id, "metis")
        assert result is None  # Not bonded enough

    def test_advance_progresses_stages(self, profile):
        update_affinity(profile.player_id, "metis", 0.8)

        stage = advance_romance(profile.player_id, "metis")
        assert stage == "spark"

        stage = advance_romance(profile.player_id, "metis")
        assert stage == "kindling"

        stage = advance_romance(profile.player_id, "metis")
        assert stage == "flame"

        stage = advance_romance(profile.player_id, "metis")
        assert stage == "bonfire"

        # Already max
        stage = advance_romance(profile.player_id, "metis")
        assert stage is None


# ── Prompt Context Builder Tests ────────────────────────────────────────


class TestBuildPlayerContext:
    def test_empty_profile_returns_empty(self):
        p = PlayerProfile()  # No display_name
        assert build_player_context(p, "metis") == ""

    def test_includes_identity(self, profile):
        ctx = build_player_context(profile, "metis")
        assert "AJ" in ctx
        assert "ay jay" in ctx
        assert "The Architect" in ctx
        assert "Divine" in ctx

    def test_includes_alignment(self, profile):
        profile.sovereignty = 42
        profile.devotion = 78
        ctx = build_player_context(profile, "metis")
        assert "42/100" in ctx
        assert "78/100" in ctx
        assert "Patron" in ctx  # devotion > 60, sovereignty < 60

    def test_includes_relationship(self, profile):
        update_affinity(profile.player_id, "metis", 0.5)
        ctx = build_player_context(profile, "metis")
        assert "Companion" in ctx  # 0.5 affinity = tier 2

    def test_includes_memories(self, profile):
        add_player_memory(profile.player_id, "Likes dark mode", "preference")
        ctx = build_player_context(profile, "metis")
        assert "Likes dark mode" in ctx

    def test_gossip_source_tagged(self, profile):
        add_player_memory(
            profile.player_id,
            "Codes at night",
            "pattern",
            agent_name="metis",
            source="gossip:techne",
        )
        ctx = build_player_context(profile, "metis")
        assert "via techne's gossip" in ctx

    def test_romance_shown_when_active(self, profile):
        update_affinity(profile.player_id, "metis", 0.8)
        advance_romance(profile.player_id, "metis")
        ctx = build_player_context(profile, "metis")
        assert "Spark" in ctx

    def test_romance_hidden_when_opted_out(self, profile):
        profile.romance_opted_out = True
        update_affinity(profile.player_id, "metis", 0.8)
        advance_romance(profile.player_id, "metis")
        ctx = build_player_context(profile, "metis")
        assert "Romance" not in ctx


# ── Memory Decay Tests ──────────────────────────────────────────────────


class TestMemoryDecay:
    def test_no_decay_for_achievements(self, profile):

        add_player_memory(profile.player_id, "First pipeline", "achievement", importance=0.01)
        pruned = decay_memories(profile.player_id, half_life_days=0.001, min_importance=0.5)
        assert pruned == 0  # Achievements are protected

    def test_prunes_low_importance_memories(self, profile):

        # Add a very old, low-importance memory
        mid = add_player_memory(profile.player_id, "Old note", "moment", importance=0.06)
        # Manually backdate it
        from datetime import UTC, datetime, timedelta

        import kourai_common.player as player_mod

        old_date = (datetime.now(UTC) - timedelta(days=200)).isoformat()
        conn = player_mod._get_player_db()
        conn.execute(
            "UPDATE player_memories SET last_accessed = ? WHERE memory_id = ?",
            (old_date, mid),
        )
        conn.commit()

        pruned = decay_memories(profile.player_id, half_life_days=7.0, min_importance=0.04)
        assert pruned == 1

    def test_preferences_protected(self, profile):

        add_player_memory(profile.player_id, "Likes dark mode", "preference", importance=0.01)
        pruned = decay_memories(profile.player_id, half_life_days=0.001, min_importance=0.5)
        assert pruned == 0


# ── Export / Import Tests ───────────────────────────────────────────────


class TestExportImport:
    def test_export_roundtrip(self, profile, tmp_path, monkeypatch):

        # Save profile to disk so export can find it
        monkeypatch.setattr("kourai_common.player.PLAYER_FILE", tmp_path / "player.json")
        monkeypatch.setattr("kourai_common.player.PLAYER_DIR", tmp_path)
        profile.save()

        add_player_memory(profile.player_id, "Test memory", "fact", importance=0.7)
        update_affinity(profile.player_id, "metis", 0.5)

        data = export_player_data(profile.player_id)
        assert data["version"] == 1
        assert data["profile"]["display_name"] == "AJ"
        assert len(data["memories"]) >= 1
        assert "metis" in data["affinities"]

    def test_import_creates_profile(self, tmp_path, monkeypatch):

        monkeypatch.setattr("kourai_common.player.PLAYER_FILE", tmp_path / "player.json")
        monkeypatch.setattr("kourai_common.player.PLAYER_DIR", tmp_path)

        data = {
            "version": 1,
            "profile": {
                "player_id": "test123",
                "display_name": "TestUser",
                "tts_name": "test user",
                "title": "The Tester",
                "role": "mortal",
                "pronouns": "they/them",
            },
            "memories": [{"content": "Imported memory", "category": "fact", "importance": 0.8}],
            "affinities": {
                "kallos": {"affinity_score": 0.3, "interaction_count": 5, "romance_stage": "none"}
            },
        }

        imported = import_player_data(data)
        assert imported.display_name == "TestUser"
        assert imported.player_id == "test123"

        # Verify memories imported
        mems = get_player_memories("test123", include_shared=True)
        assert any(m["content"] == "Imported memory" for m in mems)

    def test_import_rejects_bad_version(self):

        with pytest.raises(ValueError, match="Unsupported export version"):
            import_player_data({"version": 99})

    def test_import_merge_mode(self, profile, tmp_path, monkeypatch):

        monkeypatch.setattr("kourai_common.player.PLAYER_FILE", tmp_path / "player.json")
        monkeypatch.setattr("kourai_common.player.PLAYER_DIR", tmp_path)
        profile.save()

        # Add existing memory
        add_player_memory(profile.player_id, "Existing", "fact")

        data = {
            "version": 1,
            "profile": profile.to_dict(),
            "memories": [{"content": "New imported", "category": "fact", "importance": 0.6}],
            "affinities": {},
        }

        import_player_data(data, merge=True)
        mems = get_player_memories(profile.player_id, include_shared=True)
        contents = [m["content"] for m in mems]
        assert "Existing" in contents
        assert "New imported" in contents


# ── Enriched System Prompt Tests ────────────────────────────────────────


class TestEnrichedSystemPrompt:
    def test_returns_base_when_no_profile(self, monkeypatch):
        from kourai_common.player import get_enriched_system_prompt

        import kourai_common.player as player_mod

        player_mod._profile_cache = None
        player_mod._profile_cache_ts = 0.0
        monkeypatch.setattr(PlayerProfile, "load", staticmethod(lambda: None))

        result = get_enriched_system_prompt("base prompt", "metis")
        assert result == "base prompt"

    def test_appends_player_context_when_profile_exists(self, profile, monkeypatch):
        from kourai_common.player import get_enriched_system_prompt

        import kourai_common.player as player_mod

        player_mod._profile_cache = None
        player_mod._profile_cache_ts = 0.0
        monkeypatch.setattr(PlayerProfile, "load", staticmethod(lambda: profile))

        result = get_enriched_system_prompt("base prompt", "metis")
        assert "base prompt" in result
        assert "PLAYER IDENTITY" in result
        assert "AJ" in result
