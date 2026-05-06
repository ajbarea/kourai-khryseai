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
            patch("kourai_common.player.PROFILES_DIR", tmp_path / "profiles"),
            patch("kourai_common.player.ACTIVE_PROFILE_FILE", tmp_path / "active.txt"),
            patch("kourai_common.player.PLAYER_DIR", tmp_path),
            patch("kourai_common.player._LEGACY_PLAYER_FILE", tmp_path / "player.json"),
        ):
            p = PlayerProfile(display_name="SaveTest", sovereignty=55)
            p.save()

            loaded = PlayerProfile.load(p.player_id)
            assert loaded is not None
            assert loaded.display_name == "SaveTest"
            assert loaded.sovereignty == 55

    def test_load_returns_none_when_missing(self, tmp_path):
        with (
            patch("kourai_common.player.PROFILES_DIR", tmp_path / "profiles"),
            patch("kourai_common.player.ACTIVE_PROFILE_FILE", tmp_path / "active.txt"),
            patch(
                "kourai_common.player._LEGACY_PLAYER_FILE",
                tmp_path / "nonexistent.json",
            ),
        ):
            assert PlayerProfile.load() is None

    def test_load_or_default(self, tmp_path):
        with (
            patch("kourai_common.player.PROFILES_DIR", tmp_path / "profiles"),
            patch("kourai_common.player.ACTIVE_PROFILE_FILE", tmp_path / "active.txt"),
            patch(
                "kourai_common.player._LEGACY_PLAYER_FILE",
                tmp_path / "nonexistent.json",
            ),
        ):
            p = PlayerProfile.load_or_default()
            assert p.display_name == ""


# ── Memory CRUD Tests ──────────────────────────────────────────────────


class TestPlayerMemory:
    def test_ensure_player_tables_handles_new_connection_after_prior_init(self, tmp_path):
        import kourai_common.player as player_mod

        first = sqlite3.connect(str(tmp_path / "first.db"), check_same_thread=False)
        second = sqlite3.connect(str(tmp_path / "second.db"), check_same_thread=False)

        try:
            player_mod._tables_initialized = False
            _ensure_player_tables(first)

            # Simulate later work on a different connection after prior init.
            player_mod._tables_initialized = True  # ty: ignore[invalid-assignment]
            _ensure_player_tables(second)

            second.execute("DELETE FROM player_memories WHERE player_id = ?", ("test123",))
            second.execute("DELETE FROM agent_affinity WHERE player_id = ?", ("test123",))
        finally:
            first.close()
            second.close()

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

    def test_add_player_memory_default_project_id_is_none(self, profile):
        """Memories without an explicit project_id round-trip as None."""
        add_player_memory(profile.player_id, "global preference", "fact")
        memories = get_player_memories(profile.player_id)
        assert len(memories) == 1
        assert memories[0]["project_id"] is None

    def test_add_player_memory_persists_project_id(self, profile):
        """Project-scoped memories carry project_id through to retrieval."""
        add_player_memory(
            profile.player_id,
            "coverage_target: 80%",
            "fact",
            project_id="abc123def4567890",
        )
        memories = get_player_memories(profile.player_id)
        assert len(memories) == 1
        assert memories[0]["project_id"] == "abc123def4567890"

    def test_get_memories_no_project_filter_returns_all_scopes(self, profile):
        """Without a project_id arg, all scopes are returned (backwards compatible)."""
        add_player_memory(profile.player_id, "in proj A", "fact", project_id="proj-A")
        add_player_memory(profile.player_id, "in proj B", "fact", project_id="proj-B")
        add_player_memory(profile.player_id, "global fact", "fact", project_id=None)

        all_mems = get_player_memories(profile.player_id)
        assert len(all_mems) == 3
        contents = {m["content"] for m in all_mems}
        assert contents == {"in proj A", "in proj B", "global fact"}

    def test_get_memories_with_project_id_includes_global(self, profile):
        """Project-scoped query returns matching project AND global facts."""
        add_player_memory(profile.player_id, "in proj A", "fact", project_id="proj-A")
        add_player_memory(profile.player_id, "global fact", "fact", project_id=None)

        scoped = get_player_memories(profile.player_id, project_id="proj-A")
        contents = {m["content"] for m in scoped}
        assert contents == {"in proj A", "global fact"}

    def test_get_memories_with_project_id_excludes_other_projects(self, profile):
        """Project-scoped query does NOT leak facts from other projects."""
        add_player_memory(profile.player_id, "in proj A", "fact", project_id="proj-A")
        add_player_memory(profile.player_id, "in proj B", "fact", project_id="proj-B")

        scoped = get_player_memories(profile.player_id, project_id="proj-A")
        contents = {m["content"] for m in scoped}
        assert contents == {"in proj A"}

    def test_get_memories_prefers_project_match_at_equal_importance(self, profile):
        """At tied retrieval score, project-tagged rows beat global rows."""
        # Add global first (older last_accessed) at importance 0.5
        add_player_memory(profile.player_id, "global fact", "fact", importance=0.5, project_id=None)
        # Add project-tagged second at the SAME importance — global's
        # last_accessed is older, so without the project-boost the global
        # row would tie or rank lower; with the boost project-tagged wins.
        add_player_memory(
            profile.player_id,
            "project fact",
            "fact",
            importance=0.5,
            project_id="proj-A",
        )

        scoped = get_player_memories(profile.player_id, project_id="proj-A")
        assert scoped[0]["content"] == "project fact"
        assert scoped[1]["content"] == "global fact"


# ── M17 Phase 1: end-to-end property test ─────────────────────────────


class TestM17Phase1Property:
    """Definition of done for M17 Phase 1.

    A HOTL answer in project A persists, is recalled in the same agent on the
    next run for project A, AND is NOT recalled when the player switches to
    project B. End-to-end: derive_project_id → synthesise_fact_from_pause →
    build_fact_context with project filter.
    """

    def test_hotl_answer_recalled_in_same_project_not_in_different_project(self, profile):
        from kourai_common.facts import build_fact_context
        from kourai_common.hooks_interaction import synthesise_fact_from_pause

        # Two distinct project ids — in production these come from
        # `derive_project_id(project_root)` (see PR #81 / sibling branch);
        # the integration is identity-agnostic, so opaque strings suffice
        # to demonstrate cross-project isolation.
        proj_a_id = "abc123def4567890"
        proj_b_id = "fedcba9876543210"

        # Metis pauses on project A; player answers "80%"
        ok = synthesise_fact_from_pause(
            player_id=profile.player_id,
            project_id=proj_a_id,
            preference_kind="coverage_target",
            player_response="80%",
            source_agent="metis",
        )
        assert ok is True

        # On project A — Metis recalls the answer
        context_a = build_fact_context(profile.player_id, agent_name="metis", project_id=proj_a_id)
        assert "coverage_target: 80%" in context_a

        # On project B — Metis does NOT recall (no leakage across projects)
        context_b = build_fact_context(profile.player_id, agent_name="metis", project_id=proj_b_id)
        assert "coverage_target: 80%" not in context_b

    def test_global_facts_visible_from_any_project(self, profile):
        """Facts stored without a project_id are global and visible everywhere."""
        from kourai_common.facts import build_fact_context
        from kourai_common.hooks_interaction import synthesise_fact_from_pause

        proj_id = "abc123def4567890"

        synthesise_fact_from_pause(
            player_id=profile.player_id,
            project_id=None,  # global
            preference_kind="python_version",
            player_response="3.12",
            source_agent="metis",
        )

        context = build_fact_context(profile.player_id, agent_name="metis", project_id=proj_id)
        assert "python_version: 3.12" in context


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
        monkeypatch.setattr("kourai_common.player.PROFILES_DIR", tmp_path / "profiles")
        monkeypatch.setattr("kourai_common.player.ACTIVE_PROFILE_FILE", tmp_path / "active.txt")
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
        monkeypatch.setattr("kourai_common.player.PROFILES_DIR", tmp_path / "profiles")
        monkeypatch.setattr("kourai_common.player.ACTIVE_PROFILE_FILE", tmp_path / "active.txt")
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
                "kallos": {
                    "affinity_score": 0.3,
                    "interaction_count": 5,
                    "romance_stage": "none",
                }
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
        monkeypatch.setattr("kourai_common.player.PROFILES_DIR", tmp_path / "profiles")
        monkeypatch.setattr("kourai_common.player.ACTIVE_PROFILE_FILE", tmp_path / "active.txt")
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


# ── Enriched System Blocks Tests ────────────────────────────────────────


class TestEnrichedSystemBlocks:
    """Verify get_enriched_system_blocks returns cache-marked text blocks
    split into (truly-static, player-dynamic) so the static block always
    cache-hits while the dynamic block resets only on player state shifts.

    research(2026-05): post-#177 follow-on. Pre-fix shape concatenated
    SYSTEM_PROMPT with dynamic player context as a single string, so every
    player-state shift invalidated the static portion's cache. Source:
    platform.claude.com/docs/en/build-with-claude/prompt-caching.
    """

    def test_returns_single_static_block_when_no_profile(self, monkeypatch):
        import kourai_common.player as player_mod
        from kourai_common.player import get_enriched_system_blocks

        player_mod._profile_cache = None  # ty: ignore[unresolved-attribute]
        player_mod._profile_cache_ts = 0.0  # ty: ignore[unresolved-attribute]
        monkeypatch.setattr(PlayerProfile, "load", staticmethod(lambda: None))

        # Static block opts into 1h TTL — see cached_text_blocks docstring.
        result = get_enriched_system_blocks("base prompt", "metis")
        assert result == [
            {
                "type": "text",
                "text": "base prompt",
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            }
        ]

    def test_splits_static_and_dynamic_blocks_when_profile_exists(self, profile, monkeypatch):
        import kourai_common.player as player_mod
        from kourai_common.player import get_enriched_system_blocks

        player_mod._profile_cache = None  # ty: ignore[unresolved-attribute]
        player_mod._profile_cache_ts = 0.0  # ty: ignore[unresolved-attribute]
        monkeypatch.setattr(PlayerProfile, "load", staticmethod(lambda: profile))

        result = get_enriched_system_blocks("base prompt", "metis")
        assert len(result) == 2
        # Block 0 is the truly-static prompt — bytewise just the base, 1h TTL.
        assert result[0]["text"] == "base prompt"
        assert result[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
        # Block 1 is the player-dynamic context — has identity/alignment data,
        # 5min default TTL because player state churns sub-hourly anyway.
        assert "PLAYER IDENTITY" in result[1]["text"]
        assert "AJ" in result[1]["text"]
        assert result[1]["cache_control"] == {"type": "ephemeral"}
        # Critically: the base prompt is NOT also embedded in block 1.
        assert "base prompt" not in result[1]["text"]

    def test_static_suffix_baked_into_static_block(self, profile, monkeypatch):
        """Call sites with mode-specific extras (dokimasia's "Fix failing
        tests..." or metis's "DISCUSSION MODE...") pass them via static_suffix
        so they end up in Block 0 — they're truly-static for that call site
        and shouldn't invalidate the dynamic block when player state shifts."""
        import kourai_common.player as player_mod
        from kourai_common.player import get_enriched_system_blocks

        player_mod._profile_cache = None  # ty: ignore[unresolved-attribute]
        player_mod._profile_cache_ts = 0.0  # ty: ignore[unresolved-attribute]
        monkeypatch.setattr(PlayerProfile, "load", staticmethod(lambda: profile))

        result = get_enriched_system_blocks(
            "base prompt", "metis", static_suffix="DISCUSSION MODE: brief"
        )
        assert len(result) == 2
        # Both base + suffix end up in the static block.
        assert "base prompt" in result[0]["text"]
        assert "DISCUSSION MODE: brief" in result[0]["text"]
        # NOT in the dynamic block — it must stay free of static text.
        assert "DISCUSSION MODE" not in result[1]["text"]

    def test_static_block_byte_identical_across_player_state_shifts(self, profile, monkeypatch):
        """The whole point: the static block must remain bytewise identical
        even when player state mutates (new memory added, affinity changed),
        so the prefix-cache machinery cache-hits the static block on every
        call regardless of dynamic-block churn."""
        import kourai_common.player as player_mod
        from kourai_common.player import add_player_memory, get_enriched_system_blocks

        player_mod._profile_cache = None  # ty: ignore[unresolved-attribute]
        player_mod._profile_cache_ts = 0.0  # ty: ignore[unresolved-attribute]
        monkeypatch.setattr(PlayerProfile, "load", staticmethod(lambda: profile))

        first = get_enriched_system_blocks("base prompt", "metis")

        # Mutate player state; force profile-cache reload.
        add_player_memory(profile.player_id, "new memory entry", "achievement", agent_name="metis")
        player_mod._profile_cache = None  # ty: ignore[unresolved-attribute]
        player_mod._profile_cache_ts = 0.0  # ty: ignore[unresolved-attribute]

        second = get_enriched_system_blocks("base prompt", "metis")

        # Block 0 (static) — bytewise identical.
        assert first[0]["text"] == second[0]["text"]
        # Block 1 (dynamic) — must reflect the new memory; therefore differs.
        assert first[1]["text"] != second[1]["text"]
        assert "new memory entry" in second[1]["text"]
