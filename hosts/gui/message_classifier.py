"""GUI re-export shim for message classification.

The pure regex-based classifiers (is_system_status, is_scratchpad_content)
live in :mod:`kourai_common.message_classifier` so CLI streaming and the
VN bridge can route the same KIND_DIALOGUE-vs-status decision through
one set of regexes. Existing GUI imports of
``hosts.gui.message_classifier`` continue to work unchanged.
"""

from __future__ import annotations

from kourai_common.message_classifier import is_scratchpad_content, is_system_status

__all__ = ["is_scratchpad_content", "is_system_status"]
