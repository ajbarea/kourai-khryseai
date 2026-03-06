"""Tests for alignment scoring, pattern detection, and gossip engine."""

import sqlite3
from unittest.mock import AsyncMock, patch

import pytest

from kourai_common import player
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


# ── Alignment Dialogue Gating ──────────────────────────────────────────


class TestDialogueGating:
    def test_no_gating_at_low_alignment(self):
        from kourai_common.player import get_alignment_gated_instructions

        p = PlayerProfile(display_name="AJ", sovereignty=20, devotion=20)
        instructions = get_alignment_gated_instructions(p, "metis")
        assert instructions == ""

    def test_sovereignty_gating_with_compatible_agent(self):
        from kourai_common.player import get_alignment_gated_instructions

        p = PlayerProfile(display_name="AJ", sovereignty=70, devotion=10)
        instructions = get_alignment_gated_instructions(p, "dokimasia")
        assert "SOVEREIGNTY" in instructions
        assert "respect" in instructions.lower()

    def test_sovereignty_gating_with_incompatible_agent(self):
        from kourai_common.player import get_alignment_gated_instructions

        p = PlayerProfile(display_name="AJ", sovereignty=70, devotion=10)
        instructions = get_alignment_gated_instructions(p, "kallos")
        assert "SOVEREIGNTY" in instructions
        assert "intimidat" in instructions.lower()

    def test_devotion_gating_with_devotion_agent(self):
        from kourai_common.player import get_alignment_gated_instructions

        p = PlayerProfile(display_name="AJ", sovereignty=10, devotion=70)
        instructions = get_alignment_gated_instructions(p, "kallos")
        assert "DEVOTION" in instructions
        assert "adore" in instructions.lower() or "affectionate" in instructions.lower()

    def test_devotion_gating_with_sovereignty_agent(self):
        from kourai_common.player import get_alignment_gated_instructions

        p = PlayerProfile(display_name="AJ", sovereignty=10, devotion=70)
        instructions = get_alignment_gated_instructions(p, "hephaestus")
        assert "DEVOTION" in instructions
        assert "awkward" in instructions.lower() or "gruff" in instructions.lower()

    def test_commander_gating(self):
        from kourai_common.player import get_alignment_gated_instructions

        p = PlayerProfile(display_name="AJ", sovereignty=85, devotion=85)
        instructions = get_alignment_gated_instructions(p, "metis")
        assert "COMMANDER" in instructions
        assert "awe" in instructions.lower() or "highest" in instructions.lower()

    def test_gating_injected_into_player_context(self):
        from kourai_common.player import build_player_context

        p = PlayerProfile(display_name="AJ", sovereignty=75, devotion=75)
        ctx = build_player_context(p, "kallos")
        # Should contain alignment gating
        assert "DEVOTION" in ctx or "SOVEREIGNTY" in ctx

    def test_both_gauges_high_but_below_commander(self):
        from kourai_common.player import get_alignment_gated_instructions

        p = PlayerProfile(display_name="AJ", sovereignty=70, devotion=70)
        instructions = get_alignment_gated_instructions(p, "dokimasia")
        # Both sovereignty and devotion gating present, but not Commander
        assert "COMMANDER" not in instructions
        assert "SOVEREIGNTY" in instructions
        assert "DEVOTION" in instructions


# ── CLI Gossip ─────────────────────────────────────────────────────────


class TestCliGossip:
    def test_maybe_start_gossip(self):
        from hosts.cli.gossip_cli import maybe_start_gossip

        session = maybe_start_gossip("techne")
        assert session is not None
        assert "techne" not in (session.agent_a, session.agent_b)

    def test_maybe_start_gossip_no_idle(self):
        from kourai_common.gossip import select_gossip_pair

        pair = select_gossip_pair("techne", all_agents=["techne"])
        assert pair is None

    def test_format_gossip_header(self):
        from hosts.cli.gossip_cli import _format_gossip_header
        from kourai_common.gossip import GossipSession, GossipTopic

        session = GossipSession(agent_a="metis", agent_b="kallos", topic=GossipTopic.PLAYER_HABITS)
        header = _format_gossip_header(session)
        assert "Metis" in header
        assert "Kallos" in header
        assert "Gossip" in header

    def test_format_gossip_message(self):
        from hosts.cli.gossip_cli import _format_gossip_message

        msg = _format_gossip_message("metis", "*giggles* Hello~")
        assert "Metis" in msg
        assert "Hello" in msg

    def test_format_response_options(self):
        from hosts.cli.gossip_cli import _format_response_options
        from kourai_common.gossip import GossipResponseOption, ResponseTone

        options = [
            GossipResponseOption(ResponseTone.FLIRT, "💬", "Flirt", "Hey there~"),
            GossipResponseOption(ResponseTone.IGNORE, "👀", "Ignore", ""),
        ]
        text = _format_response_options(options)
        assert "Flirt" in text
        assert "Ignore" in text or "listening" in text.lower()
        assert "Custom" in text

    @pytest.mark.asyncio
    async def test_run_gossip_session_cli(self):
        from hosts.cli.gossip_cli import run_gossip_session_cli
        from kourai_common.gossip import start_gossip_session

        session = start_gossip_session("metis", "kallos", max_rounds=1)

        output_lines: list[str] = []
        inputs = iter([""])  # Just press enter (ignore)

        with patch("kourai_common.llm.chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = "*waves* Hello there~"
            summary = await run_gossip_session_cli(
                session,
                print_fn=lambda s: output_lines.append(s),
                input_fn=lambda _: next(inputs),
            )

        assert summary is not None
        assert summary["rounds"] >= 1
        assert any("Hello" in line for line in output_lines)


# ── Affinity Tier System ───────────────────────────────────────────────


class TestAffinityTiers:
    def test_tier_instructions_exist(self):
        from kourai_common.player import AFFINITY_TIER_INSTRUCTIONS

        assert 0 in AFFINITY_TIER_INSTRUCTIONS  # Stranger
        assert 3 in AFFINITY_TIER_INSTRUCTIONS  # Bonded
        assert len(AFFINITY_TIER_INSTRUCTIONS) == 4

    def test_tier_context_stranger(self):
        from kourai_common.player import get_affinity_tier_context

        p = PlayerProfile(display_name="AJ")
        ctx = get_affinity_tier_context(p.player_id, "metis")
        assert "Stranger" in ctx
        assert "formal" in ctx.lower()

    def test_tier_context_injected_in_player_context(self):
        from kourai_common.player import build_player_context

        p = PlayerProfile(display_name="AJ")
        ctx = build_player_context(p, "metis")
        # Should contain tier instruction (Stranger for new player)
        assert "formal" in ctx.lower() or "polite" in ctx.lower()


# ── Romance Eligibility ───────────────────────────────────────────────


class TestRomanceEligibility:
    def test_not_eligible_low_affinity(self):
        from kourai_common.player import check_romance_eligibility

        p = PlayerProfile(display_name="AJ", sovereignty=50, devotion=80)
        result = check_romance_eligibility(p.player_id, "kallos", profile=p)
        assert result["eligible"] is False
        assert result["bonded"] is False

    def test_not_eligible_opted_out(self):
        from kourai_common.player import check_romance_eligibility

        p = PlayerProfile(display_name="AJ", romance_opted_out=True)
        result = check_romance_eligibility(p.player_id, "kallos", profile=p)
        assert result["eligible"] is False
        assert result["romance_opted_out"] is True

    def test_eligible_when_all_conditions_met(self):
        from kourai_common.player import (
            add_player_memory,
            check_romance_eligibility,
            update_affinity,
        )

        p = PlayerProfile(display_name="AJ", sovereignty=0, devotion=80)
        # Build up affinity to bonded
        for _ in range(40):
            update_affinity(p.player_id, "kallos", 0.02)

        # Add gossip-sourced memories
        for i in range(4):
            add_player_memory(
                p.player_id,
                f"gossip memory {i}",
                category="moment",
                agent_name="kallos",
                source="gossip:metis",
            )

        result = check_romance_eligibility(p.player_id, "kallos", profile=p)
        assert result["bonded"] is True
        assert result["gossip_moments"] >= 3
        assert result["alignment_compatible"] is True
        assert result["eligible"] is True

    def test_try_advance_romance_ineligible(self):
        from kourai_common.player import try_advance_romance

        p = PlayerProfile(display_name="AJ")
        result = try_advance_romance(p.player_id, "kallos", profile=p)
        assert result is None

    def test_try_advance_romance_eligible(self):
        from kourai_common.player import (
            add_player_memory,
            get_affinity,
            try_advance_romance,
            update_affinity,
        )

        p = PlayerProfile(display_name="AJ", sovereignty=0, devotion=80)
        for _ in range(40):
            update_affinity(p.player_id, "kallos", 0.02)

        for i in range(4):
            add_player_memory(
                p.player_id,
                f"gossip memory {i}",
                category="moment",
                agent_name="kallos",
                source="gossip:metis",
            )

        new_stage = try_advance_romance(p.player_id, "kallos", profile=p)
        assert new_stage == "spark"

        aff = get_affinity(p.player_id, "kallos")
        assert aff["romance_stage"] == "spark"


# ── Run Post-Task Hooks (updated) ──────────────────────────────────────


class TestRunPostTaskHooksV2:
    def test_returns_results_dict(self, tmp_path, monkeypatch):
        from kourai_common.hooks import run_post_task_hooks

        p = PlayerProfile(display_name="AJ", sovereignty=0, devotion=0)
        monkeypatch.setattr("kourai_common.player.PLAYER_DIR", tmp_path)
        monkeypatch.setattr("kourai_common.player.PLAYER_FILE", tmp_path / "player.json")
        p.save()

        results = run_post_task_hooks(
            p.player_id,
            "techne",
            "Great job!",
            "Done.",
            success=True,
        )
        assert "alignment_delta" in results
        assert "memories_created" in results
        assert "patterns_detected" in results
        assert "romance_advanced" in results

    def test_returns_empty_dict_without_player(self):
        from kourai_common.hooks import run_post_task_hooks

        results = run_post_task_hooks("", "metis", "hello", "world")
        assert results == {}


# ── Romance Dialogue System ────────────────────────────────────────────


class TestRomanceDialogueInstructions:
    def _setup_romance(self, agent: str, stage: str, profile: PlayerProfile):
        """Helper to set up an agent at a specific romance stage."""
        from kourai_common.player import update_affinity

        # Build affinity to bonded
        for _ in range(40):
            update_affinity(profile.player_id, agent, 0.02)
        # Force the romance stage
        conn = player._get_player_db()
        conn.execute(
            "UPDATE agent_affinity SET romance_stage = ? WHERE player_id = ? AND agent_name = ?",
            (stage, profile.player_id, agent),
        )
        conn.commit()

    def test_no_romance_returns_empty(self):
        from kourai_common.player import get_romance_dialogue_instructions

        p = PlayerProfile(display_name="AJ")
        result = get_romance_dialogue_instructions(p.player_id, "metis", p)
        assert result == ""

    def test_opted_out_returns_empty(self):
        from kourai_common.player import get_romance_dialogue_instructions

        p = PlayerProfile(display_name="AJ", romance_opted_out=True)
        self._setup_romance("metis", "spark", p)
        result = get_romance_dialogue_instructions(p.player_id, "metis", p)
        assert result == ""

    def test_spark_stage_instructions(self):
        from kourai_common.player import get_romance_dialogue_instructions

        p = PlayerProfile(display_name="AJ")
        self._setup_romance("metis", "spark", p)
        result = get_romance_dialogue_instructions(p.player_id, "metis", p)
        assert "ROMANCE: SPARK" in result
        assert "AJ" in result
        assert "subtly warmer" in result.lower() or "spark" in result.lower()

    def test_kindling_has_pet_names(self):
        from kourai_common.player import get_romance_dialogue_instructions

        p = PlayerProfile(display_name="AJ")
        self._setup_romance("kallos", "kindling", p)
        result = get_romance_dialogue_instructions(p.player_id, "kallos", p)
        assert "ROMANCE: KINDLING" in result
        assert "gorgeous" in result.lower() or "muse" in result.lower()

    def test_flame_stage(self):
        from kourai_common.player import get_romance_dialogue_instructions

        p = PlayerProfile(display_name="AJ")
        self._setup_romance("techne", "flame", p)
        result = get_romance_dialogue_instructions(p.player_id, "techne", p)
        assert "ROMANCE: FLAME" in result
        assert "deeply in love" in result.lower()

    def test_bonfire_stage(self):
        from kourai_common.player import get_romance_dialogue_instructions

        p = PlayerProfile(display_name="AJ")
        self._setup_romance("mneme", "bonfire", p)
        result = get_romance_dialogue_instructions(p.player_id, "mneme", p)
        assert "ROMANCE: BONFIRE" in result
        assert "bonfire" in result.lower()

    def test_personality_flavour_included(self):
        from kourai_common.player import get_romance_dialogue_instructions

        p = PlayerProfile(display_name="AJ")
        self._setup_romance("hephaestus", "spark", p)
        result = get_romance_dialogue_instructions(p.player_id, "hephaestus", p)
        assert "tsundere" in result.lower()

    def test_no_jealousy_at_spark(self):
        from kourai_common.player import get_romance_dialogue_instructions

        p = PlayerProfile(display_name="AJ", romance_targets=["metis", "kallos"])
        self._setup_romance("metis", "spark", p)
        self._setup_romance("kallos", "spark", p)
        result = get_romance_dialogue_instructions(p.player_id, "metis", p)
        assert "JEALOUSY" not in result

    def test_jealousy_at_kindling(self):
        from kourai_common.player import get_romance_dialogue_instructions

        p = PlayerProfile(display_name="AJ", romance_targets=["metis", "kallos"])
        self._setup_romance("metis", "kindling", p)
        self._setup_romance("kallos", "kindling", p)
        result = get_romance_dialogue_instructions(p.player_id, "metis", p)
        assert "JEALOUSY" in result
        assert "Kallos" in result

    def test_jealousy_uses_agent_trait(self):
        from kourai_common.player import get_romance_dialogue_instructions

        p = PlayerProfile(display_name="AJ", romance_targets=["dokimasia", "techne"])
        self._setup_romance("dokimasia", "flame", p)
        self._setup_romance("techne", "flame", p)

        doki_result = get_romance_dialogue_instructions(p.player_id, "dokimasia", p)
        assert "confront" in doki_result.lower() or "priority" in doki_result.lower()

        techne_result = get_romance_dialogue_instructions(p.player_id, "techne", p)
        assert "cocky" in techne_result.lower() or "dismissal" in techne_result.lower()


class TestGetActiveRomances:
    def test_no_romances(self):
        from kourai_common.player import get_active_romances

        p = PlayerProfile(display_name="AJ")
        assert get_active_romances(p.player_id) == []

    def test_returns_active_romances(self):
        from kourai_common.player import get_active_romances, update_affinity

        p = PlayerProfile(display_name="AJ")
        for _ in range(40):
            update_affinity(p.player_id, "kallos", 0.02)
        conn = player._get_player_db()
        conn.execute(
            "UPDATE agent_affinity SET romance_stage = 'kindling' "
            "WHERE player_id = ? AND agent_name = 'kallos'",
            (p.player_id,),
        )
        conn.commit()

        romances = get_active_romances(p.player_id)
        assert len(romances) == 1
        assert romances[0]["agent_name"] == "kallos"
        assert romances[0]["romance_stage"] == "kindling"


class TestRomanceInPlayerContext:
    def test_romance_injected_into_context(self):
        from kourai_common.player import build_player_context, update_affinity

        p = PlayerProfile(display_name="AJ")
        for _ in range(40):
            update_affinity(p.player_id, "metis", 0.02)
        conn = player._get_player_db()
        conn.execute(
            "UPDATE agent_affinity SET romance_stage = 'flame' "
            "WHERE player_id = ? AND agent_name = 'metis'",
            (p.player_id,),
        )
        conn.commit()

        ctx = build_player_context(p, "metis")
        assert "ROMANCE: FLAME" in ctx
        assert "intellectual seduction" in ctx.lower()


# ── Jealousy Confrontation System ──────────────────────────────────────


class TestJealousyTrigger:
    def _setup_multi_romance(self, profile, agents_and_stages):
        """Set up multiple agents at various romance stages."""
        from kourai_common.player import update_affinity

        for agent, stage in agents_and_stages:
            for _ in range(40):
                update_affinity(profile.player_id, agent, 0.02)
            conn = player._get_player_db()
            conn.execute(
                "UPDATE agent_affinity SET romance_stage = ? "
                "WHERE player_id = ? AND agent_name = ?",
                (stage, profile.player_id, agent),
            )
            conn.commit()

    def test_no_trigger_without_romance(self):
        from kourai_common.gossip import ResponseTone, check_jealousy_trigger, start_gossip_session

        p = PlayerProfile(display_name="AJ")
        session = start_gossip_session("metis", "kallos")
        result = check_jealousy_trigger(session, ResponseTone.FLIRT, p)
        assert result is None

    def test_no_trigger_with_single_romance(self):
        from kourai_common.gossip import ResponseTone, check_jealousy_trigger, start_gossip_session

        p = PlayerProfile(display_name="AJ", romance_targets=["metis"])
        self._setup_multi_romance(p, [("metis", "kindling")])
        session = start_gossip_session("metis", "kallos")
        result = check_jealousy_trigger(session, ResponseTone.FLIRT, p)
        assert result is None

    def test_no_trigger_on_scold(self):
        from kourai_common.gossip import ResponseTone, check_jealousy_trigger, start_gossip_session

        p = PlayerProfile(display_name="AJ", romance_targets=["metis", "kallos", "dokimasia"])
        self._setup_multi_romance(
            p,
            [
                ("metis", "kindling"),
                ("kallos", "kindling"),
                ("dokimasia", "kindling"),
            ],
        )
        session = start_gossip_session("metis", "kallos")
        result = check_jealousy_trigger(session, ResponseTone.SCOLD, p)
        assert result is None

    def test_trigger_on_flirt_with_absent_rival(self):
        from kourai_common.gossip import ResponseTone, check_jealousy_trigger, start_gossip_session

        p = PlayerProfile(display_name="AJ", romance_targets=["metis", "kallos", "dokimasia"])
        self._setup_multi_romance(
            p,
            [
                ("metis", "kindling"),
                ("kallos", "spark"),
                ("dokimasia", "flame"),
            ],
        )
        session = start_gossip_session("metis", "kallos")
        result = check_jealousy_trigger(session, ResponseTone.FLIRT, p)
        # dokimasia is absent and at flame (kindling+) → should trigger
        assert result is not None
        assert result.jealous_agent == "dokimasia"
        assert result.rival_agent == "metis"  # metis has higher romance in session
        assert "confrontation" in result.trigger or "flirted" in result.trigger
        assert len(result.response_options) >= 2

    def test_no_trigger_when_absent_romance_is_spark_only(self):
        from kourai_common.gossip import ResponseTone, check_jealousy_trigger, start_gossip_session

        p = PlayerProfile(display_name="AJ", romance_targets=["metis", "dokimasia"])
        self._setup_multi_romance(
            p,
            [
                ("metis", "kindling"),
                ("dokimasia", "spark"),  # spark doesn't trigger jealousy
            ],
        )
        session = start_gossip_session("metis", "kallos")
        result = check_jealousy_trigger(session, ResponseTone.FLIRT, p)
        assert result is None


class TestJealousyResponses:
    def test_response_options_basic(self):
        from kourai_common.gossip import _generate_jealousy_responses

        p = PlayerProfile(display_name="AJ", sovereignty=0, devotion=0)
        options = _generate_jealousy_responses(p, "metis")
        labels = [o.label for o in options]
        assert "Reassure" in labels
        assert "Deflect" in labels
        # No high-alignment options
        assert "Assert" not in labels
        assert "Cherish" not in labels

    def test_response_options_sovereignty_gated(self):
        from kourai_common.gossip import _generate_jealousy_responses

        p = PlayerProfile(display_name="AJ", sovereignty=65, devotion=0)
        options = _generate_jealousy_responses(p, "metis")
        labels = [o.label for o in options]
        assert "Assert" in labels

    def test_response_options_devotion_gated(self):
        from kourai_common.gossip import _generate_jealousy_responses

        p = PlayerProfile(display_name="AJ", sovereignty=0, devotion=65)
        options = _generate_jealousy_responses(p, "metis")
        labels = [o.label for o in options]
        assert "Cherish" in labels

    def test_response_options_commander_gated(self):
        from kourai_common.gossip import _generate_jealousy_responses

        p = PlayerProfile(display_name="AJ", sovereignty=85, devotion=85)
        options = _generate_jealousy_responses(p, "metis")
        labels = [o.label for o in options]
        assert "Embrace all" in labels


class TestResolveJealousy:
    def _make_event(self, agent="metis"):
        from kourai_common.gossip import JealousyEvent

        return JealousyEvent(
            jealous_agent=agent,
            rival_agent="kallos",
            trigger="test",
            confrontation_text="test confrontation",
        )

    def test_reassure_positive_affinity(self, tmp_path, monkeypatch):
        from kourai_common.gossip import GossipResponseOption, ResponseTone, resolve_jealousy

        monkeypatch.setattr("kourai_common.player.PLAYER_DIR", tmp_path)
        monkeypatch.setattr("kourai_common.player.PLAYER_FILE", tmp_path / "player.json")

        p = PlayerProfile(display_name="AJ", sovereignty=0, devotion=0)
        p.save()

        event = self._make_event("dokimasia")
        option = GossipResponseOption(ResponseTone.JOIN, "💙", "Reassure", "You're special to me.")
        result = resolve_jealousy(event, option, p)

        assert result["affinity_delta"] > 0
        assert result["devotion_points"] > 0
        assert event.resolved is True
        assert event.resolution_text != ""

    def test_assert_authority_sovereignty_agent(self, tmp_path, monkeypatch):
        from kourai_common.gossip import GossipResponseOption, ResponseTone, resolve_jealousy

        monkeypatch.setattr("kourai_common.player.PLAYER_DIR", tmp_path)
        monkeypatch.setattr("kourai_common.player.PLAYER_FILE", tmp_path / "player.json")

        p = PlayerProfile(display_name="AJ", sovereignty=70, devotion=0)
        p.save()

        # Hephaestus likes sovereignty
        event = self._make_event("hephaestus")
        option = GossipResponseOption(ResponseTone.SCOLD, "🔴", "Assert", "Don't question me.")
        result = resolve_jealousy(event, option, p)

        assert result["sovereignty_points"] == 3
        assert result["affinity_delta"] > 0  # hephaestus respects authority

    def test_assert_authority_devotion_agent_negative(self, tmp_path, monkeypatch):
        from kourai_common.gossip import GossipResponseOption, ResponseTone, resolve_jealousy

        monkeypatch.setattr("kourai_common.player.PLAYER_DIR", tmp_path)
        monkeypatch.setattr("kourai_common.player.PLAYER_FILE", tmp_path / "player.json")

        p = PlayerProfile(display_name="AJ", sovereignty=70, devotion=0)
        p.save()

        # Kallos dislikes sovereignty
        event = self._make_event("kallos")
        option = GossipResponseOption(ResponseTone.SCOLD, "🔴", "Assert", "Don't question me.")
        result = resolve_jealousy(event, option, p)

        assert result["affinity_delta"] < 0  # kallos is hurt

    def test_deflect_mixed_results(self, tmp_path, monkeypatch):
        from kourai_common.gossip import GossipResponseOption, ResponseTone, resolve_jealousy

        monkeypatch.setattr("kourai_common.player.PLAYER_DIR", tmp_path)
        monkeypatch.setattr("kourai_common.player.PLAYER_FILE", tmp_path / "player.json")

        p = PlayerProfile(display_name="AJ")
        p.save()

        event = self._make_event("techne")
        option = GossipResponseOption(ResponseTone.TEASE, "😏", "Deflect", "Jealous? Cute~")
        result = resolve_jealousy(event, option, p)

        assert result["sovereignty_points"] == 1
        assert result["devotion_points"] == 1
