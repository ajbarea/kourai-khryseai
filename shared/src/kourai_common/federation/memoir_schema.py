"""Pydantic schemas for Forge Memoir entries.

Each Memoir entry has two faces — a narrative beat the visual novel can
replay, and a training tuple the federated-learning pipeline can consume.
The `SplitDecision` records which side of the council/bond split an entry
falls on. The `decide_split()` pure function applies the gameplay rules
from `docs/research/federated-forge/index.md`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

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


class PlayerResponse(BaseModel):
    """How the player responded to an agent's proposal.

    `kind` is the high-level reaction; `delta` carries free-form payload
    (a diff, a comment, etc); `felt` is the optional Likert-style affect
    tag the host may choose to gather.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["accepted", "modified", "rejected", "deferred"]
    delta: str | None = None
    felt: Literal["right", "off", "unsure"] | None = None


class TrainingLabel(BaseModel):
    """The FL-pipeline view of an entry. `preference_pair` is two scored
    candidates the trainer can consume as a DPO pair; `weight` lets the
    host emphasize or downweight specific entries (e.g. interrupted turns
    weigh less than fully-completed ones).
    """

    model_config = ConfigDict(frozen=True)

    preference_pair: list[dict[str, Any]] | None = None
    weight: float = 1.0


class MemoirEntry(BaseModel):
    """One Memoir entry on disk and on the wire.

    Fields are split into:

    - **identity / context** — `scene_id`, `agent`, `source`,
      `narrative_beat`
    - **narrative payload** — `agent_proposed`, `player_response`,
      `affinity_delta`
    - **training payload** — `training_label`
    - **derived** — `split`, decided automatically from `source` + `agent`
      via `decide_split()` if not provided

    The dual-face contract: every entry can be replayed by the VN via
    `narrative_beat`, AND consumed by the FL pipeline via `training_label`.
    """

    model_config = ConfigDict(frozen=True)

    scene_id: str
    agent: str
    source: EntrySource

    context: dict[str, Any] | None = None

    narrative_beat: str | None = None
    agent_proposed: str | None = None
    player_response: PlayerResponse | None = None
    affinity_delta: float = 0.0
    training_label: TrainingLabel | None = None

    split: SplitDecision = SplitDecision()

    @model_validator(mode="after")
    def _validate_agent_known(self) -> MemoirEntry:
        if self.agent not in ALL_AGENTS:
            raise ValueError(f"unknown agent {self.agent!r}")
        return self

    @model_validator(mode="after")
    def _populate_split(self) -> MemoirEntry:
        if self.split.shared_eligible or self.split.private_only:
            return self  # caller provided one explicitly; trust them
        decided = decide_split(self.source, agent=self.agent)
        # Pydantic frozen models need object.__setattr__ to mutate after init.
        object.__setattr__(self, "split", decided)
        return self
