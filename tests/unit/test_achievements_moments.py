"""Tests for achievements, memory moments, and personality adaptation."""

import sqlite3
from unittest.mock import patch

import pytest

from kourai_common import player
from kourai_common.player import (
    PlayerProfile,
    _ensure_player_tables,
    add_player_memory,
    update_affinity,
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
    monkeypatch.setattr(player_mod, "PLAYER_FILE", tmp_path / "player.json")

    player_mod._profile_cache = None
    player_mod._profile_cache_ts = 0.0

    yield conn
    conn.close()


# ── Achievement System ──────────────────────────────────────────────────


class TestAchievementDefinitions:
    def test_all_achievements_registered(self):
        from kourai_common.achievements import ACHIEVEMENTS

        assert len(ACHIEVEMENTS) >= 20
        assert "first_forge" in ACHIEVEMENTS
        assert "the_commander" in ACHIEVEMENTS
        assert "first_spark" in ACHIEVEMENTS

    def test_achievement_categories(self):
        from kourai_common.achievements import ACHIEVEMENTS

        categories = {a.category for a in ACHIEVEMENTS.values()}
        assert "task" in categories
        assert "gossip" in categories
        assert "alignment" in categories
        assert "romance" in categories
        assert "social" in categories

    def test_hidden_achievements(self):
        from kourai_common.achievements import ACHIEVEMENTS

        hidden = [a for a in ACHIEVEMENTS.values() if a.hidden]
        assert len(hidden) >= 2  # thousand_hammers, heartbreaker, harem_protagonist


class TestAchievementChecking:
    def test_first_forge_on_first_interaction(self):
        from kourai_common.achievements import check_achievements

        p = PlayerProfile(display_name="AJ")
        update_affinity(p.player_id, "techne", 0.02)

        unlocked = check_achievements(p.player_id, p)
        ids = [a.id for a in unlocked]
        assert "first_forge" in ids

    def test_no_duplicate_unlock(self):
        from kourai_common.achievements import check_achievements

        p = PlayerProfile(display_name="AJ")
        update_affinity(p.player_id, "techne", 0.02)

        unlocked1 = check_achievements(p.player_id, p)
        unlocked2 = check_achievements(p.player_id, p)
        assert len(unlocked1) > 0
        # first_forge should NOT appear again
        ids2 = [a.id for a in unlocked2]
        assert "first_forge" not in ids2

    def test_alignment_achievements(self):
        from kourai_common.achievements import check_achievements

        p = PlayerProfile(display_name="AJ", sovereignty=85, devotion=85)

        unlocked = check_achievements(p.player_id, p)
        ids = [a.id for a in unlocked]
        assert "first_steps" in ids
        assert "iron_fist" in ids
        assert "heart_of_gold" in ids
        assert "the_commander" in ids

    def test_romance_achievements(self):
        from kourai_common.achievements import check_achievements

        p = PlayerProfile(display_name="AJ")
        # Set up a romance
        for _ in range(40):
            update_affinity(p.player_id, "kallos", 0.02)
        conn = player._get_player_db()
        conn.execute(
            "UPDATE agent_affinity SET romance_stage = 'bonfire' "
            "WHERE player_id = ? AND agent_name = 'kallos'",
            (p.player_id,),
        )
        conn.commit()

        unlocked = check_achievements(p.player_id, p)
        ids = [a.id for a in unlocked]
        assert "first_spark" in ids
        assert "eternal_flame" in ids
        assert "ride_or_die" in ids

    def test_full_pipeline_achievement(self):
        from kourai_common.achievements import check_achievements

        p = PlayerProfile(display_name="AJ")
        update_affinity(p.player_id, "metis", 0.01)

        ctx = {"agents_used_this_session": {"metis", "techne", "dokimasia", "kallos", "mneme"}}
        unlocked = check_achievements(p.player_id, p, context=ctx)
        ids = [a.id for a in unlocked]
        assert "full_pipeline" in ids

    def test_gossip_achievements(self):
        from kourai_common.achievements import check_achievements

        p = PlayerProfile(display_name="AJ")
        update_affinity(p.player_id, "metis", 0.01)

        ctx = {"gossip_sessions": 50, "gossip_joins": 20, "scold_count": 10}
        unlocked = check_achievements(p.player_id, p, context=ctx)
        ids = [a.id for a in unlocked]
        assert "gossip_monarch" in ids
        assert "social_butterfly" in ids
        assert "taskmaster" in ids

    def test_social_achievements(self):
        from kourai_common.achievements import check_achievements

        p = PlayerProfile(display_name="AJ")
        # Build multiple bonded relationships
        for agent in ["metis", "techne", "dokimasia", "kallos", "mneme"]:
            for _ in range(40):
                update_affinity(p.player_id, agent, 0.02)

        unlocked = check_achievements(p.player_id, p)
        ids = [a.id for a in unlocked]
        assert "bonded_pair" in ids
        assert "inner_circle" in ids
        assert "everyones_friend" in ids


class TestAchievementProgress:
    def test_progress_summary(self):
        from kourai_common.achievements import (
            ACHIEVEMENTS,
            check_achievements,
            get_achievement_progress,
        )

        p = PlayerProfile(display_name="AJ", sovereignty=85, devotion=85)
        update_affinity(p.player_id, "techne", 0.02)
        check_achievements(p.player_id, p)

        progress = get_achievement_progress(p.player_id, p)
        assert progress["total"] == len(ACHIEVEMENTS)
        assert progress["unlocked_count"] >= 3  # first_forge + alignment
        assert "alignment" in progress["by_category"]

    def test_notification_format(self):
        from kourai_common.achievements import ACHIEVEMENTS, format_achievement_notification

        ach = ACHIEVEMENTS["first_forge"]
        text = format_achievement_notification(ach)
        assert "🏆" in text
        assert "First Forge" in text


# ── Memory Moments ──────────────────────────────────────────────────────


class TestMemoryMoments:
    def test_should_trigger_low_tier(self):
        from kourai_common.memory_moments import should_trigger_moment

        p = PlayerProfile(display_name="AJ")
        # Stranger tier — very low probability
        # Run many times and check it triggers sometimes but not always
        triggered = sum(1 for _ in range(1000) if should_trigger_moment(p.player_id, "metis", p))
        assert triggered < 100  # Less than 10% for strangers (2% expected)

    def test_should_trigger_high_tier(self):
        from kourai_common.memory_moments import should_trigger_moment

        p = PlayerProfile(display_name="AJ")
        for _ in range(40):
            update_affinity(p.player_id, "metis", 0.02)

        # Bonded tier — higher probability
        triggered = sum(1 for _ in range(1000) if should_trigger_moment(p.player_id, "metis", p))
        assert triggered > 100  # More than 10% for bonded (25% expected)

    def test_romance_bonus_probability(self):
        from kourai_common.memory_moments import should_trigger_moment

        p = PlayerProfile(display_name="AJ")
        for _ in range(40):
            update_affinity(p.player_id, "metis", 0.02)
        conn = player._get_player_db()
        conn.execute(
            "UPDATE agent_affinity SET romance_stage = 'bonfire' "
            "WHERE player_id = ? AND agent_name = 'metis'",
            (p.player_id,),
        )
        conn.commit()

        # Bonded + bonfire = 0.25 + 0.20 = 0.45 probability
        triggered = sum(1 for _ in range(1000) if should_trigger_moment(p.player_id, "metis", p))
        assert triggered > 300  # ~45% expected

    def test_select_memory_with_memories(self):
        from kourai_common.memory_moments import select_memory_for_moment

        p = PlayerProfile(display_name="AJ")
        add_player_memory(
            p.player_id,
            "Worked late debugging async issue",
            category="moment",
            agent_name="techne",
            importance=0.7,
        )

        moment = select_memory_for_moment(p.player_id, "techne", p)
        assert moment is not None
        assert moment.memory_content == "Worked late debugging async issue"
        assert moment.prompt_hint != ""
        assert moment.agent_name == "techne"

    def test_select_memory_no_memories(self):
        from kourai_common.memory_moments import select_memory_for_moment

        p = PlayerProfile(display_name="AJ")
        moment = select_memory_for_moment(p.player_id, "techne", p)
        assert moment is None

    def test_generate_moment_context(self):
        from kourai_common.memory_moments import generate_moment_context

        p = PlayerProfile(display_name="AJ")
        for _ in range(40):
            update_affinity(p.player_id, "metis", 0.02)
        add_player_memory(
            p.player_id,
            "Refactored the auth system together",
            category="moment",
            agent_name="metis",
            importance=0.8,
        )

        # Force trigger by patching random
        with patch("kourai_common.memory_moments.random.random", return_value=0.01):
            ctx = generate_moment_context(p.player_id, "metis", p)

        assert ctx is not None
        assert "MEMORY MOMENT" in ctx
        assert "auth system" in ctx.lower() or "refactored" in ctx.lower()

    def test_moment_type_romance(self):
        from kourai_common.memory_moments import _select_moment_type

        # At flame/bonfire, "intimate" type should be possible
        results = set()
        for _ in range(100):
            results.add(_select_moment_type(3, "flame", "moment"))
        assert "intimate" in results

    def test_moment_type_achievement_always_growth(self):
        from kourai_common.memory_moments import _select_moment_type

        for _ in range(20):
            assert _select_moment_type(2, "none", "achievement") == "growth"


# ── Personality Adaptation ──────────────────────────────────────────────


class TestPersonalityAdaptation:
    def test_stranger_returns_empty(self):
        from kourai_common.personality_adaptation import get_personality_adaptation

        p = PlayerProfile(display_name="AJ")
        result = get_personality_adaptation(p.player_id, "metis", p)
        assert result == ""

    def test_acquaintance_tier(self):
        from kourai_common.personality_adaptation import get_personality_adaptation

        p = PlayerProfile(display_name="AJ")
        for _ in range(10):
            update_affinity(p.player_id, "metis", 0.02)

        result = get_personality_adaptation(p.player_id, "metis", p)
        assert "PERSONALITY ADAPTATION" in result
        assert "dry wit" in result.lower()

    def test_bonded_tier(self):
        from kourai_common.personality_adaptation import get_personality_adaptation

        p = PlayerProfile(display_name="AJ")
        for _ in range(40):
            update_affinity(p.player_id, "techne", 0.02)

        result = get_personality_adaptation(p.player_id, "techne", p)
        assert "Tier 3" in result
        assert "genuine" in result.lower()

    def test_sovereignty_modifier(self):
        from kourai_common.personality_adaptation import get_personality_adaptation

        p = PlayerProfile(display_name="AJ", sovereignty=70, devotion=0)
        for _ in range(10):
            update_affinity(p.player_id, "dokimasia", 0.02)

        result = get_personality_adaptation(p.player_id, "dokimasia", p)
        assert "authority" in result.lower() or "discipline" in result.lower()

    def test_devotion_modifier(self):
        from kourai_common.personality_adaptation import get_personality_adaptation

        p = PlayerProfile(display_name="AJ", sovereignty=0, devotion=70)
        for _ in range(10):
            update_affinity(p.player_id, "kallos", 0.02)

        result = get_personality_adaptation(p.player_id, "kallos", p)
        assert "bloom" in result.lower() or "expressive" in result.lower()

    def test_commander_modifier(self):
        from kourai_common.personality_adaptation import get_personality_adaptation

        p = PlayerProfile(display_name="AJ", sovereignty=85, devotion=85)
        for _ in range(10):
            update_affinity(p.player_id, "hephaestus", 0.02)

        result = get_personality_adaptation(p.player_id, "hephaestus", p)
        assert "unguarded" in result.lower() or "loyalty" in result.lower()

    def test_all_agents_have_adaptations(self):
        from kourai_common.personality_adaptation import (
            AGENT_TIER_ADAPTATIONS,
            ALIGNMENT_PERSONALITY_MODIFIERS,
        )

        agents = ["metis", "techne", "dokimasia", "kallos", "mneme", "hephaestus"]
        for agent in agents:
            assert agent in AGENT_TIER_ADAPTATIONS
            assert len(AGENT_TIER_ADAPTATIONS[agent]) == 4  # Tiers 0-3
            assert agent in ALIGNMENT_PERSONALITY_MODIFIERS
            mods = ALIGNMENT_PERSONALITY_MODIFIERS[agent]
            assert "high_sovereignty" in mods
            assert "high_devotion" in mods
            assert "commander" in mods


# ── Integration: Enriched System Prompt ─────────────────────────────────


class TestEnrichedPromptIntegration:
    def test_enriched_prompt_includes_adaptation(self):
        from kourai_common.player import get_enriched_system_prompt

        p = PlayerProfile(display_name="AJ", sovereignty=70, devotion=0)
        p.save()
        for _ in range(15):
            update_affinity(p.player_id, "metis", 0.02)

        # Clear cache
        player._profile_cache = None
        player._profile_cache_ts = 0

        result = get_enriched_system_prompt("Base prompt here.", "metis")
        assert "Base prompt here." in result
        assert "PLAYER IDENTITY" in result
        # Personality adaptation should be present (acquaintance tier)
        assert "PERSONALITY ADAPTATION" in result

    def test_hooks_include_achievements(self, tmp_path, monkeypatch):
        from kourai_common.hooks import run_post_task_hooks

        p = PlayerProfile(display_name="AJ", sovereignty=0, devotion=0)
        monkeypatch.setattr("kourai_common.player.PLAYER_DIR", tmp_path)
        monkeypatch.setattr("kourai_common.player.PLAYER_FILE", tmp_path / "player.json")
        p.save()

        results = run_post_task_hooks(p.player_id, "techne", "hello", "done", success=True)
        assert "achievements_unlocked" in results
        # first_forge should unlock on first interaction
        assert "first_forge" in results["achievements_unlocked"]
