"""GUI re-export shim for dialogue pacing.

The pure timing logic (PacingMode, PacingConfig, DialoguePacer) lives
in :mod:`kourai_common.dialogue_pacing` so CLI streaming can adopt the
same contract. Existing GUI imports of ``hosts.gui.dialogue_pacing``
continue to work unchanged.
"""

from __future__ import annotations

from kourai_common.dialogue_pacing import DialoguePacer, PacingConfig, PacingMode

__all__ = ["DialoguePacer", "PacingConfig", "PacingMode"]
