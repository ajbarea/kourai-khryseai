# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **`/compact` slash command** (tier-1
lift from the OSS-CC research sweep — universal pattern across every
serious Claude Code clone, we didn't have it)

---

## Plan-of-record

End state: the player can type `/compact` mid-session and have Mneme
fold older turns into long-term memory across every agent in the
current `context_id`, freeing the working window without losing the
thread. The auto-compaction logic in `_manage_memory` already handled
the heavy lifting (LLM summarization + state persistence) — it just
gated on `len(unsummarized) > WORKING_MEMORY_LIMIT`. Player-triggered
compaction needed (a) a force-flag to bypass that threshold, (b) a
way to discover which agents have history under the current context,
(c) a CLI dispatch + Mneme comms-window emit.

### Change 1 — `list_agents_with_history` memory primitive ✅ 2026-04-26

- [x] `shared/src/kourai_common/memory.py`: new function returning
      distinct `agent_name` values with any messages stored against a
      `context_id`. Sorted alphabetically for deterministic /compact
      roster ordering. 4 unit tests in `test_memory.py`.

### Change 2 — `_manage_memory` force-flag + `compact_memory` wrapper ✅ 2026-04-26

- [x] `shared/src/kourai_common/llm.py::_manage_memory(... , *, force=False)`:
      new keyword. When `force=True` bypass the
      `len(unsummarized) > WORKING_MEMORY_LIMIT` gate. Still keep the
      "last 2 unsummarized for immediate context fluidity" rule and
      no-op when there aren't enough messages to fold (≤2). Now
      returns `int` (count of messages folded) so callers can report.
- [x] `shared/src/kourai_common/llm.py::compact_memory(context_id, agent_name)`:
      thin public wrapper that always passes `force=True`. Used by
      the CLI handler to keep concerns separate (auto-compaction stays
      private with its threshold gate; player-triggered work has a
      named entry point).
- [x] 3 new unit tests in `test_llm.py::TestManageMemory`: force
      bypasses threshold, no-op on too-few-messages, wrapper forces.

### Change 3 — `/compact` slash command ✅ 2026-04-26

- [x] `hosts/cli/completer.py`: new `SlashCommand("compact", ...)`
      entry between `/yolo` and `/metrics`.
- [x] `hosts/cli/__main__.py::_compact_session_memory(context_id)`:
      iterates `list_agents_with_history`, awaits `compact_memory`
      for each, totals counts, emits a Mneme comms-window narrating
      what happened. M10 speech convention: dialogue body wrapped in
      `"..."` so `_comms_window` flips italic. Three states:
      empty thread (`"Nothing to chronicle yet — the thread is still
      fresh."`), nothing-to-fold (`"The recent turns are already lean
      — nothing to fold yet."`), or success (`"I tucked N turns
      into long-term memory — agent (count), …. The thread is lighter
      now."`).
- [x] REPL handler at `__main__.py` calls
      `_compact_session_memory(context_id)` on `prompt_text == "/compact"`.
- [x] Hoisted `compact_memory` and `list_agents_with_history` to
      module-level imports so the function is properly mockable in
      tests via `hosts.cli.__main__.<name>`.

### Tests ✅ 2026-04-26

- [x] `tests/unit/test_memory.py::TestListAgentsWithHistory` — 4
      tests including a "doesn't leak across contexts" guard.
- [x] `tests/unit/test_llm.py::TestManageMemory` — 3 new tests
      bringing the class to 6 (3 pre-existing + 3 new).
- [x] `tests/unit/test_cli.py::TestCompactSessionMemory` — 3 tests:
      empty-agents path, full iterate-and-total path with order
      preserved, zero-total "already lean" path.
- [x] All 90 tests across the three affected files pass in ~3 s.

### Live smoke (folds into next interactive `/project` session)

- [ ] Run a few exchanges with the agents, then type `/compact`.
      Confirm the Mneme comms-window appears with a count and
      roster of agents whose buckets were folded.
- [ ] Send another message after `/compact` — confirm the agent
      replies referencing prior context (proving the semantic
      summary survived).

---

## Notes / open questions

- **Why a public `compact_memory` wrapper instead of just exposing
  `_manage_memory`?** Two reasons. (1) The auto-compaction call inside
  `chat()`/`chat_with_tools()` keeps its threshold gate semantics
  clearly; the player-triggered call gets a named entry point so a
  future reader doesn't have to read the `force=True` site to know
  what's happening. (2) Refactoring later (e.g., to use a cheaper
  model for player-triggered compaction, or to attach a different
  prompt) is a one-place change in the wrapper, not a kwarg cascade
  through `_manage_memory`.

- **Why per-agent compaction rather than a single conversation-wide
  rollup?** Each agent maintains its own `semantic_summary` because
  the summarization is voiced from that agent's perspective and
  prefixed back into that agent's prompts. Folding across agents
  would lose the per-voice framing. The roster Mneme reports lets
  the player see which agents had enough history to compact.

- **What this lift does NOT do.** It doesn't add a `<COMPACTED>`
  block format the way I sketched in ROADMAP — that turned out to
  be over-design. The existing summarization prompt already
  produces a structured-enough summary; wrapping it in a block-tag
  was solution looking for a problem. If a future need surfaces
  (e.g., the LLM needs structural cues about what's a summary vs
  raw history), that's a separate prompt-engineering PR.

- **Pairs with M4.** Compacted prompts are smaller, so the system
  block + first user message stays under the 2048/4096-token cache
  threshold for longer. M4's within-loop caching benefits directly.

---

## Up next (queued, not yet active — tier order from #37 prioritization)

- **MCP `roots` + `elicitation` declared at M2 init** — design-time
  work for when M2 (`kourai-forge-mcp`) is being scaffolded. Cheap
  if done at design time, expensive retrofit later.
- **`/permissions` granular tool gating** — small extension to
  `CLISettings.auto_approve: dict[str, bool]` keyed on tool name.
  Maps onto the existing `MUTATING_TOOL_NAMES` frozenset.
- **`A2A-Version` header** — one-line prerequisite for any v1.0
  migration attempt.
- **`/cost` alias for `/usage`** — five-line cleanup matching OSS-CC
  vocabulary so muscle-memory carries over.
- **T8 follow-up** (ParallelContext shared buffer feeding Metis's
  partial output back into the classifier prompt). Substantial
  async work.
- **T4 follow-up from M13** (`[forge_intent]` block on user message
  to specialists). Needs SQL migration or in-memory plumbing.
- **M2** (`kourai-forge-mcp` server) — real architectural milestone.
- **M15** (forge logging architecture) — operational hygiene.
- **M5** (UID alignment for forge worktrees) — quality-of-life.
- **M7** (a2a-sdk 1.0.x migration) — properly scoped.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor.
