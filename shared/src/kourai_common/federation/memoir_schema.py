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
