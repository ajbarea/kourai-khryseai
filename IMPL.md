# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **`/permissions` slash command**
(tier-2 lift from the OSS-CC research sweep — granular middle ground
between full `/yolo` and the always-on confirmation gate)

---

## Plan-of-record

End state: a player can opt into "skip the gate when nothing's about
to write to disk" without taking the full `/yolo` blast radius. Today
`/yolo` is binary — either every CONFIRM_ORDER is bypassed or every
pipeline goes through it. The lift adds one new policy
(`auto_approve_reads`) and a unified `/permissions` command for
inspecting and toggling all gating policies side-by-side.

The mechanism mirrors `/yolo` end-to-end so future per-tool gates can
land along the same path without re-litigating transport choices:

1. **CLI persistence** — `CLISettings.auto_approve_reads: bool = False`.
2. **CLI → Hephaestus transport** — text-tag `[auto_approve_reads: on]`
   prepended to outbound messages (A2A `Message.metadata` isn't
   transport-guaranteed; same convention as `[yolo: on]` and
   `[project_root: …]`).
3. **Hephaestus extracts + augments prompt** — new
   `extract_auto_approve_reads(text)` parallel to `extract_yolo`.
   System-prompt augmentation tells the LLM to skip CONFIRM_ORDER
   ONLY when the planned pipeline contains none of {techne, kallos,
   dokimasia} — those three are the agents whose tools live in
   `MUTATING_TOOL_NAMES`.
4. **Unified `/permissions` UI** — bare `/permissions` lists every
   gate with state + effect; `/permissions <name>` toggles. Aliases
   `yolo` and `reads` keep typing short.

### Change 1 — `CLISettings.auto_approve_reads` field ✅ 2026-04-26

- [x] Default `False` so existing players see no behaviour change.
- [x] Persists through `CLISettings.load()/save()` like every other
      bool field. Forward-compat fallback already in place from M13.

### Change 2 — `extract_auto_approve_reads` + system-prompt augment ✅ 2026-04-26

- [x] `agents/hephaestus/agent.py::extract_auto_approve_reads` —
      regex strip + bool, mirrors `extract_yolo`.
- [x] `determine_pipeline` parses both flags. `if yolo` augments
      the prompt with the YOLO MODE block as before; `elif
      auto_approve_reads` augments with the AUTO_APPROVE_READS
      block. The `elif` is intentional — `/yolo` wins when both are
      set since it's the broader bypass.
- [x] AUTO_APPROVE_READS prompt block explicitly names {techne,
      kallos, dokimasia} as the agents that still require
      CONFIRM_ORDER, so the LLM doesn't widen the bypass to write
      paths.

### Change 3 — CLI text-tag prepend + `/permissions` handler ✅ 2026-04-26

- [x] `hosts/cli/__main__.py` text-tag prepend — same site as
      `[yolo: on]`, with the `elif` guard so `/yolo` wins.
- [x] `_handle_permissions_command(prompt_text, settings)` —
      bare lists all gates with state + descriptions; argument
      toggles the named gate and persists.
- [x] `_PERMISSIONS_GATES` dict makes new gates a one-line
      addition (field name → off/on description tuple).
- [x] `_PERMISSIONS_ALIASES` keeps user-facing names short
      (`yolo`, `reads`) while accepting the long forms for
      muscle-memory.

### Change 4 — `/permissions` slash-command registration ✅ 2026-04-26

- [x] `hosts/cli/completer.py`: new `SlashCommand("permissions",
      …, arg_hint="[yolo|reads]")` between `/compact` and
      `/metrics`.

### Tests ✅ 2026-04-26

- [x] `tests/unit/test_confirmation_protocol.py::TestAutoApproveReadsBypass`
      — 6 tests: extract strips tag, case-insensitive,
      absent-returns-false, doesn't-match-substring, prompt
      augmentation names the three mutating agents, `/yolo` wins
      when both flags are set.
- [x] `tests/unit/test_confirmation_protocol.py::TestCLISettingsAutoApproveReadsField`
      — 2 tests: default-off, toggle-persists.
- [x] `tests/unit/test_confirmation_protocol.py::TestPermissionsCommand`
      — 4 tests: bare lists all gates, named toggle persists,
      unknown gate prints help, `yolo` alias maps to existing
      `yolo_enabled` field.
- [x] All 33 tests in `test_confirmation_protocol.py` green; full
      `test_cli.py` + `test_hephaestus.py` suite (78 tests) green.

### Live smoke (folds into next interactive `/project` session)

- [ ] `/permissions` → confirm both gates listed with current state.
- [ ] `/permissions reads` → confirm toggle + persist message.
- [ ] Send "summarize the project structure" (Metis-only route) →
      confirm pipeline runs without CONFIRM_ORDER.
- [ ] Send "add a function to foo.py" (Techne in route) → confirm
      CONFIRM_ORDER still appears (the bypass should NOT widen).

---

## Notes / open questions

- **Why `elif` instead of treating both flags additively?** `/yolo`
  is the broader bypass — when both are on, the player has clearly
  opted into max-autonomy mode and the narrower `auto_approve_reads`
  augmentation would just add noise to the prompt. The `elif` keeps
  the system-prompt clean and the precedence semantics legible.

- **Why text-tag transport again rather than `Message.metadata`?**
  Same answer as `[yolo: on]` and `[project_root: …]` from M13:
  `a2a-sdk` 0.3.x doesn't guarantee metadata propagation across
  every transport. Inlining the flag survives every code path.
  When we eventually move to MCP `elicitation` (M2) the host can
  declare these as proper protocol primitives.

- **Why a unified `/permissions` instead of more `/yolo`-style
  per-flag commands?** Two reasons. (1) The OSS-CC clones (Cline,
  ClawCode) all converged on a single `/permissions` surface — the
  tier-2 entry exists so future per-tool gates have a discoverable
  home rather than 5 new top-level slash commands. (2) Listing all
  gates side-by-side makes the security posture legible at a glance
  ("am I in YOLO right now?") rather than requiring the player to
  remember every relevant command.

- **What this lift does NOT do.** It doesn't add per-tool gates the
  way ClawCode does (e.g., "auto-approve `read_file` but gate
  `write_file`"). The reason: those gates would need to fire inside
  the specialist containers' tool-dispatch loop, and specialists
  don't have access to host CLISettings. That's an M2 (forge MCP)
  concern — once tools are MCP-served, the host can intercept each
  call via the MCP `elicitation` primitive (see M2 section in
  ROADMAP). For now, pipeline-level gating is the cleanest cut.

---

## Up next (queued, not yet active — tier order from #37 prioritization)

- **`A2A-Version` header** — one-line prerequisite for any v1.0
  migration attempt. Must add it to every outbound request in
  `remote_connections.py` before the SDK pin can flip to ≥1.0.
- **`/cost` alias for `/usage`** — five-line cleanup matching
  OSS-CC vocabulary so muscle-memory carries over.
- **MCP `roots` + `elicitation` declared at M2 init** — design-time
  work for when M2 (`kourai-forge-mcp`) is being scaffolded.
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
