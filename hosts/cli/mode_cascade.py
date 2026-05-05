"""Mode cascade — flip all seven Puck-tutorial settings in one pass.

Single source of truth used by the `/settings` panel's `[0] Session Mode`
entry and (in a follow-up PR) the Puck-led onboarding mode gate.

Cascade per `docs/architecture/puck-first-run-tutorial.md` Section 3:

| setting                   | focused | gamified |
|---------------------------|---------|----------|
| experience_mode           | focused | gamified |
| romance_enabled           | False   | False    | ← unchanged in both paths
| gossip_enabled            | False   | True     |
| romance_nudges_enabled    | False   | True     |
| gossip_nudges_enabled     | False   | True     |
| metrics_tracking_enabled  | False   | True     |
| affinity_tracking_enabled | False   | True     |

The settings are split across two stores by existing architecture:
- `PlayerProfile.preferences` (player-level, persisted to
  `~/.kourai_khryseai/profiles/<player_id>.json`).
- `CLISettings` (host-level, persisted to `<repo>/.cache/cli_settings.json`).

The metrics / nudges keys appear in BOTH stores by design — profile is
the player-level source-of-truth, CLISettings is the host-active cache
that existing code reads from. The cascade writes both.

`romance_enabled` is intentionally False in BOTH paths: full romance
dialogue requires a separate two-step gate (toggle `[5] Romance System`
in `/settings`). Cupid's *nudges* fire under gamified mode, but full
romance is a deeper opt-in than the mode preset.

Idempotent: re-applying the same mode produces identical loaded state
on the next read. Cascade is opinionated — overrides individual toggles
the player may have set independently. Callers warn the player if that
matters.
"""

from __future__ import annotations

import logging
from typing import Literal

from hosts.cli.settings import CLISettings
from kourai_common.player_profile import PlayerProfile

logger = logging.getLogger(__name__)

Mode = Literal["focused", "gamified"]

_VALID_MODES: tuple[str, ...] = ("focused", "gamified")

# PlayerProfile.preferences cascade values.
_FOCUSED_PREFERENCES: dict[str, object] = {
    "experience_mode": "focused",
    "metrics_tracking_enabled": False,
    "affinity_tracking_enabled": False,
    "romance_nudges_enabled": False,
    "gossip_nudges_enabled": False,
}

_GAMIFIED_PREFERENCES: dict[str, object] = {
    "experience_mode": "gamified",
    "metrics_tracking_enabled": True,
    "affinity_tracking_enabled": True,
    "romance_nudges_enabled": True,
    "gossip_nudges_enabled": True,
}

# CLISettings cascade values. romance_enabled stays False in BOTH paths.
_FOCUSED_SETTINGS: dict[str, bool] = {
    "romance_enabled": False,
    "gossip_enabled": False,
    "metrics_tracking_enabled": False,
    "romance_nudges_enabled": False,
    "gossip_nudges_enabled": False,
}

_GAMIFIED_SETTINGS: dict[str, bool] = {
    "romance_enabled": False,
    "gossip_enabled": True,
    "metrics_tracking_enabled": True,
    "romance_nudges_enabled": True,
    "gossip_nudges_enabled": True,
}


def apply_mode_cascade(mode: Mode) -> None:
    """Flip all seven settings between focused and gamified, save both stores.

    Idempotent — re-applying the current mode produces identical state.
    Skips the PlayerProfile write when no profile exists on disk (edge
    case: caller invoked from `/settings` before onboarding ran);
    CLISettings still gets written so the host has a coherent cache.
    """
    if mode not in _VALID_MODES:
        raise ValueError(f"unknown mode: {mode!r} (expected 'focused' or 'gamified')")

    prefs = _GAMIFIED_PREFERENCES if mode == "gamified" else _FOCUSED_PREFERENCES
    setting_values = _GAMIFIED_SETTINGS if mode == "gamified" else _FOCUSED_SETTINGS

    profile = PlayerProfile.load()
    if profile is not None:
        profile.preferences.update(prefs)
        profile.save()
    else:
        logger.debug("apply_mode_cascade: no PlayerProfile on disk; skipping profile write")

    settings = CLISettings.load()
    for key, value in setting_values.items():
        setattr(settings, key, value)
    settings.save()


def current_mode() -> Mode:
    """Read the active mode from `PlayerProfile.preferences`.

    Falls back to `gamified` when no profile exists or the stored value
    is unrecognised — matches the spec default and the existing
    onboarding's keep-Puck behavior.
    """
    profile = PlayerProfile.load()
    if profile is None:
        return "gamified"
    raw = profile.preferences.get("experience_mode", "gamified")
    if raw == "focused":
        return "focused"
    return "gamified"
