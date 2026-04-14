"""Backward-compatible wrapper for the centralized Audio Manager.

New code should import from kourai_common.audio directly.
"""

from __future__ import annotations

import logging

from kourai_common.audio import AudioManager as CentralAudioManager

logger = logging.getLogger(__name__)


class AudioManager(CentralAudioManager):
    """GUI-specific wrapper for the centralized AudioManager."""
