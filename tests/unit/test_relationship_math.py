from kourai_common.player import get_affinity_tier


def test_get_affinity_tier():
    assert get_affinity_tier(-0.5) == 0
    assert get_affinity_tier(0.0) == 0
    assert get_affinity_tier(0.14) == 0
    assert get_affinity_tier(0.15) == 1
    assert get_affinity_tier(0.39) == 1
    assert get_affinity_tier(0.40) == 2
    assert get_affinity_tier(0.69) == 2
    assert get_affinity_tier(0.70) == 3
    assert get_affinity_tier(1.0) == 3
