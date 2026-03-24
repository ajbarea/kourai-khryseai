"""Backwards-compatibility shim — imports from focused submodules.

The original god module has been split into:
- player_constants: All module-level constants and _now_iso()
- player_profile: PlayerProfile class + profile management
- player_memory: Memory CRUD, retrieval scoring, gossip transfer, decay
- player_affinity: Affinity tracking + romance progression
- player_alignment: Alignment-gated dialogue instructions
- player_romance: Romance dialogue system + jealousy context
- player_context: Prompt builder hub (get_enriched_system_prompt, build_player_context)
- player_io: Data import/export

All public names are re-exported here so existing `from kourai_common.player import X`
statements continue to work without modification.

Test fixtures that monkeypatch attributes on this module (e.g.
``monkeypatch.setattr(player_mod, "_get_player_db", ...)``) are forwarded
to the real submodule via a custom ``__setattr__`` installed at import time.
"""

from __future__ import annotations

import sys
import types

import kourai_common.player_affinity as _mod_affinity
import kourai_common.player_alignment as _mod_alignment

# ── Attribute-forwarding for monkeypatch / test compatibility ──────────
#
# When tests do ``monkeypatch.setattr(player_mod, "_get_player_db", ...)``,
# the write must land in the submodule where the function's callers actually
# look it up (the function closes over its own module globals).
import kourai_common.player_constants as _mod_constants
import kourai_common.player_context as _mod_context
import kourai_common.player_io as _mod_io
import kourai_common.player_memory as _mod_memory
import kourai_common.player_profile as _mod_profile
import kourai_common.player_romance as _mod_romance
from kourai_common.player_affinity import *  # noqa: F403
from kourai_common.player_alignment import *  # noqa: F403
from kourai_common.player_constants import *  # noqa: F403
from kourai_common.player_constants import (
    _LEGACY_PLAYER_FILE,  # noqa: F401
    _now_iso,  # noqa: F401
)
from kourai_common.player_context import *  # noqa: F403
from kourai_common.player_io import *  # noqa: F403
from kourai_common.player_memory import *  # noqa: F403
from kourai_common.player_memory import (  # noqa: F401
    _ensure_player_tables,
    _get_player_db,
    _tables_initialized,
)
from kourai_common.player_profile import *  # noqa: F403
from kourai_common.player_romance import *  # noqa: F403

_SUBMODULES: list[types.ModuleType] = [
    _mod_constants,
    _mod_profile,
    _mod_memory,
    _mod_affinity,
    _mod_alignment,
    _mod_romance,
    _mod_context,
    _mod_io,
]


class _PlayerShimModule(types.ModuleType):
    """Module subclass that forwards attribute writes to the owning submodule.

    This ensures ``monkeypatch.setattr(player_mod, "X", val)`` propagates
    to the submodule where ``X`` is actually used by other functions.
    """

    _submodules = _SUBMODULES  # class-level ref survives module replacement

    def __setattr__(self, name: str, value: object) -> None:
        # Always set locally so ``getattr(player_mod, name)`` returns the patched value
        super().__setattr__(name, value)
        # Also forward to every submodule that has this attribute, so functions
        # that close over their module globals see the patched value.
        for mod in type(self)._submodules:
            if hasattr(mod, name):
                object.__setattr__(mod, name, value)


# Replace this module in sys.modules with our shim class instance
_this = sys.modules[__name__]
_shim = _PlayerShimModule(__name__, __doc__)
_shim.__dict__.update(_this.__dict__)
_shim.__file__ = _this.__file__
_shim.__loader__ = _this.__loader__
_shim.__package__ = _this.__package__
_shim.__spec__ = _this.__spec__
_shim.__path__ = getattr(_this, "__path__", [])
sys.modules[__name__] = _shim
