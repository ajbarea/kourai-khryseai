"""Cross-host scratchpad — agent chain-of-thought / TODO buffer.

Per-agent ring buffer of recent ``ScratchpadEntry`` instances. Each host
wires ``kourai_common.message_classifier.is_scratchpad_content`` into
``Scratchpad.add()`` and renders entries in its own idiom (CLI slash
command + ANSI block; future GUI overlay panel; future VN parchment).

`research(2026-05)`: the 2026 best practice for LLM scratchpad / CoT
display is "render distinct from dialogue, prefer structured visibility,
don't TTS the reasoning". Documented visibility tiers: in-context visible,
structured (JSON / YAML), tool traces, hidden / private. Kourai routes
classifier-shaped multi-line bullet / TODO / checkbox content into this
buffer at the host boundary; renderers display newest-last per agent
without piping through the synth path. Sources: ICLR 2026 "scratchpads +
verifiers" (arxiv 2510.27246); Masood 2026-04 "Engineering Trustworthy LM
Agents with Scratchpads and Verifiers"; Unite.AI "Scratchpad Technique" (2026).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

DEFAULT_MAX_PER_AGENT: int = 20
"""Per-agent ring buffer cap.

Sized for a single player session. ~20 entries × ~10 maidens ≈ 200
max in the worst case; well inside cheap. Tuned so /scratchpad output
fits a typical terminal scrollback without paging.
"""


@dataclass(frozen=True)
class ScratchpadEntry:
    """One scratchpad message from an agent.

    ``text`` is the raw classifier-shaped multi-line string (bullets,
    TODO, ``[ ]`` checkboxes, numbered steps); renderers split on
    newline as they see fit. ``timestamp`` is wall-clock seconds for
    chronological display.
    """

    agent: str
    text: str
    timestamp: float


class Scratchpad:
    """Per-agent ring-buffered scratchpad.

    Each agent has an independent ``deque(maxlen=max_per_agent)`` so
    a chatty maiden doesn't push other maidens' entries out. Cross-
    agent ordering is recovered via wall-clock timestamp at display.
    """

    def __init__(self, max_per_agent: int = DEFAULT_MAX_PER_AGENT):
        self._max = max_per_agent
        self._by_agent: dict[str, deque[ScratchpadEntry]] = {}

    def add(self, agent: str, text: str) -> ScratchpadEntry:
        """Append a scratchpad entry for ``agent``. Returns the entry."""
        entry = ScratchpadEntry(agent=agent, text=text, timestamp=time.time())
        buf = self._by_agent.setdefault(agent, deque(maxlen=self._max))
        buf.append(entry)
        return entry

    def entries(self, agent: str | None = None) -> list[ScratchpadEntry]:
        """Return entries for ``agent``, or all agents oldest-first if None."""
        if agent is None:
            merged: list[ScratchpadEntry] = []
            for buf in self._by_agent.values():
                merged.extend(buf)
            merged.sort(key=lambda e: e.timestamp)
            return merged
        return list(self._by_agent.get(agent, ()))

    def agents(self) -> list[str]:
        """Return agents that have at least one buffered entry, alphabetical."""
        return sorted(a for a, buf in self._by_agent.items() if buf)

    def clear(self, agent: str | None = None) -> None:
        """Clear ``agent``'s buffer, or all buffers if None."""
        if agent is None:
            self._by_agent.clear()
        else:
            self._by_agent.pop(agent, None)

    def __len__(self) -> int:
        return sum(len(b) for b in self._by_agent.values())


# Process-scoped singleton — each host imports and uses it directly.
# kourai_common.scratchpad lives in shared/, instantiated once per
# Python process. CLI, GUI, vn_bridge all share the same instance
# within a process; cross-process state is intentionally NOT shared
# (each invocation is a separate player session).
_SHARED: Scratchpad | None = None


def get_scratchpad() -> Scratchpad:
    """Return the process-scoped ``Scratchpad`` singleton (lazy-init)."""
    global _SHARED
    if _SHARED is None:
        _SHARED = Scratchpad()
    return _SHARED


def reset_scratchpad() -> None:
    """Reset the singleton. Test-only; production callers don't need this."""
    global _SHARED
    _SHARED = None
