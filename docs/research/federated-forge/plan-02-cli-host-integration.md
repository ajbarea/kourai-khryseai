# Federated Forge — Sub-Plan 02: CLI Host Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the kourai-khryseai CLI host so every successful Forge run writes one `MemoirEntry` to disk. Bond and council adapter training in later sub-plans will consume these entries; this plan ships the producer for the simplest case (one entry per pipeline run, capturing the final agent's output).

**Architecture:** A small pure helper module `kourai_common.federation.host_helpers` provides two functions: `derive_scene_id(session_id, turn_number) -> str` and `build_pipeline_turn_entry(scene_id, agent, agent_proposed) -> MemoirEntry`. The CLI's `send_and_stream` accepts an optional `Memoir` plus a scene id and writes one entry on successful completion. The CLI main loop instantiates a `Memoir(forge_session.workdir)` when a `ForgeSession` starts and threads a turn counter through.

**Tech Stack:** Python 3.12, pydantic v2 (already present from plan-01), pytest 9, the existing `_make_task` mocked-client pattern from `tests/unit/test_cli.py`.

**Spec reference:** [`docs/research/federated-forge/index.md`](./index.md) — Forge Memoir section. **Prior plan:** [`plan-01-memoir-foundation.md`](./plan-01-memoir-foundation.md) shipped the library this plan now wires up.

**Scope discipline.** Plan-02 ships ONE entry per pipeline run, source `SPECIALIST_PROPOSED`, agent = the last maiden seen by `get_last_seen_agent()`. It does NOT write player-revision entries (no `/accept` / `/discard` integration yet — defers to plan-05 along with replay tooling), does NOT capture intermediate per-agent turns (defers to plan-06's interrupt channel), does NOT touch the GUI or VN hosts (plan-03 / plan-04). Keep the diff focused.

---

## File Structure

**Create:**

- `shared/src/kourai_common/federation/host_helpers.py` — `derive_scene_id`, `build_pipeline_turn_entry`
- `tests/unit/test_host_helpers.py` — unit tests for the pure helpers

**Modify:**

- `hosts/cli/streaming.py` — `send_and_stream` accepts optional `memoir: Memoir | None = None` and `scene_id: str | None = None` keyword args; writes one entry on success
- `tests/unit/test_cli.py` — extend `TestSendAndStream` with two new tests for the Memoir integration
- `hosts/cli/__main__.py` — when `ForgeSession.start()` succeeds, also instantiate `Memoir(forge_session.workdir)` and a per-session turn counter; pass both to `send_and_stream`

---

## Task 1: Add the pure helper functions

**Files:**

- Create: `tests/unit/test_host_helpers.py`
- Create: `shared/src/kourai_common/federation/host_helpers.py`

`derive_scene_id` formats a stable identifier given a session id and a turn number. `build_pipeline_turn_entry` constructs a `MemoirEntry` from CLI-side data — pure, no I/O, fully testable.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_host_helpers.py`:

```python
"""Pure helpers used by hosts to construct MemoirEntries for the FL pipeline."""

from __future__ import annotations

import pytest

from kourai_common.federation.host_helpers import (
    build_pipeline_turn_entry,
    derive_scene_id,
)
from kourai_common.federation.memoir_schema import EntrySource


class TestDeriveSceneId:
    """`session-<short-id>.turn-<n>` is the canonical format."""

    def test_uses_first_eight_chars_of_session_id(self):
        sid = derive_scene_id("abcdef0123456789", turn_number=1)
        assert sid == "session-abcdef01.turn-1"

    def test_zero_turn_is_valid(self):
        # Some hosts may want to write a session-open marker entry.
        sid = derive_scene_id("abcdef01", turn_number=0)
        assert sid == "session-abcdef01.turn-0"

    def test_negative_turn_rejected(self):
        with pytest.raises(ValueError, match="turn_number must be"):
            derive_scene_id("abcdef01", turn_number=-1)

    def test_empty_session_id_rejected(self):
        with pytest.raises(ValueError, match="session_id must be"):
            derive_scene_id("", turn_number=1)


class TestBuildPipelineTurnEntry:
    """Constructs a SPECIALIST_PROPOSED MemoirEntry from CLI-side data."""

    def test_minimal_inputs_produces_shared_eligible_entry(self):
        entry = build_pipeline_turn_entry(
            scene_id="session-abc.turn-1",
            agent="kallos",
            agent_proposed="lint suggestion text",
        )
        assert entry.scene_id == "session-abc.turn-1"
        assert entry.agent == "kallos"
        assert entry.source is EntrySource.SPECIALIST_PROPOSED
        assert entry.agent_proposed == "lint suggestion text"
        assert entry.split.shared_eligible is True

    def test_unknown_agent_rejected(self):
        with pytest.raises(ValueError, match="unknown agent"):
            build_pipeline_turn_entry(
                scene_id="session-abc.turn-1",
                agent="nobody",
                agent_proposed="x",
            )

    def test_empty_agent_proposed_rejected(self):
        with pytest.raises(ValueError, match="agent_proposed must be"):
            build_pipeline_turn_entry(
                scene_id="session-abc.turn-1",
                agent="kallos",
                agent_proposed="",
            )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_host_helpers.py -v`
Expected: collection error with `ModuleNotFoundError: No module named 'kourai_common.federation.host_helpers'`

- [ ] **Step 3: Implement the helpers**

Create `shared/src/kourai_common/federation/host_helpers.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_host_helpers.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_host_helpers.py shared/src/kourai_common/federation/host_helpers.py
git commit -m "feat(memoir): add host_helpers for scene-id derivation and entry construction"
```

---

## Task 2: Wire `send_and_stream` to optionally write a Memoir entry

**Files:**

- Modify: `hosts/cli/streaming.py`
- Modify: `tests/unit/test_cli.py`

`send_and_stream` gains two new keyword arguments — `memoir: Memoir | None = None` and `scene_id: str | None = None`. When both are provided AND the run produced non-empty `final_text` AND `get_last_seen_agent()` returned a known agent, build and append one entry. Failure to write an entry must NOT cause the function to fail — log and continue, since the pipeline already succeeded for the user.

- [ ] **Step 1: Add the failing tests for Memoir integration**

In `tests/unit/test_cli.py`, locate the `TestSendAndStream` class. Append two new test methods to it (after the existing tests):

```python
    @pytest.mark.asyncio
    async def test_writes_memoir_entry_on_success(self, monkeypatch, tmp_path):
        from kourai_common.federation.memoir import Memoir
        from kourai_common.federation.memoir_schema import EntrySource

        # Pretend Kallos was the last agent seen during the run.
        monkeypatch.setattr(
            "hosts.cli.streaming.get_last_seen_agent",
            lambda: "kallos",
        )

        client = MagicMock()
        task = _make_task(TaskState.completed)
        artifact_event = MagicMock(spec=TaskArtifactUpdateEvent)
        # Patch artifact extraction to return a deterministic string.
        monkeypatch.setattr(
            "hosts.cli.streaming._extract_artifact_text",
            lambda _: "final lint suggestion",
        )

        async def _events():
            yield (task, artifact_event)
            yield (task, None)

        client.send_message = MagicMock(return_value=_events())

        memoir = Memoir(tmp_path)
        await send_and_stream(
            client,
            "hello",
            "ctx-1",
            memoir=memoir,
            scene_id="session-abc12345.turn-1",
        )

        entries = list(memoir.entries())
        assert len(entries) == 1
        entry = entries[0]
        assert entry.scene_id == "session-abc12345.turn-1"
        assert entry.agent == "kallos"
        assert entry.source is EntrySource.SPECIALIST_PROPOSED
        assert entry.agent_proposed == "final lint suggestion"

    @pytest.mark.asyncio
    async def test_no_memoir_entry_when_memoir_none(self, monkeypatch, tmp_path):
        # Sanity: backward-compatible default — no Memoir kwarg, no write.
        from kourai_common.federation.memoir import Memoir

        monkeypatch.setattr(
            "hosts.cli.streaming.get_last_seen_agent",
            lambda: "kallos",
        )
        monkeypatch.setattr(
            "hosts.cli.streaming._extract_artifact_text",
            lambda _: "final text",
        )

        client = MagicMock()
        task = _make_task(TaskState.completed)
        artifact_event = MagicMock(spec=TaskArtifactUpdateEvent)

        async def _events():
            yield (task, artifact_event)
            yield (task, None)

        client.send_message = MagicMock(return_value=_events())

        await send_and_stream(client, "hello", "ctx-1")
        # No exception, no Memoir written — there isn't one to check.
        # Verify by creating a Memoir at tmp_path and confirming its file
        # does not exist (proxy: nothing wrote to that directory).
        memoir = Memoir(tmp_path)
        assert not memoir.path.exists()
```

If `TaskArtifactUpdateEvent` is not already imported in this test file, add it from `a2a.types` alongside whatever is already imported there.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/test_cli.py::TestSendAndStream::test_writes_memoir_entry_on_success tests/unit/test_cli.py::TestSendAndStream::test_no_memoir_entry_when_memoir_none -v`
Expected: 2 failures with `TypeError: send_and_stream() got an unexpected keyword argument 'memoir'`

- [ ] **Step 3: Update `send_and_stream` signature and add the write block**

Edit `hosts/cli/streaming.py`. Add this import alongside the existing imports (top of file, after the `httpx` import):

```python
from kourai_common.federation.host_helpers import build_pipeline_turn_entry
```

And add this typing-only import inside the existing `if TYPE_CHECKING:` block:

```python
    from kourai_common.federation.memoir import Memoir
```

Then update the `send_and_stream` function signature. It currently reads:

```python
async def send_and_stream(
    client: Client,
    user_text: str,
    context_id: str,
    task_id: str | None = None,
    verbose: bool = False,
    attachments: list[tuple[str, str]] | None = None,
    tts: TTSEngine | None = None,
    gossip_enabled: bool = True,
) -> tuple[bool, str, str | None]:
```

Add two new keyword-only arguments after `gossip_enabled`:

```python
async def send_and_stream(
    client: Client,
    user_text: str,
    context_id: str,
    task_id: str | None = None,
    verbose: bool = False,
    attachments: list[tuple[str, str]] | None = None,
    tts: TTSEngine | None = None,
    gossip_enabled: bool = True,
    *,
    memoir: Memoir | None = None,
    scene_id: str | None = None,
) -> tuple[bool, str, str | None]:
```

Now find the block where `final_text` is rendered (it starts with `if final_text:` near the end of the success path). After that block writes its output but BEFORE the elapsed-time print, insert this Memoir-write block:

```python
        # Write a Memoir entry capturing this turn for FL training data.
        if memoir is not None and scene_id is not None:
            last_agent = get_last_seen_agent()
            if last_agent:
                try:
                    entry = build_pipeline_turn_entry(
                        scene_id=scene_id,
                        agent=last_agent,
                        agent_proposed=final_text,
                    )
                    memoir.append(entry)
                except (ValueError, OSError) as e:
                    # Memoir failures must not break the user's pipeline.
                    # Log at debug; the user already saw their result.
                    import logging

                    logging.getLogger("cli.streaming").debug(
                        "Memoir append skipped: %s", e
                    )
```

Place this AFTER the `_render_markdown(final_text)` and the elapsed-time `_echo`, and BEFORE the victory chatter block — so a write failure can't suppress the user's victory line.

Recursive `send_and_stream` calls (for `input_required` follow-up) should NOT write a Memoir entry for the follow-up turn — only the originating call writes one. Since the recursive call doesn't pass `memoir=`/`scene_id=`, this is automatic.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_cli.py::TestSendAndStream -v`
Expected: All TestSendAndStream tests pass — the prior 5 + the 2 new ones.

- [ ] **Step 5: Commit**

```bash
git add hosts/cli/streaming.py tests/unit/test_cli.py
git commit -m "feat(cli): write Memoir entry per pipeline run when memoir+scene_id passed"
```

---

## Task 3: Wire the CLI main loop to construct a Memoir per ForgeSession

**Files:**

- Modify: `hosts/cli/__main__.py`

When a `ForgeSession.start()` succeeds, instantiate a `Memoir(forge_session.workdir)` and a `turn_number` counter starting at 1. On every subsequent `send_and_stream` call within that session, pass `memoir=` and a `scene_id=` derived from `forge_session.session_id` and the current `turn_number`, then increment.

The existing forge-session lifecycle in `hosts/cli/__main__.py` lives around lines 553-585. Find that block — it starts with `forge_session: ForgeSession | None = None`. The existing code starts a session if the prompt isn't a slash command.

- [ ] **Step 1: Read the current forge_session handling**

Run: `grep -n "ForgeSession\|forge_session" hosts/cli/__main__.py | head -20`
Expected output: lines around 47 (import), 553+ (lifecycle).

Read lines 540-600 of `hosts/cli/__main__.py` to confirm where `send_and_stream` is called within the loop. The exact form may have evolved; the plan adapts.

- [ ] **Step 2: Add the imports**

At the top of `hosts/cli/__main__.py`, alongside the existing `from kourai_common.forge_session import ForgeSession, ForgeSessionError`, add:

```python
from kourai_common.federation.host_helpers import derive_scene_id
from kourai_common.federation.memoir import Memoir
```

- [ ] **Step 3: Add per-session Memoir + turn counter**

Locate the line `forge_session: ForgeSession | None = None`. Immediately below it add:

```python
                forge_memoir: Memoir | None = None
                forge_turn_number: int = 0
```

Find the block where `forge_session = ForgeSession.start(...)` is called on a successful start. Right after the line that assigns `forge_session`, add:

```python
                        forge_memoir = Memoir(forge_session.workdir)
                        forge_turn_number = 0
```

This runs once per session start; the worktree directory is guaranteed to exist by the `ForgeSession.start` contract.

- [ ] **Step 4: Pass memoir + scene_id to `send_and_stream` and increment turn**

Find where `await send_and_stream(client, prompt_text or forge_msg, ...)` is called inside the loop. The exact form depends on the current `__main__.py` shape — search for `send_and_stream(client,` with grep. The simplest correct pattern: just before the call, build the kwargs:

```python
                stream_kwargs: dict[str, object] = {}
                if forge_session is not None and forge_memoir is not None:
                    forge_turn_number += 1
                    stream_kwargs["memoir"] = forge_memoir
                    stream_kwargs["scene_id"] = derive_scene_id(
                        forge_session.session_id,
                        turn_number=forge_turn_number,
                    )
```

Then add `**stream_kwargs` to the existing `send_and_stream` call's keyword arguments (keep all the existing args).

If a `/project accept` or `/project discard` later resolves the session, the existing code path likely sets `forge_session = None`. Mirror that for `forge_memoir`:

```python
# Wherever forge_session is reset to None, also reset:
forge_memoir = None
forge_turn_number = 0
```

Search for `forge_session = None` and add the matching resets adjacent to each.

- [ ] **Step 5: Run the existing CLI test suite to confirm no regression**

Run: `uv run pytest tests/unit/test_cli.py -v`
Expected: All TestSendAndStream tests still pass; TestMainCommand tests still pass (they don't exercise the new Memoir path because they don't start a ForgeSession).

- [ ] **Step 6: Commit**

```bash
git add hosts/cli/__main__.py
git commit -m "feat(cli): instantiate Memoir per ForgeSession and thread through pipeline"
```

---

## Task 4: Integration test — full session writes and replays entries

**Files:**

- Create: `tests/unit/test_cli_memoir_integration.py`

A higher-level test that drives `send_and_stream` twice within one fake session and confirms two ordered entries land in the Memoir on disk.

- [ ] **Step 1: Write the integration test**

Create `tests/unit/test_cli_memoir_integration.py`:

```python
"""Integration: CLI streaming writes ordered Memoir entries to a session workdir."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from a2a.types import TaskArtifactUpdateEvent, TaskState

from hosts.cli.streaming import send_and_stream
from kourai_common.federation.host_helpers import derive_scene_id
from kourai_common.federation.memoir import Memoir


def _make_completed_task() -> MagicMock:
    task = MagicMock()
    task.id = "task-1"
    task.context_id = "ctx-1"
    task.status.state = TaskState.completed
    return task


@pytest.mark.asyncio
async def test_two_turns_produce_two_ordered_entries(monkeypatch, tmp_path):
    """A session that runs twice writes two MemoirEntries in turn order."""

    monkeypatch.setattr(
        "hosts.cli.streaming.get_last_seen_agent",
        lambda: "techne",
    )

    artifact_texts = iter(["first artifact", "second artifact"])
    monkeypatch.setattr(
        "hosts.cli.streaming._extract_artifact_text",
        lambda _: next(artifact_texts),
    )

    memoir = Memoir(tmp_path)
    session_id = "deadbeef0000ffff"

    for turn in (1, 2):
        client = MagicMock()
        task = _make_completed_task()
        artifact_event = MagicMock(spec=TaskArtifactUpdateEvent)

        async def _events():
            yield (task, artifact_event)
            yield (task, None)

        client.send_message = MagicMock(return_value=_events())

        await send_and_stream(
            client,
            f"prompt-{turn}",
            "ctx-1",
            memoir=memoir,
            scene_id=derive_scene_id(session_id, turn_number=turn),
        )

    entries = list(memoir.entries())
    assert len(entries) == 2
    assert entries[0].scene_id == "session-deadbeef.turn-1"
    assert entries[0].agent_proposed == "first artifact"
    assert entries[1].scene_id == "session-deadbeef.turn-2"
    assert entries[1].agent_proposed == "second artifact"


@pytest.mark.asyncio
async def test_unknown_agent_does_not_break_pipeline(monkeypatch, tmp_path):
    """If get_last_seen_agent returns something not in ALL_AGENTS, the pipeline
    still completes successfully; the entry is silently skipped."""

    monkeypatch.setattr(
        "hosts.cli.streaming.get_last_seen_agent",
        lambda: "nobody",  # not a known maiden
    )
    monkeypatch.setattr(
        "hosts.cli.streaming._extract_artifact_text",
        lambda _: "some artifact",
    )

    client = MagicMock()
    task = _make_completed_task()
    artifact_event = MagicMock(spec=TaskArtifactUpdateEvent)

    async def _events():
        yield (task, artifact_event)
        yield (task, None)

    client.send_message = MagicMock(return_value=_events())

    memoir = Memoir(tmp_path)
    cont, ctx, tid = await send_and_stream(
        client,
        "prompt",
        "ctx-1",
        memoir=memoir,
        scene_id="session-deadbeef.turn-1",
    )

    # Pipeline must still report success.
    assert cont is True
    # No entry written because the agent is unknown.
    assert list(memoir.entries()) == []
```

- [ ] **Step 2: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_cli_memoir_integration.py -v`
Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_cli_memoir_integration.py
git commit -m "test(cli): integration test — session writes ordered Memoir entries"
```

---

## Task 5: Final verification gate

**Files:** Possibly none modified, depending on lint findings.

- [ ] **Step 1: Run the full unit suite**

Run: `uv run pytest tests/unit -q --no-header --tb=no`
Expected: 1267 + 9 (Task 1's 7 + Task 4's 2) = 1276+ passed (Task 2's 2 are inside `TestSendAndStream` so already counted in the prior baseline-ish number). Pre-existing failures unchanged (the same 10 + 4 collection errors as plan-01 saw). No new failures in the federation/, hosts/cli/, or test_cli paths from this branch.

- [ ] **Step 2: Run ruff format AND ruff check**

Run: `uv run ruff format --check . 2>&1 | tail -3`
Expected: `N files already formatted` — no `Would reformat:` lines for this branch's files.

If ruff format wants changes:

```bash
uv run ruff format shared/src/kourai_common/federation/host_helpers.py tests/unit/test_host_helpers.py tests/unit/test_cli.py tests/unit/test_cli_memoir_integration.py hosts/cli/streaming.py hosts/cli/__main__.py
```

Then:

Run: `uv run ruff check shared/src/kourai_common/federation/ tests/unit/test_host_helpers.py tests/unit/test_cli_memoir_integration.py hosts/cli/streaming.py hosts/cli/__main__.py`
Expected: `All checks passed!`

- [ ] **Step 3: Run ty over the changed source paths**

Run: `uv run ty check shared/src/kourai_common/federation/ hosts/cli/streaming.py`
Expected: no diagnostics.

- [ ] **Step 4: Confirm public surface still imports**

Run: `uv run python -c "from kourai_common.federation.host_helpers import build_pipeline_turn_entry, derive_scene_id; from hosts.cli.streaming import send_and_stream; print('ok')"`
Expected: `ok`.

- [ ] **Step 5: Commit any format/lint cleanup**

If you ran `ruff format` and it changed files:

```bash
git add -u
git commit -m "style(memoir): apply ruff format to plan-02 CLI integration files"
```

Otherwise no commit needed.

---

## What this plan ships

- `kourai_common.federation.host_helpers` — `derive_scene_id`, `build_pipeline_turn_entry`
- `hosts.cli.streaming.send_and_stream` accepts `memoir=` and `scene_id=` keyword args; writes one `SPECIALIST_PROPOSED` entry per successful pipeline run
- `hosts/cli/__main__.py` instantiates a `Memoir` per `ForgeSession` and threads turn numbers through
- 9 new unit tests (7 for helpers + 2 for streaming) plus 2 integration tests
- Backward-compatible signature: callers that don't pass `memoir=` see no change in behavior

## What's deferred to follow-up plans

- plan-03 — GUI host integration (same shape, different host)
- plan-04 — VN host integration (Sovereignty Moment as the first scene)
- plan-05 — `kourai-dev memoir` inspection / replay tooling + `/project accept` / `/project discard` writing PLAYER_REVISION entries
- plan-06 — interrupt entry shape and the concurrent interrupt channel (per-agent-turn granularity)
- plan-07 — bond adapter scaffolding and local trainer (consumes the Memoir produced by these host plans)
- later — vFL LoRA-FAIR strategy, federation client, DP, Council scenes, Byzantine simulation, online preference learning ablation, evaluation pipeline

Each follow-up plan stands alone and depends only on prior plans in the chain.
