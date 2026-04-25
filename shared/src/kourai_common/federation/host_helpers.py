"""Pure helpers hosts use to construct MemoirEntries.

These intentionally do no I/O — they take strings and produce typed
schemas. Hosts call them, then hand the result to a `Memoir` writer.
"""

from __future__ import annotations

from kourai_common.federation.memoir_schema import EntrySource, MemoirEntry


def derive_scene_id(session_id: str, *, turn_number: int) -> str:
    """Build a stable scene id of the form `session-<8>.turn-<n>`.

    `session_id` is typically a `ForgeSession.session_id` (uuid hex);
    only the first 8 characters are used to keep scene ids readable.
    """
    if not session_id:
        raise ValueError("session_id must be a non-empty string")
    if turn_number < 0:
        raise ValueError("turn_number must be >= 0")
    short = session_id[:8]
    return f"session-{short}.turn-{turn_number}"


def build_pipeline_turn_entry(
    scene_id: str,
    *,
    agent: str,
    agent_proposed: str,
) -> MemoirEntry:
    """Construct a SPECIALIST_PROPOSED MemoirEntry from CLI-side data.

    The split decision is auto-populated by `MemoirEntry`'s validator.
    Federating-agent inputs produce shared-eligible entries; bond-only
    agents (Cupid, Puck) produce private-only entries — both are valid.
    """
    if not agent_proposed:
        raise ValueError("agent_proposed must be a non-empty string")
    return MemoirEntry(
        scene_id=scene_id,
        agent=agent,
        source=EntrySource.SPECIALIST_PROPOSED,
        agent_proposed=agent_proposed,
    )
