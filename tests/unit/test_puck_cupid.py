"""Unit tests for kourai_common.companion — Puck & Cupid logic helpers."""

from __future__ import annotations

import pytest

from kourai_common.companion import (
    minigame_affinity_gain,
    should_show_puck_nudge,
    should_show_vulnerability,
)

# ── minigame_affinity_gain ─────────────────────────────────────────────────────


def test_no_games_gives_full_gain():
    assert minigame_affinity_gain(0.10, 0) == pytest.approx(0.10)


def test_three_wins_decays_correctly():
    # 0.10 * 0.8^3 = 0.0512
    assert minigame_affinity_gain(0.10, 3) == pytest.approx(0.10 * 0.8**3)


def test_ten_wins_under_two_percent():
    # 0.10 * 0.8^10 ≈ 0.0107
    gain = minigame_affinity_gain(0.10, 10)
    assert gain < 0.02
    assert gain > 0.0


def test_never_negative_base():
    assert minigame_affinity_gain(-0.05, 0) == pytest.approx(0.0)


def test_never_negative_with_decay():
    assert minigame_affinity_gain(-0.10, 5) == pytest.approx(0.0)


def test_negative_minigames_treated_as_zero():
    assert minigame_affinity_gain(0.10, -1) == pytest.approx(0.10)


def test_five_wins_multiplier():
    # 0.8^5 = 0.32768
    assert minigame_affinity_gain(0.10, 5) == pytest.approx(0.10 * 0.8**5)


# ── should_show_vulnerability ──────────────────────────────────────────────────


def test_no_vulnerability_if_romance_off():
    assert not should_show_vulnerability(0.80, 20, 0, romance_mode=False)


def test_no_vulnerability_below_threshold():
    # 0.65 < 0.70
    assert not should_show_vulnerability(0.65, 20, 0, romance_mode=True)


def test_no_vulnerability_exactly_below_threshold():
    # 0.699 just under the wire
    assert not should_show_vulnerability(0.699, 20, 0, romance_mode=True)


def test_no_vulnerability_within_cooldown():
    # turn 20, last at 15, cooldown 8 → only 5 turns elapsed
    assert not should_show_vulnerability(0.80, 20, 15, romance_mode=True, cooldown_turns=8)


def test_vulnerability_fires_at_threshold():
    assert should_show_vulnerability(0.70, 20, 0, romance_mode=True, cooldown_turns=8)


def test_vulnerability_fires_past_cooldown():
    # turn 20, last at 10, cooldown 8 → 10 turns elapsed
    assert should_show_vulnerability(0.80, 20, 10, romance_mode=True, cooldown_turns=8)


def test_vulnerability_exactly_at_cooldown_boundary():
    # turn 8, last at 0, cooldown 8 → exactly 8 elapsed → should fire
    assert should_show_vulnerability(0.80, 8, 0, romance_mode=True, cooldown_turns=8)


def test_vulnerability_one_turn_before_cooldown():
    # turn 7, last at 0, cooldown 8 → 7 elapsed → should not fire
    assert not should_show_vulnerability(0.80, 7, 0, romance_mode=True, cooldown_turns=8)


# ── should_show_puck_nudge ─────────────────────────────────────────────────────


def test_nudge_fires_with_two_unengaged():
    assert should_show_puck_nudge(10, 0, unengaged_count=2)


def test_nudge_requires_two_unengaged():
    assert not should_show_puck_nudge(10, 0, unengaged_count=1)


def test_nudge_requires_zero_unengaged():
    assert not should_show_puck_nudge(10, 0, unengaged_count=0)


def test_nudge_not_before_min_turns():
    assert not should_show_puck_nudge(3, 0, unengaged_count=3, min_turns=5)


def test_nudge_at_min_turns():
    assert should_show_puck_nudge(5, 0, unengaged_count=3, min_turns=5, cooldown=4)


def test_nudge_respects_cooldown():
    # turn 8, last at 6, cooldown 4 → only 2 elapsed
    assert not should_show_puck_nudge(8, 6, unengaged_count=3, cooldown=4)


def test_nudge_fires_after_cooldown():
    # turn 10, last at 5, cooldown 4 → 5 elapsed
    assert should_show_puck_nudge(10, 5, unengaged_count=3, cooldown=4)


def test_nudge_exactly_at_cooldown_boundary():
    # turn 9, last at 5, cooldown 4 → exactly 4 elapsed → fires
    assert should_show_puck_nudge(9, 5, unengaged_count=2, cooldown=4)
