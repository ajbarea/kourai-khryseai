"""Regression guard for the VN companion-spirits palette.

VN's `_puck_color` / `_cupid_color` were hardcoded as ``#7FBC8C`` and
``#E8728C`` (plus alpha-suffixed variants) at 15+ sites across
``screens_relationships.rpy`` and ``screens_companion_spirits.rpy``.
PR pulled them into a single named-constants block in ``script_data.rpy``
(``VN_PUCK_ACCENT`` / ``VN_CUPID_ACCENT`` / ``VN_CUPID_ACCENT_BG`` /
``VN_CUPID_ACCENT_BG_STRONG`` / ``VN_CUPID_ACCENT_HOVER``).

These tests don't import Ren'Py — they enforce the centralization at
text-grep level: the only file allowed to mention the hex literals is
``script_data.rpy`` (where they're defined) and this test file (where
they're asserted).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from kourai_common.paths import PROJECT_ROOT

if TYPE_CHECKING:
    from pathlib import Path

# Locked surface-decorative tints — see script_data.rpy comment for why
# these deliberately diverge from canonical AGENT_METADATA Okabe-Ito
# values for puck/cupid.
_PUCK_HEX = "#7FBC8C"
_CUPID_HEX = "#E8728C"
_CUPID_ALPHA_VARIANTS = ("#E8728C33", "#E8728C44", "#E8728C66")

_VN_GAME_DIR = PROJECT_ROOT / "hosts" / "vn" / "kourai_vn" / "game"

# script_data.rpy owns the canonical definitions + the explainer comment;
# this test file references the literals to assert them.
_ALLOWED_FILES = frozenset({"script_data.rpy", "test_vn_companion_accent.py"})


def _scan(pattern: str) -> list[tuple[Path, int, str]]:
    """Return (path, line_no, line) for every match of ``pattern`` in VN .rpy."""
    hits: list[tuple[Path, int, str]] = []
    rx = re.compile(re.escape(pattern), re.IGNORECASE)
    for path in _VN_GAME_DIR.rglob("*.rpy"):
        if path.name in _ALLOWED_FILES:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if rx.search(line):
                hits.append((path.relative_to(PROJECT_ROOT), i, line.strip()))
    return hits


@pytest.mark.parametrize("hex_literal", [_PUCK_HEX, _CUPID_HEX, *_CUPID_ALPHA_VARIANTS])
def test_companion_accent_literal_only_in_script_data(hex_literal: str):
    """No VN .rpy outside script_data.rpy should mention these hexes literally."""
    hits = _scan(hex_literal)
    assert hits == [], (
        f"{hex_literal} leaked back into VN .rpy files; should reference the "
        f"VN_*_ACCENT* constants from script_data.rpy. Hits: {hits}"
    )


def test_script_data_defines_companion_accent_constants():
    """The constants module is the single source of truth — must exist."""
    text = (_VN_GAME_DIR / "script_data.rpy").read_text(encoding="utf-8")
    for const in (
        "VN_PUCK_ACCENT",
        "VN_CUPID_ACCENT",
        "VN_CUPID_ACCENT_BG",
        "VN_CUPID_ACCENT_BG_STRONG",
        "VN_CUPID_ACCENT_HOVER",
    ):
        assert f"{const} =" in text, f"script_data.rpy missing {const} definition"


def test_constant_values_match_locked_palette():
    """Lock the values so a future palette change goes through code review."""
    text = (_VN_GAME_DIR / "script_data.rpy").read_text(encoding="utf-8")
    # Loose-but-strict check: each constant assigns to its expected literal.
    expected = {
        "VN_PUCK_ACCENT": _PUCK_HEX,
        "VN_CUPID_ACCENT": _CUPID_HEX,
        "VN_CUPID_ACCENT_BG": "#E8728C33",
        "VN_CUPID_ACCENT_BG_STRONG": "#E8728C44",
        "VN_CUPID_ACCENT_HOVER": "#E8728C66",
    }
    for name, value in expected.items():
        # Match: NAME = "value"  with optional whitespace.
        rx = re.compile(rf'\b{re.escape(name)}\s*=\s*"{re.escape(value)}"')
        assert rx.search(text), (
            f"{name} should bind to {value!r} in script_data.rpy; check the "
            "companion-spirits palette block."
        )
