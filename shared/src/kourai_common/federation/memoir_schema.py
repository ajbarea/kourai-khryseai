"""Pydantic schemas for Forge Memoir entries.

Each Memoir entry has two faces — a narrative beat the visual novel can
replay, and a training tuple the federated-learning pipeline can consume.
The `SplitDecision` records which side of the council/bond split an entry
falls on. The `decide_split()` pure function applies the gameplay rules
from `docs/research/federated-forge/index.md`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class SplitDecision(BaseModel):
    """Whether a Memoir entry contributes to the federated council adapter,
    stays in the local bond adapter only, or has not been decided yet.

    Invariant: `shared_eligible` and `private_only` cannot both be true.
    Both false is valid for entries still under construction.
    """

    model_config = ConfigDict(frozen=True)

    shared_eligible: bool = False
    private_only: bool = False

    @model_validator(mode="after")
    def _at_most_one_true(self) -> SplitDecision:
        if self.shared_eligible and self.private_only:
            raise ValueError(
                "shared_eligible and private_only cannot both be true"
            )
        return self


from enum import StrEnum


class EntrySource(StrEnum):
    """Where a Memoir entry came from. The split decision is keyed off this
    enum and (for interrupts) the originating agent."""

    SPECIALIST_PROPOSED = "specialist_proposed"
    PLAYER_REVISION = "player_revision"
    AGENT_INTERRUPT = "agent_interrupt"
    DISAGREEMENT_RESOLUTION = "disagreement_resolution"
    CUPID_SCENE = "cupid_scene"
    PUCK_ENGAGEMENT = "puck_engagement"
    AFFINITY_CHANGE = "affinity_change"
    PLAYER_PROFILE = "player_profile"
    RAW_TRANSCRIPT = "raw_transcript"
    TASK_DESCRIPTION = "task_description"


# Agents that have a council adapter. Cupid and Puck are bond-only by
# construction (see spec, Goals/Non-goals section).
FEDERATING_AGENTS: frozenset[str] = frozenset(
    {
        "hephaestus",
        "metis",
        "techne",
        "dokimasia",
        "kallos",
        "mneme",
        "aidos",
        "aletheia",
    }
)
BOND_ONLY_AGENTS: frozenset[str] = frozenset({"cupid", "puck"})
ALL_AGENTS: frozenset[str] = FEDERATING_AGENTS | BOND_ONLY_AGENTS


def decide_split(source: EntrySource, *, agent: str | None) -> SplitDecision:
    """Apply the gameplay rules from the design spec.

    Patterns leave the forge; instances do not. Federating agents'
    proposed outputs and interrupts are shared-eligible; everything
    keyed to the player or the relationship layer is private-only.
    """
    if source in {
        EntrySource.PLAYER_REVISION,
        EntrySource.CUPID_SCENE,
        EntrySource.PUCK_ENGAGEMENT,
        EntrySource.AFFINITY_CHANGE,
        EntrySource.PLAYER_PROFILE,
        EntrySource.RAW_TRANSCRIPT,
        EntrySource.TASK_DESCRIPTION,
    }:
        return SplitDecision(shared_eligible=False, private_only=True)

    if source in {
        EntrySource.SPECIALIST_PROPOSED,
        EntrySource.DISAGREEMENT_RESOLUTION,
    }:
        return SplitDecision(shared_eligible=True, private_only=False)

    if source is EntrySource.AGENT_INTERRUPT:
        if agent is None or agent not in ALL_AGENTS:
            raise ValueError(f"unknown agent {agent!r} for AGENT_INTERRUPT")
        if agent in BOND_ONLY_AGENTS:
            return SplitDecision(shared_eligible=False, private_only=True)
        return SplitDecision(shared_eligible=True, private_only=False)

    raise ValueError(f"unhandled EntrySource {source!r}")
