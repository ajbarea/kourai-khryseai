"""Tests for alignment scoring, pattern detection, and gossip engine."""

import sqlite3
from unittest.mock import AsyncMock, patch

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
    monkeypatch.setattr(player_mod, "PLAYER_FILE", tmp_path / "player.json")

    player_mod._profile_cache = None
    player_mod._profile_cache_ts = 0.0

    yield conn
    conn.close()


# ── Alignment Scoring ──────────────────────────────────────────────────


class TestAlignmentScoring:
    def test_sovereignty_strong_pattern(self):
        from kourai_common.hooks import score_alignment

        p = PlayerProfile(display_name="AJ", sovereignty=10, devotion=10)
        sov, dev = score_alignment("This isn't good enough, redo this!", p)
        assert sov >= 3
        assert p.sovereignty > 10

    def test_devotion_strong_pattern(self):
        from kourai_common.hooks import score_alignment

        p = PlayerProfile(display_name="AJ", sovereignty=10, devotion=10)
        sov, dev = score_alignment("Great job! I believe in you!", p)
        assert dev >= 3
        assert p.devotion > 10

    def test_flirty_gives_devotion(self):
        from kourai_common.hooks import score_alignment

        p = PlayerProfile(display_name="AJ", sovereignty=0, devotion=0)
        sov, dev = score_alignment("You're so gorgeous~", p)
        assert dev >= 2  # Flirt + mild devotion
        assert p.devotion >= 2

    def test_neutral_text_no_change(self):
        from kourai_common.hooks import score_alignment

        p = PlayerProfile(display_name="AJ", sovereignty=50, devotion=50)
        sov, dev = score_alignment("Run the linter on src/main.py", p)
        assert sov == 0
        assert dev == 0
        assert p.sovereignty == 50
        assert p.devotion == 50

    def test_empty_text_no_change(self):
        from kourai_common.hooks import score_alignment

        p = PlayerProfile(display_name="AJ", sovereignty=10, devotion=10)
        sov, dev = score_alignment("", p)
        assert sov == 0 and dev == 0

    def test_mixed_sovereignty_and_devotion(self):
        from kourai_common.hooks import score_alignment

        p = PlayerProfile(display_name="AJ", sovereignty=0, devotion=0)
        sov, dev = score_alignment("Fix this now, but thanks for trying", p)
        assert sov > 0  # "fix this"
        assert dev > 0  # "thanks"

    def test_gossip_context_amplifies(self):
        from kourai_common.hooks import score_alignment

        p1 = PlayerProfile(display_name="A", sovereignty=0, devotion=0)
        sov1, _ = score_alignment("Do it again, not acceptable!", p1, context="task")

        p2 = PlayerProfile(display_name="B", sovereignty=0, devotion=0)
        sov2, _ = score_alignment("Do it again, not acceptable!", p2, context="gossip")

        assert sov2 > sov1  # Gossip amplifies by 1.5x

    def test_sovereignty_clamped_at_100(self):
        from kourai_common.hooks import score_alignment

        p = PlayerProfile(display_name="AJ", sovereignty=99, devotion=0)
        score_alignment("This isn't good enough! Not acceptable!", p)
        assert p.sovereignty == 100

    def test_devotion_clamped_at_100(self):
        from kourai_common.hooks import score_alignment

        p = PlayerProfile(display_name="AJ", sovereignty=0, devotion=99)
        score_alignment("Great job! You're the best! ❤", p)
        assert p.devotion == 100


# ── Gossip Alignment Scoring ───────────────────────────────────────────


class TestGossipScoring:
    def test_scold_in_gossip(self):
        from kourai_common.hooks import score_gossip_response

        p = PlayerProfile(display_name="AJ", sovereignty=0, devotion=0)
        sov, dev, affinity = score_gossip_response("Get back to work!", p, ["kallos", "metis"])
        assert sov > 0
        # Kallos (devotion-preferring) hurt, authority-agents neutral/positive
        assert affinity["kallos"] < affinity.get("metis", 0.01) or affinity["kallos"] <= 0.01

    def test_flirt_in_gossip(self):
        from kourai_common.hooks import score_gossip_response

        p = PlayerProfile(display_name="AJ", sovereignty=0, devotion=0)
        _sov, dev, affinity = score_gossip_response(
            "You're both so gorgeous~", p, ["kallos", "metis"]
        )
        assert dev > 0
        # Both agents should get positive affinity
        assert all(v > 0 for v in affinity.values())

    def test_warm_response_affinity(self):
        from kourai_common.hooks import score_gossip_response

        p = PlayerProfile(display_name="AJ", sovereignty=0, devotion=0)
        _sov, _dev, affinity = score_gossip_response(
            "Sounds good, great work!", p, ["dokimasia", "mneme"]
        )
        assert all(v > 0 for v in affinity.values())

    def test_returns_per_agent_deltas(self):
        from kourai_common.hooks import score_gossip_response

        p = PlayerProfile(display_name="AJ")
        _, _, affinity = score_gossip_response("Hey there~", p, ["techne", "kallos", "metis"])
        assert len(affinity) == 3
        assert set(affinity.keys()) == {"techne", "kallos", "metis"}


# ── Pattern Detection ──────────────────────────────────────────────────


class TestPatternDetection:
    def test_get_time_bucket(self):
        from kourai_common.hooks import get_time_bucket

        assert get_time_bucket(2) == "late_night"
        assert get_time_bucket(7) == "early_morning"
        assert get_time_bucket(10) == "morning"
        assert get_time_bucket(14) == "afternoon"
        assert get_time_bucket(19) == "evening"
        assert get_time_bucket(23) == "night"

    def test_record_session_pattern(self):
        from kourai_common.hooks import record_session_pattern

        p = PlayerProfile(display_name="AJ")
        bucket = record_session_pattern(p.player_id, hour=23)
        assert bucket == "night"

        # Check memory was created
        mems = get_player_memories(p.player_id, category="pattern")
        assert any("session_time:night" in m["content"] for m in mems)

    def test_record_session_pattern_dedup(self):
        from kourai_common.hooks import record_session_pattern

        p = PlayerProfile(display_name="AJ")
        bucket1 = record_session_pattern(p.player_id, hour=23)
        bucket2 = record_session_pattern(p.player_id, hour=23)
        assert bucket1 == "night"
        assert bucket2 is None  # Deduped

    def test_detect_time_pattern_histogram(self):
        from kourai_common.hooks import detect_time_pattern

        p = PlayerProfile(display_name="AJ")
        # We can't easily record multiple days, but we can test the histogram reader
        # by manually inserting pattern memories
        from kourai_common.player import add_player_memory

        for _ in range(5):
            add_player_memory(
                p.player_id,
                "session_time:late_night",
                category="pattern",
                importance=0.3,
                source=f"session_time:late_night:2026-03-{10 + _:02d}",
            )

        hist = detect_time_pattern(p.player_id)
        assert hist.get("late_night", 0) == 5

    def test_session_greeting_hint(self):
        from kourai_common.hooks import get_session_greeting_hint
        from kourai_common.player import add_player_memory

        p = PlayerProfile(display_name="AJ")
        # Create enough late_night patterns to trigger a hint
        for i in range(5):
            add_player_memory(
                p.player_id,
                "session_time:late_night",
                category="pattern",
                importance=0.3,
                source=f"session_time:late_night:2026-03-{i + 1:02d}",
            )

        hint = get_session_greeting_hint(p.player_id, hour=2)
        assert hint is not None
        assert "night owl" in hint.lower()

    def test_session_greeting_no_data(self):
        from kourai_common.hooks import get_session_greeting_hint

        p = PlayerProfile(display_name="AJ")
        hint = get_session_greeting_hint(p.player_id)
        assert hint is None

    def test_detect_work_patterns(self):
        from kourai_common.hooks import detect_work_patterns

        p = PlayerProfile(display_name="AJ")
        detected = detect_work_patterns(p.player_id, "Write the tests first before coding")
        assert "tests_first" in detected

        mems = get_player_memories(p.player_id, category="pattern")
        assert any("work_habit:tests_first" in m["content"] for m in mems)

    def test_detect_work_patterns_dedup(self):
        from kourai_common.hooks import detect_work_patterns

        p = PlayerProfile(display_name="AJ")
        detect_work_patterns(p.player_id, "refactor this module")
        detect_work_patterns(p.player_id, "refactor that function too")

        mems = get_player_memories(p.player_id, category="pattern")
        refactor_count = sum(1 for m in mems if "work_habit:refactor_lover" in m["content"])
        assert refactor_count == 1  # Deduped

    def test_work_pattern_summary(self):
        from kourai_common.hooks import detect_work_patterns, get_work_pattern_summary

        p = PlayerProfile(display_name="AJ")
        detect_work_patterns(p.player_id, "Write tests before implementation")
        detect_work_patterns(p.player_id, "Let's refactor this")

        summary = get_work_pattern_summary(p.player_id)
        assert summary is not None
        assert "tests" in summary.lower()
        assert "refactor" in summary.lower()

    def test_work_pattern_summary_empty(self):
        from kourai_common.hooks import get_work_pattern_summary

        p = PlayerProfile(display_name="AJ")
        assert get_work_pattern_summary(p.player_id) is None


# ── Unified Post-Task Hook ─────────────────────────────────────────────


class TestRunPostTaskHooks:
    def test_runs_all_hooks(self, tmp_path, monkeypatch):
        from kourai_common.hooks import run_post_task_hooks

        p = PlayerProfile(display_name="AJ", sovereignty=0, devotion=0)
        monkeypatch.setattr("kourai_common.player.PLAYER_DIR", tmp_path)
        monkeypatch.setattr("kourai_common.player.PLAYER_FILE", tmp_path / "player.json")
        p.save()

        run_post_task_hooks(
            p.player_id,
            "techne",
            "Great job! I prefer dark mode for everything in my editor",
            "All 42 tests passed!",
            success=True,
        )

        # Affinity updated
        aff = get_affinity(p.player_id, "techne")
        assert aff["affinity_score"] > 0

        # Memories extracted
        mems = get_player_memories(p.player_id)
        assert any(m["category"] == "preference" for m in mems)
        assert any(m["category"] == "achievement" for m in mems)

        # Alignment changed (profile saved to disk)
        reloaded = PlayerProfile.load()
        assert reloaded.devotion > 0  # "Great job" → devotion

    def test_noop_without_player_id(self):
        from kourai_common.hooks import run_post_task_hooks

        run_post_task_hooks("", "metis", "hello", "world")  # Should not raise


# ── Gossip Engine ──────────────────────────────────────────────────────


class TestGossipPairSelection:
    def test_select_gossip_pair_excludes_busy(self):
        from kourai_common.gossip import select_gossip_pair

        pair = select_gossip_pair("techne")
        assert pair is not None
        assert "techne" not in pair

    def test_select_gossip_pair_all_agents(self):
        from kourai_common.gossip import select_gossip_pair

        pair = select_gossip_pair("techne", all_agents=["techne", "metis", "kallos"])
        assert pair is not None
        a, b = pair
        assert a != "techne" and b != "techne"
        assert {a, b} == {"metis", "kallos"}

    def test_select_gossip_pair_insufficient(self):
        from kourai_common.gossip import select_gossip_pair

        pair = select_gossip_pair("techne", all_agents=["techne", "metis"])
        assert pair is None  # Only 1 idle agent

    def test_pair_chemistry_known(self):
        from kourai_common.gossip import get_pair_chemistry

        chem = get_pair_chemistry("metis", "kallos")
        assert "Strategist" in chem or "aesthete" in chem.lower() or len(chem) > 10

    def test_pair_chemistry_reversed(self):
        from kourai_common.gossip import get_pair_chemistry

        # Known pairs should return the same chemistry regardless of order
        chem1 = get_pair_chemistry("techne", "kallos")
        chem2 = get_pair_chemistry("kallos", "techne")
        assert chem1 == chem2  # Normalized lookup

    def test_pair_chemistry_unknown(self):
        from kourai_common.gossip import get_pair_chemistry

        chem = get_pair_chemistry("hephaestus", "kallos")
        assert "chat" in chem.lower() or len(chem) > 5


class TestGossipSession:
    def test_start_session(self):
        from kourai_common.gossip import start_gossip_session

        session = start_gossip_session("metis", "kallos")
        assert session.agent_a == "metis"
        assert session.agent_b == "kallos"
        assert session.round_count == 0
        assert not session.is_complete

    def test_start_session_with_profile(self):
        from kourai_common.gossip import start_gossip_session

        p = PlayerProfile(display_name="AJ")
        session = start_gossip_session("metis", "kallos", profile=p)
        assert session.topic is not None

    def test_generate_response_options(self):
        from kourai_common.gossip import (
            GossipMessage,
            GossipSession,
            GossipTopic,
            ResponseTone,
            generate_response_options,
        )

        session = GossipSession(
            agent_a="metis",
            agent_b="kallos",
            topic=GossipTopic.PLAYER_HABITS,
            messages=[GossipMessage(agent_name="metis", text="Test message")],
        )
        options = generate_response_options(session)
        tones = {o.tone for o in options}
        assert ResponseTone.IGNORE in tones
        assert ResponseTone.FLIRT in tones
        assert ResponseTone.SCOLD in tones
        assert ResponseTone.JOIN in tones

    def test_alignment_gated_options(self):
        from kourai_common.gossip import (
            GossipSession,
            GossipTopic,
            generate_response_options,
        )

        session = GossipSession(
            agent_a="metis",
            agent_b="kallos",
            topic=GossipTopic.PLAYER_HABITS,
        )

        # Low alignment — no special options
        p_low = PlayerProfile(display_name="AJ", sovereignty=10, devotion=10)
        opts_low = generate_response_options(session, profile=p_low)

        # High sovereignty — gets Command option
        p_sov = PlayerProfile(display_name="AJ", sovereignty=70, devotion=10)
        opts_sov = generate_response_options(session, profile=p_sov)

        assert len(opts_sov) > len(opts_low)  # Sovereignty unlocks Command

    def test_commander_option(self):
        from kourai_common.gossip import (
            GossipSession,
            GossipTopic,
            generate_response_options,
        )

        session = GossipSession(
            agent_a="metis",
            agent_b="kallos",
            topic=GossipTopic.PLAYER_HABITS,
        )
        p = PlayerProfile(display_name="AJ", sovereignty=85, devotion=85)
        opts = generate_response_options(session, profile=p)
        emojis = [o.emoji for o in opts]
        assert "👑" in emojis  # Commander rally option


class TestGossipRound:
    @pytest.mark.asyncio
    async def test_generate_gossip_round(self):
        from kourai_common.gossip import start_gossip_session

        session = start_gossip_session("metis", "kallos")

        with patch("kourai_common.llm.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "*giggles* Did you see what they did yesterday?"

            messages = await session_round(session)
            assert len(messages) == 2
            assert messages[0].agent_name == "metis"
            assert messages[1].agent_name == "kallos"
            assert session.round_count == 1

    @pytest.mark.asyncio
    async def test_gossip_completes_after_max_rounds(self):
        from kourai_common.gossip import generate_gossip_round, start_gossip_session

        session = start_gossip_session("metis", "kallos", max_rounds=2)

        with patch("kourai_common.llm.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "Test gossip line."

            await generate_gossip_round(session)
            await generate_gossip_round(session)
            assert session.is_complete

            # Additional rounds produce nothing
            msgs = await generate_gossip_round(session)
            assert msgs == []

    @pytest.mark.asyncio
    async def test_gossip_handles_llm_failure(self):
        from kourai_common.gossip import generate_gossip_round, start_gossip_session

        session = start_gossip_session("metis", "kallos")

        with patch("kourai_common.llm.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = Exception("LLM down")
            messages = await generate_gossip_round(session)
            assert len(messages) == 2
            # Fallback messages should contain agent names
            assert "Metis" in messages[0].text
            assert "Kallos" in messages[1].text


class TestGossipPlayerResponse:
    @pytest.mark.asyncio
    async def test_process_player_flirt(self):
        from kourai_common.gossip import (
            GossipResponseOption,
            GossipSession,
            GossipTopic,
            ResponseTone,
            process_player_response,
        )

        session = GossipSession(
            agent_a="metis",
            agent_b="kallos",
            topic=GossipTopic.PLAYER_HABITS,
        )

        opt = GossipResponseOption(
            tone=ResponseTone.FLIRT,
            emoji="💬",
            label="Flirt",
            preview_text="Talking about me behind my back~?",
        )

        p = PlayerProfile(display_name="AJ", sovereignty=0, devotion=0)
        p.save()

        with patch("kourai_common.llm.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "*blushes* O-oh! We weren't—"
            reactions = await process_player_response(session, opt, profile=p)

            assert len(reactions) == 2
            assert session.player_joined is True
            # Player message should be in history
            assert any(m.is_player for m in session.messages)

    @pytest.mark.asyncio
    async def test_process_player_ignore(self):
        from kourai_common.gossip import (
            GossipResponseOption,
            GossipSession,
            GossipTopic,
            ResponseTone,
            process_player_response,
        )

        session = GossipSession(
            agent_a="metis",
            agent_b="kallos",
            topic=GossipTopic.PLAYER_HABITS,
        )
        opt = GossipResponseOption(
            tone=ResponseTone.IGNORE,
            emoji="👀",
            label="Ignore",
            preview_text="",
        )
        reactions = await process_player_response(session, opt)
        assert reactions == []

    @pytest.mark.asyncio
    async def test_process_custom_text(self):
        from kourai_common.gossip import GossipSession, GossipTopic, process_player_response

        session = GossipSession(
            agent_a="metis",
            agent_b="kallos",
            topic=GossipTopic.PLAYER_HABITS,
        )

        with patch("kourai_common.llm.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "Oh? That's interesting~"
            reactions = await process_player_response(session, "Hello ladies~")
            assert len(reactions) == 2
            assert session.player_joined

    @pytest.mark.asyncio
    async def test_player_response_extends_session(self):
        from kourai_common.gossip import (
            GossipResponseOption,
            GossipSession,
            GossipTopic,
            ResponseTone,
            process_player_response,
        )

        session = GossipSession(
            agent_a="metis",
            agent_b="kallos",
            topic=GossipTopic.PLAYER_HABITS,
            max_rounds=3,
        )
        opt = GossipResponseOption(
            tone=ResponseTone.JOIN,
            emoji="😊",
            label="Join",
            preview_text="Room for one more~?",
        )

        with patch("kourai_common.llm.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "Welcome~"
            await process_player_response(session, opt)
            assert session.max_rounds == 4  # Extended by 1

    @pytest.mark.asyncio
    async def test_complete_session_no_response(self):
        from kourai_common.gossip import GossipSession, GossipTopic, process_player_response

        session = GossipSession(
            agent_a="metis",
            agent_b="kallos",
            topic=GossipTopic.PLAYER_HABITS,
            is_complete=True,
        )
        reactions = await process_player_response(session, "Hello!")
        assert reactions == []


class TestGossipSummary:
    def test_summarize_session(self):
        from kourai_common.gossip import (
            GossipMessage,
            GossipSession,
            GossipTopic,
            summarize_gossip_session,
        )

        session = GossipSession(
            agent_a="metis",
            agent_b="kallos",
            topic=GossipTopic.PLAYER_ROAST,
            round_count=2,
            messages=[
                GossipMessage(agent_name="metis", text="Did you see~"),
                GossipMessage(agent_name="kallos", text="Oh yes~"),
                GossipMessage(agent_name="player", text="Hey!", is_player=True),
            ],
            player_joined=True,
            memory_ids_shared=["abc123"],
        )

        summary = summarize_gossip_session(session)
        assert summary["agents"] == ["metis", "kallos"]
        assert summary["topic"] == "player_roast"
        assert summary["player_joined"] is True
        assert summary["memories_shared"] == 1
        assert len(summary["dialogue"]) == 3


class TestGossipTopicSelection:
    def test_topic_with_profile(self):
        from kourai_common.gossip import select_gossip_topic

        p = PlayerProfile(display_name="AJ")
        topic = select_gossip_topic(p, "metis", "kallos")
        assert topic is not None

    def test_topic_without_profile_favors_banter(self):
        from kourai_common.gossip import GossipTopic, select_gossip_topic

        # Run many times to check distribution tendency
        topics = [select_gossip_topic(None, "metis", "kallos") for _ in range(100)]
        banter_count = sum(1 for t in topics if t == GossipTopic.AGENT_BANTER)
        # Should be heavily weighted toward banter without a profile
        assert banter_count > 30


# Helper to import and call generate_gossip_round
async def session_round(session):
    from kourai_common.gossip import generate_gossip_round

    return await generate_gossip_round(session)
