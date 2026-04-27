# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-27 · Working on: **CLI input_required follow-up
preserves forge tags** (Bug B from the 2026-04-27 smoke pass; stacked
on the gitdir/safe.directory infrastructure fix in #42)

---

## Plan-of-record

End state: every M13 `yes` confirmation, every mid-pipeline ASK_USER
reply, and every other `input_required` follow-up arrives at
specialists carrying the same `[project_root: ...]` / `[yolo: on]` /
`[auto_approve_reads: on]` text-tags as the original turn — so Metis's
`get_project_context` and Techne's `get_git_context` operate on the
correct worktree path instead of falling back to `Path.cwd()` = `/app`
inside the agent container.

The smoke that exposed the gitdir/UID bugs (#42) also revealed this —
when a player typed `yes` to a CONFIRM_ORDER read-back, the resumed
turn went straight through without the bracket-tags. Specialists then
ran `git status --short` from `/app` (not a git repo) → `exit 128` →
the pipeline gracefully fell back to file_contents only, masking the
loss of git context across every confirmation flow shipped to date.

### Change 1 — `send_and_stream` accepts `forge_tags` kwarg ✅ 2026-04-27

- [x] `hosts/cli/streaming.py::send_and_stream(...)` grew a
      `forge_tags: list[str] | None = None` keyword-only parameter.
- [x] The `input_required` recursive callback re-prepends the tags
      to the player's response before the inner `send_and_stream`
      call, and threads `forge_tags=forge_tags` through so subsequent
      follow-ups (multi-turn ASK_USER) keep them too.
- [x] Backward-compat preserved: when `forge_tags is None`, follow-up
      sends bare text — same shape every existing caller relied on.
- [x] `/q` quit short-circuits before the prepend, so the abort
      path doesn't accidentally send `[project_root: ...]\n/q`.

### Change 2 — `__main__.py` constructs the tag list ✅ 2026-04-27

- [x] Replaced the per-tag string-concatenation block (3 separate
      `forge_msg = f"...\n{forge_msg}"` rebuilds) with a single
      `forge_tags: list[str]` accumulator. Reads cleaner and gives us
      the list to pass through `send_and_stream(..., forge_tags=)`.
- [x] Final `forge_msg = "\n".join((*forge_tags, prompt_text))` only
      runs when there are tags — preserves the no-project bare-text
      shape.
- [x] `forge_tags or None` passed to `send_and_stream` so the kwarg
      carries `None` (not an empty list) when no tags exist —
      matches the function's documented default.

### Tests ✅ 2026-04-27

- [x] `tests/unit/test_cli.py::TestForgeTagsPropagation` — 3 tests:
      - `test_input_required_follow_up_re_prepends_tags`: assert both
        `[project_root: ...]` and `[yolo: on]` appear before the
        `yes` payload on the second `send_message` call.
      - `test_no_tags_keeps_follow_up_bare`: backward-compat — when
        forge_tags is None, follow-up text is the bare user input.
      - `test_quit_response_does_not_recurse`: `/q` aborts cleanly
        without sending the tags + `/q` payload.
- [x] All 32 tests in `test_cli.py` green; no regressions in
      `TestSendAndStream` (existing 7 tests), `TestCompactSessionMemory`,
      `TestForgeTagsPropagation`, `TestGreetingFormat`, etc.

### Live smoke (folds into next interactive `/project` session)

- [ ] Send a real Techne task via `make cli` against `smoke-2026-04-27`
      project. After CONFIRM_ORDER fires, confirm with `yes`.
- [ ] Verify Metis's `🔍 $ git status --short` line is followed by
      modified-file content (or empty status), NOT `🔍 exit 128`.
      This requires #42 to have merged so the gitdir resolves AND
      this PR so the project_root tag survives the confirmation.
- [ ] Toggle `/yolo` on, send a task, watch the comms-window for
      Hephaestus's "Let me get to it" handoff (no CONFIRM_ORDER) —
      validate the yolo tag survives if a future turn also goes
      input_required (e.g., a specialist mid-pipeline ASK_USER).

---

## Notes / open questions

- **Why not move to `Message.metadata` now?** A2A v1.0 spec makes
  `Message.metadata` the canonical channel for exactly these tags
  ("a flexible key-value map for passing additional context or
  parameters with operations" — propagates with messages, grouped by
  contextId across multi-turn). But we're pinned to a2a-sdk `<1.0`
  until M7 lands — 0.3.x's metadata propagation isn't reliable
  enough to retire the text-tag carrier today (per existing docstring
  in `extract_project_root`). Added a M7-scope item to do the
  migration cleanly when the SDK flips.

- **Why a list of tags rather than a dict / dataclass?** Tags are
  ordered by precedence today (yolo wins over auto_approve_reads,
  both prepend before project_root). The list preserves the order
  the existing code already produces. A dataclass would force
  call-sites to reason about precedence. List + `\n.join` is the
  smallest cognitive footprint that ships value.

- **Why not lift the input_required loop out of streaming.py
  entirely?** That's a bigger refactor — would require the REPL's
  outer loop to reason about session continuity (don't call
  `ForgeSession.start` again on a follow-up, reuse the existing
  one). Today every REPL turn calls `ForgeSession.start`
  unconditionally. The recursive-loop architecture sidesteps that
  by never returning to the outer loop on input_required, so the
  forge session implicitly stays the same. Refactoring would touch
  ForgeSession state management and isn't justified by this bug's
  scope. Surgical kwarg fix > architectural rework.

- **What this lift does NOT do.** It doesn't migrate to
  `Message.metadata` (M7 scope). It doesn't lift the loop into the
  REPL (out of scope). It doesn't add a way to override tags
  per-follow-up (e.g., player toggling `/yolo` mid-confirmation
  doesn't propagate — they'd need to exit to the REPL outer loop,
  toggle, then resend). All deferred.

---

## Up next (queued, not yet active)

- **MCP `roots` + `elicitation` declared at M2 init** — design-time
  work for when M2 (`kourai-forge-mcp`) is being scaffolded.
- **M2** (`kourai-forge-mcp` server) — real architectural milestone;
  unblocked since M1 done.
- **Plan Mode toggle (Cline-style)** — persistent planning mode
  where Hephaestus loops on M14 parallel routing every turn but
  never dispatches until the player explicitly types `/plan
  execute`.
- **Background memory consolidation (Mneme "autoDream")** —
  ClawCode pattern; pairs nicely with the just-shipped `/compact`.
- **Custom-agent-via-markdown registration (OpenCode-style)** —
  long-term direction; touches A2A registration, MCP toolkit,
  routing prompt — wait until M2 lands.
- **T8 follow-up** (ParallelContext shared buffer feeding Metis's
  partial output back into the classifier prompt). Substantial
  async work.
- **T4 follow-up from M13** (`[forge_intent]` block on user message
  to specialists). Needs SQL migration or in-memory plumbing.
- **M15** (forge logging architecture) — operational hygiene; the
  three-layer-memory observation from the OSS-CC sweep is a useful
  framing for it.
- **M5** (UID alignment for forge worktrees) — quality-of-life;
  would let us drop the `safe.directory '*'` workaround from #42.
- **M7** (a2a-sdk 1.0.x migration) — properly scoped now, with the
  Message.metadata migration item added 2026-04-27 as part of the
  scope. Would let us delete the text-tag carrier entirely.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor.
