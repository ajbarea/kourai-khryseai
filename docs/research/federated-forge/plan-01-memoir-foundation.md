# Federated Forge — Sub-Plan 01: Memoir Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Forge Memoir library — a typed, append-only JSONL data layer where every entry is simultaneously a narrative beat for the visual novel and a labeled training tuple for the federated learning pipeline. This sub-plan ships the library only; host integration ships in plan-02.

**Architecture:** A new `kourai_common.federation` subpackage holds two modules: `memoir_schema.py` defines pydantic models for entries and the gameplay-rule split decision (which entries are `shared_eligible` vs. `private_only`); `memoir.py` provides a `Memoir` class with append-only writer and iterating reader, scoped to one `ForgeSession`. The library is pure — no host code, no agent code, no FL code touches it yet.

**Tech Stack:** Python 3.12, pydantic v2 (already transitively pulled via a2a-sdk; promoted to explicit dep in this plan), pytest 9, hatchling build backend.

**Spec reference:** [`docs/research/federated-forge/index.md`](./index.md) — see the Forge Memoir section for the schema, the shared/personal split table for the gameplay rules, and Phase 1 of the phasing list for scope.

---

## File Structure

**Create:**

- `shared/src/kourai_common/federation/__init__.py` — empty subpackage marker
- `shared/src/kourai_common/federation/memoir_schema.py` — pydantic models (`MemoirEntry`, `PlayerResponse`, `TrainingLabel`, `SplitDecision`) plus the pure `decide_split()` function applying the gameplay rules from the spec
- `shared/src/kourai_common/federation/memoir.py` — `Memoir` reader/writer scoped to one ForgeSession, JSONL append-only on disk
- `tests/unit/test_memoir_schema.py` — schema validation, split-decision rule coverage
- `tests/unit/test_memoir.py` — round-trip writer/reader, file-on-disk behavior, error handling

**Modify:**

- `shared/pyproject.toml` — promote pydantic from transitive to explicit dep at `>=2.0,<3.0`

**No host code is touched in this plan.** Plan-02 will wire the CLI host to write Memoir entries; plan-03 covers GUI; plan-04 covers VN.

---

## Task 1: Promote pydantic to an explicit dependency

**Files:**

- Modify: `shared/pyproject.toml`

- [ ] **Step 1: Read current dependencies block**

Run: `head -25 shared/pyproject.toml`
Expected output: `[project]` block with a `dependencies = [...]` list including `a2a-sdk`, `litellm`, `httpx`, `mcp`, `opentelemetry-*`, `huggingface-hub`. Pydantic is NOT listed (it's transitive via a2a-sdk).

- [ ] **Step 2: Add pydantic to the dependencies list**

In `shared/pyproject.toml`, the `dependencies = [` list currently ends with `"huggingface-hub>=1.5.0",`. Insert this line just before the closing `]`:

```toml
    "pydantic>=2.0,<3.0",
```

The full edited block should now end:

```toml
    "opentelemetry-exporter-otlp-proto-http>=1.20.0",
    "huggingface-hub>=1.5.0",
    "pydantic>=2.0,<3.0",
]
```

- [ ] **Step 3: Re-resolve the lockfile**

Run: `uv sync`
Expected output: `Resolved N packages` (lockfile updated; the install step is a no-op because pydantic is already present transitively at v2.12.5).

- [ ] **Step 4: Confirm import still works**

Run: `uv run python -c "import pydantic; print(pydantic.VERSION)"`
Expected output: `2.12.5` (or any 2.x).

- [ ] **Step 5: Commit**

```bash
git add shared/pyproject.toml uv.lock
git commit -m "deps(kourai-common): promote pydantic to explicit dep for Forge Memoir schema"
```

---

## Task 2: Create the federation subpackage marker

**Files:**

- Create: `shared/src/kourai_common/federation/__init__.py`

- [ ] **Step 1: Create the subpackage directory and empty `__init__.py`**

```bash
mkdir -p shared/src/kourai_common/federation
touch shared/src/kourai_common/federation/__init__.py
```

The file should be empty. Public API will be defined later when plan-02+ adds adapters and trainers; for now the library is internal.

- [ ] **Step 2: Verify it imports**

Run: `uv run python -c "import kourai_common.federation; print('ok')"`
Expected output: `ok`

- [ ] **Step 3: Commit**

```bash
git add shared/src/kourai_common/federation/__init__.py
git commit -m "feat(kourai-common): scaffold kourai_common.federation subpackage"
```

---

## Task 3: Define the SplitDecision dataclass with failing tests

**Files:**

- Create: `tests/unit/test_memoir_schema.py`
- Create: `shared/src/kourai_common/federation/memoir_schema.py`

- [ ] **Step 1: Write the failing test for SplitDecision**

Create `tests/unit/test_memoir_schema.py` with this content:

```python
"""Schema models and gameplay-rule split logic for the Forge Memoir."""

from __future__ import annotations

import pytest

from kourai_common.federation.memoir_schema import SplitDecision


class TestSplitDecision:
    """SplitDecision is a frozen pydantic model with two booleans and an
    invariant that they cannot both be true."""

    def test_shared_eligible_only(self):
        d = SplitDecision(shared_eligible=True, private_only=False)
        assert d.shared_eligible is True
        assert d.private_only is False

    def test_private_only_only(self):
        d = SplitDecision(shared_eligible=False, private_only=True)
        assert d.shared_eligible is False
        assert d.private_only is True

    def test_neither_set_is_valid(self):
        # Used for entries that are still being constructed.
        d = SplitDecision(shared_eligible=False, private_only=False)
        assert d.shared_eligible is False
        assert d.private_only is False

    def test_both_true_is_rejected(self):
        with pytest.raises(ValueError, match="cannot both be true"):
            SplitDecision(shared_eligible=True, private_only=True)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_memoir_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kourai_common.federation.memoir_schema'`

- [ ] **Step 3: Implement SplitDecision**

Create `shared/src/kourai_common/federation/memoir_schema.py` with this content:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_memoir_schema.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_memoir_schema.py shared/src/kourai_common/federation/memoir_schema.py
git commit -m "feat(memoir): add SplitDecision schema with at-most-one-true invariant"
```

---

## Task 4: Define decide_split() with one test per gameplay rule row

**Files:**

- Modify: `tests/unit/test_memoir_schema.py`
- Modify: `shared/src/kourai_common/federation/memoir_schema.py`

The spec's gameplay-rule table has these rows:

| Row | Source | Result |
|---|---|---|
| 1 | Specialist's proposed output | shared_eligible=True |
| 2 | Player's revised version (the diff) | private_only=True |
| 3 | Federating-agent interrupt | shared_eligible=True |
| 4 | Cupid or Puck interrupt | private_only=True |
| 5 | Inter-agent disagreement resolution | shared_eligible=True |
| 6 | Cupid scene of any kind | private_only=True |
| 7 | Puck tutorial / minigame / engagement | private_only=True |
| 8 | Affinity gain or loss | private_only=True |
| 9 | Player profile / memory_moments / relationship state | private_only=True |
| 10 | Raw forge transcript | private_only=True |
| 11 | Player's task description (free text) | private_only=True |

`decide_split()` is a pure function over a small enum of source types.

- [ ] **Step 1: Add the failing tests for decide_split**

Append to `tests/unit/test_memoir_schema.py`:

```python
from kourai_common.federation.memoir_schema import (
    EntrySource,
    decide_split,
)


class TestDecideSplit:
    """Pure function applying the gameplay rules from the design spec."""

    def test_specialist_proposed_output_is_shared(self):
        d = decide_split(EntrySource.SPECIALIST_PROPOSED, agent="kallos")
        assert d.shared_eligible is True
        assert d.private_only is False

    def test_player_revision_is_private(self):
        d = decide_split(EntrySource.PLAYER_REVISION, agent="kallos")
        assert d.shared_eligible is False
        assert d.private_only is True

    def test_federating_agent_interrupt_is_shared(self):
        d = decide_split(EntrySource.AGENT_INTERRUPT, agent="aidos")
        assert d.shared_eligible is True
        assert d.private_only is False

    def test_cupid_interrupt_is_private(self):
        d = decide_split(EntrySource.AGENT_INTERRUPT, agent="cupid")
        assert d.private_only is True
        assert d.shared_eligible is False

    def test_puck_interrupt_is_private(self):
        d = decide_split(EntrySource.AGENT_INTERRUPT, agent="puck")
        assert d.private_only is True
        assert d.shared_eligible is False

    def test_disagreement_resolution_is_shared(self):
        d = decide_split(EntrySource.DISAGREEMENT_RESOLUTION, agent="hephaestus")
        assert d.shared_eligible is True
        assert d.private_only is False

    def test_cupid_scene_is_private(self):
        d = decide_split(EntrySource.CUPID_SCENE, agent="cupid")
        assert d.private_only is True

    def test_puck_engagement_is_private(self):
        d = decide_split(EntrySource.PUCK_ENGAGEMENT, agent="puck")
        assert d.private_only is True

    def test_affinity_change_is_private(self):
        d = decide_split(EntrySource.AFFINITY_CHANGE, agent="cupid")
        assert d.private_only is True

    def test_player_profile_is_private(self):
        d = decide_split(EntrySource.PLAYER_PROFILE, agent=None)
        assert d.private_only is True

    def test_raw_transcript_is_private(self):
        d = decide_split(EntrySource.RAW_TRANSCRIPT, agent=None)
        assert d.private_only is True

    def test_task_description_is_private(self):
        d = decide_split(EntrySource.TASK_DESCRIPTION, agent=None)
        assert d.private_only is True

    def test_unknown_agent_for_interrupt_raises(self):
        with pytest.raises(ValueError, match="unknown agent"):
            decide_split(EntrySource.AGENT_INTERRUPT, agent="nobody")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_memoir_schema.py::TestDecideSplit -v`
Expected: 13 failures with `ImportError: cannot import name 'EntrySource'`

- [ ] **Step 3: Implement EntrySource and decide_split**

Append to `shared/src/kourai_common/federation/memoir_schema.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_memoir_schema.py -v`
Expected: 17 passed (4 from Task 3 + 13 from Task 4)

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_memoir_schema.py shared/src/kourai_common/federation/memoir_schema.py
git commit -m "feat(memoir): add decide_split() pure function applying gameplay-rule table"
```

---

## Task 5: Define MemoirEntry with auto-decided split

**Files:**

- Modify: `tests/unit/test_memoir_schema.py`
- Modify: `shared/src/kourai_common/federation/memoir_schema.py`

`MemoirEntry` is the wire/disk schema. Each entry knows its source, populates `SplitDecision` automatically, and carries the dual-face contract: `narrative_beat` for the VN replay, `training_label` for the FL pipeline.

This sub-plan only ships the `pipeline_turn` and `agent_interrupt` shapes; richer shapes (`council_event`, `loyalty_beat`) come in later sub-plans.

- [ ] **Step 1: Add the failing tests for MemoirEntry**

Append to `tests/unit/test_memoir_schema.py`:

```python
from kourai_common.federation.memoir_schema import (
    MemoirEntry,
    PlayerResponse,
    TrainingLabel,
)


class TestMemoirEntry:
    """The on-disk schema. Each entry carries narrative + training payloads
    and auto-populates its SplitDecision from EntrySource + agent."""

    def test_minimal_specialist_proposal_is_shared(self):
        entry = MemoirEntry(
            scene_id="session-1.turn-1",
            agent="kallos",
            source=EntrySource.SPECIALIST_PROPOSED,
            agent_proposed="some style edit",
        )
        assert entry.split.shared_eligible is True
        assert entry.split.private_only is False

    def test_cupid_scene_is_private(self):
        entry = MemoirEntry(
            scene_id="session-1.scene-cupid-7",
            agent="cupid",
            source=EntrySource.CUPID_SCENE,
            narrative_beat="cupid_late_night_check_in",
        )
        assert entry.split.private_only is True

    def test_pipeline_turn_with_player_response(self):
        entry = MemoirEntry(
            scene_id="session-1.turn-2",
            agent="kallos",
            source=EntrySource.SPECIALIST_PROPOSED,
            agent_proposed="lint fix",
            player_response=PlayerResponse(
                kind="modified", delta="player edits", felt="right"
            ),
            training_label=TrainingLabel(
                preference_pair=[
                    {"text": "lint fix", "score": 0},
                    {"text": "lint fix with player edits", "score": 1},
                ],
                weight=1.0,
            ),
        )
        assert entry.player_response.kind == "modified"
        assert entry.training_label.weight == 1.0

    def test_unknown_agent_rejected(self):
        with pytest.raises(ValueError, match="unknown agent"):
            MemoirEntry(
                scene_id="session-1.turn-3",
                agent="nobody",
                source=EntrySource.SPECIALIST_PROPOSED,
                agent_proposed="x",
            )

    def test_round_trip_json(self):
        original = MemoirEntry(
            scene_id="session-1.turn-1",
            agent="kallos",
            source=EntrySource.SPECIALIST_PROPOSED,
            agent_proposed="hello",
        )
        as_json = original.model_dump_json()
        restored = MemoirEntry.model_validate_json(as_json)
        assert restored == original

    def test_optional_context_block_round_trips(self):
        # Spec shows a `context` block with task_type, transcript_hash,
        # preceding_agents. We accept any dict for forward compatibility;
        # plan-02 will lock in the host-emitted shape.
        original = MemoirEntry(
            scene_id="session-1.turn-1",
            agent="kallos",
            source=EntrySource.SPECIALIST_PROPOSED,
            agent_proposed="hello",
            context={
                "task_type": "style_review",
                "transcript_hash": "sha256:abc",
                "preceding_agents": ["techne"],
            },
        )
        restored = MemoirEntry.model_validate_json(original.model_dump_json())
        assert restored.context["task_type"] == "style_review"
        assert restored.context["preceding_agents"] == ["techne"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_memoir_schema.py::TestMemoirEntry -v`
Expected: 5 failures with `ImportError: cannot import name 'MemoirEntry'`

- [ ] **Step 3: Implement MemoirEntry, PlayerResponse, TrainingLabel**

Append to `shared/src/kourai_common/federation/memoir_schema.py`:

```python
from typing import Any, Literal


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
    def _populate_split(self) -> MemoirEntry:
        if self.split.shared_eligible or self.split.private_only:
            return self  # caller provided one explicitly; trust them
        decided = decide_split(self.source, agent=self.agent)
        # Pydantic frozen models need object.__setattr__ to mutate after init.
        object.__setattr__(self, "split", decided)
        return self
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_memoir_schema.py -v`
Expected: 23 passed (17 from prior tasks + 6 new — including the optional-context round-trip)

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_memoir_schema.py shared/src/kourai_common/federation/memoir_schema.py
git commit -m "feat(memoir): add MemoirEntry, PlayerResponse, TrainingLabel with auto-split"
```

---

## Task 6: Build the append-only Memoir writer

**Files:**

- Create: `tests/unit/test_memoir.py`
- Create: `shared/src/kourai_common/federation/memoir.py`

The writer takes a directory path (typically `forge_session.workdir`), opens `memoir.jsonl` for appending, and writes one JSON-encoded entry per line. Append-only by contract; no concurrent-writer guarantees in this iteration (a single host owns one Memoir at a time).

- [ ] **Step 1: Write the failing tests for Memoir.append**

Create `tests/unit/test_memoir.py` with this content:

```python
"""Memoir reader/writer scoped to one ForgeSession workdir."""

from __future__ import annotations

import pytest

from kourai_common.federation.memoir import Memoir, MemoirError
from kourai_common.federation.memoir_schema import (
    EntrySource,
    MemoirEntry,
)


class TestMemoirAppend:
    """Append-only writes produce one JSON-encoded line per entry."""

    def test_append_creates_file(self, tmp_path):
        memoir = Memoir(tmp_path)
        entry = MemoirEntry(
            scene_id="s1.t1",
            agent="kallos",
            source=EntrySource.SPECIALIST_PROPOSED,
            agent_proposed="x",
        )
        memoir.append(entry)
        assert (tmp_path / "memoir.jsonl").exists()

    def test_append_writes_one_line_per_entry(self, tmp_path):
        memoir = Memoir(tmp_path)
        for i in range(3):
            memoir.append(
                MemoirEntry(
                    scene_id=f"s1.t{i}",
                    agent="kallos",
                    source=EntrySource.SPECIALIST_PROPOSED,
                    agent_proposed=f"x{i}",
                )
            )
        contents = (tmp_path / "memoir.jsonl").read_text()
        lines = contents.strip().split("\n")
        assert len(lines) == 3

    def test_append_does_not_truncate(self, tmp_path):
        m1 = Memoir(tmp_path)
        m1.append(
            MemoirEntry(
                scene_id="s1.t1",
                agent="kallos",
                source=EntrySource.SPECIALIST_PROPOSED,
                agent_proposed="first",
            )
        )

        m2 = Memoir(tmp_path)
        m2.append(
            MemoirEntry(
                scene_id="s1.t2",
                agent="kallos",
                source=EntrySource.SPECIALIST_PROPOSED,
                agent_proposed="second",
            )
        )

        contents = (tmp_path / "memoir.jsonl").read_text()
        assert "first" in contents
        assert "second" in contents

    def test_append_to_missing_directory_raises(self, tmp_path):
        bogus = tmp_path / "does_not_exist"
        memoir = Memoir(bogus)
        with pytest.raises(MemoirError, match="not a directory"):
            memoir.append(
                MemoirEntry(
                    scene_id="s1.t1",
                    agent="kallos",
                    source=EntrySource.SPECIALIST_PROPOSED,
                    agent_proposed="x",
                )
            )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_memoir.py -v`
Expected: 4 failures with `ModuleNotFoundError: No module named 'kourai_common.federation.memoir'`

- [ ] **Step 3: Implement the Memoir class with append**

Create `shared/src/kourai_common/federation/memoir.py` with this content:

```python
"""Forge Memoir reader/writer.

The Memoir is the canonical record of one ForgeSession — a JSONL file
where each line is a `MemoirEntry`. Every entry has two faces: a
narrative beat the visual novel can replay, and a training tuple the
federated-learning pipeline can consume.

Append-only by contract. One host owns one Memoir at a time; no
cross-process coordination is provided in this iteration.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from kourai_common.federation.memoir_schema import MemoirEntry


MEMOIR_FILENAME = "memoir.jsonl"


class MemoirError(Exception):
    """Raised on Memoir read/write failures."""


class Memoir:
    """Reader/writer for one ForgeSession's memoir.jsonl file."""

    def __init__(self, workdir: Path) -> None:
        self.workdir = Path(workdir)
        self.path = self.workdir / MEMOIR_FILENAME

    def append(self, entry: MemoirEntry) -> None:
        if not self.workdir.is_dir():
            raise MemoirError(f"workdir {self.workdir} is not a directory")
        with self.path.open("a", encoding="utf-8") as f:
            f.write(entry.model_dump_json())
            f.write("\n")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_memoir.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_memoir.py shared/src/kourai_common/federation/memoir.py
git commit -m "feat(memoir): add append-only JSONL writer scoped to ForgeSession workdir"
```

---

## Task 7: Build the iterating Memoir reader

**Files:**

- Modify: `tests/unit/test_memoir.py`
- Modify: `shared/src/kourai_common/federation/memoir.py`

The reader iterates entries from disk in append order. Used by replay tooling, the bond trainer (next sub-plan), and the council trainer (later sub-plan).

- [ ] **Step 1: Write the failing tests for Memoir.entries()**

Append to `tests/unit/test_memoir.py`:

```python
class TestMemoirRead:
    """`entries()` yields one MemoirEntry per JSONL line, preserving order."""

    def test_empty_memoir_yields_nothing(self, tmp_path):
        memoir = Memoir(tmp_path)
        assert list(memoir.entries()) == []

    def test_round_trip_preserves_order(self, tmp_path):
        memoir = Memoir(tmp_path)
        originals = [
            MemoirEntry(
                scene_id=f"s1.t{i}",
                agent="kallos",
                source=EntrySource.SPECIALIST_PROPOSED,
                agent_proposed=f"x{i}",
            )
            for i in range(5)
        ]
        for entry in originals:
            memoir.append(entry)

        restored = list(memoir.entries())
        assert restored == originals

    def test_round_trip_preserves_split(self, tmp_path):
        memoir = Memoir(tmp_path)
        cupid_entry = MemoirEntry(
            scene_id="s1.cupid",
            agent="cupid",
            source=EntrySource.CUPID_SCENE,
            narrative_beat="cupid_check_in",
        )
        kallos_entry = MemoirEntry(
            scene_id="s1.kallos",
            agent="kallos",
            source=EntrySource.SPECIALIST_PROPOSED,
            agent_proposed="lint fix",
        )
        memoir.append(cupid_entry)
        memoir.append(kallos_entry)

        restored = list(memoir.entries())
        assert restored[0].split.private_only is True
        assert restored[1].split.shared_eligible is True

    def test_malformed_line_raises(self, tmp_path):
        memoir = Memoir(tmp_path)
        memoir.path.write_text("not valid json\n")
        with pytest.raises(MemoirError, match="malformed"):
            list(memoir.entries())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_memoir.py::TestMemoirRead -v`
Expected: 4 failures with `AttributeError: 'Memoir' object has no attribute 'entries'`

- [ ] **Step 3: Implement Memoir.entries()**

Edit `shared/src/kourai_common/federation/memoir.py`. Add the import at the top (alongside the existing imports):

```python
import json
```

Then add this method to the `Memoir` class (after `append`):

```python
    def entries(self) -> Iterator[MemoirEntry]:
        """Yield each entry from the on-disk file in append order.

        Returns an empty iterator if the file does not exist yet.
        """
        from kourai_common.federation.memoir_schema import MemoirEntry

        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    yield MemoirEntry.model_validate_json(stripped)
                except (json.JSONDecodeError, ValueError) as e:
                    raise MemoirError(
                        f"malformed entry on line {line_number}: {e}"
                    ) from e
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_memoir.py -v`
Expected: 8 passed (4 from Task 6 + 4 new)

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_memoir.py shared/src/kourai_common/federation/memoir.py
git commit -m "feat(memoir): add Memoir.entries() iterator over append-order JSONL"
```

---

## Task 8: Run the full kourai-common unit suite to confirm no regressions

**Files:** none modified

- [ ] **Step 1: Run the full unit test directory**

Run: `uv run pytest tests/unit -v`
Expected: All previously-passing tests still pass; 23 new tests in `test_memoir_schema.py`; 8 new tests in `test_memoir.py`. Total new: 31. Pre-existing test count is preserved.

- [ ] **Step 2: Run ruff and ty over the new files**

Run: `uv run ruff check shared/src/kourai_common/federation/ tests/unit/test_memoir.py tests/unit/test_memoir_schema.py`
Expected: `All checks passed!` or empty output.

Run: `uv run ty check shared/src/kourai_common/federation/`
Expected: no diagnostics.

If either reports issues, fix them inline and re-run.

- [ ] **Step 3: Confirm the federation subpackage is now properly importable**

Run: `uv run python -c "from kourai_common.federation.memoir import Memoir; from kourai_common.federation.memoir_schema import MemoirEntry, EntrySource, decide_split; print('ok')"`
Expected: `ok`

- [ ] **Step 4: No commit needed (this task is a verification gate)**

---

## What this plan ships

- `kourai_common.federation.memoir_schema` — `EntrySource`, `SplitDecision`, `PlayerResponse`, `TrainingLabel`, `MemoirEntry`, `decide_split`, `FEDERATING_AGENTS`, `BOND_ONLY_AGENTS`, `ALL_AGENTS`
- `kourai_common.federation.memoir` — `Memoir`, `MemoirError`, `MEMOIR_FILENAME`
- 30 new unit tests, all passing
- pydantic promoted to explicit dep
- Zero host or agent code changed

## What's deferred to follow-up plans

- Plan-02 — CLI host integration (CLI emits Memoir entries on every agent turn and player response)
- Plan-03 — GUI host integration
- Plan-04 — VN host integration
- Plan-05 — `kourai-dev memoir` inspection CLI command (replay tooling)
- Plan-06 — interrupt entry shape and the concurrent interrupt channel itself
- Plan-07 — bond adapter scaffolding and local trainer (consumes the Memoir)
- Later plans — vFL LoRA-FAIR strategy, federation client, DP, Council scenes, Byzantine simulation, online preference learning ablation, evaluation pipeline

Each follow-up plan stands alone and has clear dependencies on this one (and on each other).
