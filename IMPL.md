# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **Round 6 bullet 5 — final** (git
context discovery for specialist agents in worktree; closes the last
of the 5 M6-future bullets AJ flagged from live smoke)

---

## Plan-of-record

End state: `git status --short` no longer exits 128 from inside the
Metis and Techne specialist containers. The bug was simple: the
container's default cwd is `/app`, not the worktree, so git had no
repo to look at. The `[project_root: ...]` tag was already in the
user message; the executors just weren't threading it through to the
git-context helpers.

The ROADMAP suggested option (c) — auto-prepend `cd <project_root> && `
in the bash helper — but the cleaner fix is at the call site where
`project_root` is already in scope as a parsed `Path`. Just pass it
as `cwd` to the helper that already accepts it.

### Change 1 — Techne executor threads project_root → get_git_context cwd ✅ 2026-04-26

- [x] `agents/techne/agent_executor.py:103`: `get_git_context(...)`
      now receives `cwd=str(project_root)`. `project_root` was
      already parsed at line 56 via `parse_project_root(user_input)`
      — pure threading change.

### Change 2 — Metis executor parses + threads project_root → get_project_context ✅ 2026-04-26

- [x] `agents/metis/agent_executor.py`: import `parse_project_root`
      alongside the existing `extract_image_parts`. Parse
      `project_root` from `user_input` immediately after
      `context.get_user_input()`. Pass `project_root=str(project_root)`
      to `get_project_context(...)` (the function already accepts
      it; the executor just wasn't passing it).
- [x] `parse_project_root` falls back to `Path.cwd()` when the tag
      is missing (internal/test invocations), so existing test
      fixtures aren't disturbed.

### Tests ✅ 2026-04-26

- [x] `tests/unit/test_executors.py::TestTechneExecutor::test_get_git_context_called_with_project_root_cwd`:
      asserts `get_git_context` is called with a non-None `cwd`
      kwarg when the user message carries `[project_root: …]`.
- [x] `tests/unit/test_executors.py::TestMetisExecutor::test_get_project_context_called_with_project_root`:
      same shape, asserts `get_project_context` receives
      `project_root=`.
- [x] All 24 executor unit tests pass (22 pre-existing + 2 new) in
      ~4 s. No regressions.

### Live smoke (folds into next interactive `/project` session)

- [ ] Send a Techne task → confirm the comms-window line shows
      `🔍 $ git status --short` followed by *content* (modified
      files) instead of `🔍 exit 128`.
- [ ] Same for Metis: `📐` panel should surface a real
      `Git status:` block in the project-context output rather than
      the empty fallback.

---

## Notes / open questions

- **Why this and not the ROADMAP's `cd <project_root> &&` prefix?**
  The prefix would have meant mutating the command string inside a
  bash-tool helper that doesn't currently exist as a shared
  abstraction (each agent calls `run_command` directly). Threading
  `cwd` through the helper signature that already supports it is
  one-line-per-call and surfaces the intent at the call site rather
  than hiding it behind a runner-level fallback. Same minimum
  scope, less indirection.

- **Why not also fix the Mneme/Kallos/Dokimasia executors?** Mneme
  doesn't run git itself (it consumes git output Hephaestus
  collects). Kallos and Dokimasia operate on file paths the player
  / Techne supplied — they don't need a repo-scoped cwd today. If
  that changes when M2 (`kourai-forge-mcp`) lands and tools become
  MCP-served, this'll need to be revisited; the new MCP `roots`
  primitive (see M2 section in ROADMAP) is the natural home for
  per-call worktree scoping.

- **All 5 Round 6 M6-future bullets are now closed.** The five-PR
  arc that started with #34 (read_file dir rejection + branch slug
  whitelist) and ends with this PR clears the slate of bugs AJ
  caught in the M1 Round 6 live smoke. The two big architectural
  pickups from the same session — M13 Forge Order Confirmation and
  M14 Metis-First Parallel Routing — both shipped earlier in the
  day. The next active work is whatever AJ picks from the queue
  below.

---

## Up next (queued, not yet active)

- **Tier-1 lifts from the OSS-CC research sweep** (#37, just landed):
  `/compact` slash command (universal across every clone, Mneme has
  the documenter persona ready), then MCP `roots` + `elicitation`
  declared at M2 init (cheap design-time work, expensive retrofit),
  then `/permissions` granular tool gating (small extension to
  `CLISettings`), then `A2A-Version` header (one-line prerequisite
  for any v1.0 attempt), then `/cost` alias (5-line cleanup).
- **T8 follow-up** (ParallelContext shared buffer feeding Metis's
  partial output back into the classifier prompt). Substantial
  async work.
- **T4 follow-up from M13** (`[forge_intent]` block on user message
  to specialists). Needs SQL migration or in-memory plumbing.
- **M2** (`kourai-forge-mcp` server) — real architectural milestone;
  carries the MCP `roots` / `elicitation` / `sampling` work as part
  of its scaffolding.
- **M15** (forge logging architecture) — operational hygiene; the
  three-layer-memory observation from the OSS-CC sweep is a useful
  framing for it.
- **M5** (UID alignment for forge worktrees) — quality-of-life.
- **M7** (a2a-sdk 1.0.x migration) — properly scoped now, with the
  `A2A-Version` header + AUTH_REQUIRED state + multi-stream-per-task
  notes from the spec sweep.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor.
