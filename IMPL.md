# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **M13 — Forge Order Confirmation**
(Phase 1 of `plans/2026-04-26-forge-order-confirmation.md`)

---

## Plan-of-record

End state: every development task goes through a guaranteed pre-pipeline
confirmation gate. Hephaestus reads the parsed intent back to the player
("Light the forge?") and waits for explicit confirmation before any
specialist runs. Three tiers scale verbosity to ambiguity (clear / smart
/ clarify). `/yolo` opts out for power users.

Following the plan's TDD flow inline (not subagent-driven). T1-T3 + T5 +
T6 land in this PR. T4 (ForgeSession `[forge_intent]` block for richer
specialist context) deferred to a follow-up — the gate works without it
because the LLM router sees the prior CONFIRM_ORDER + player response in
context_id memory automatically.

### T1 — CONFIRM_ORDER protocol parser + ROUTING_PROMPT ✅ 2026-04-26

- [x] `agents/hephaestus/confirmation.py`: `parse_confirmation_response`
      decodes `CONFIRM_ORDER: <tier> "<read-back>"` → frozen
      `ConfirmationResponse(tier, read_back)`. Three known tiers, raises
      on unknown / malformed.
- [x] `agents/hephaestus/agent.py::ROUTING_PROMPT`: response option #5
      added with the three-tier rubric, examples, and voice constraints
      (tight tier 1; tier 2 may have one in-character aside; never
      roasts the player).
- [x] `tests/unit/test_hephaestus_confirmation.py`: 12 tests across 2
      classes (parser happy/error paths, prompt content assertions).

### T2 — Wire CONFIRM_ORDER through executor → INPUT_REQUIRED ✅ 2026-04-26

- [x] `agents/hephaestus/agent.py::determine_pipeline`: recognises
      `CONFIRM_ORDER:` prefix and forwards verbatim, parallel to the
      existing `ASK_USER:` / `CHAT:` branches.
- [x] `agents/hephaestus/agent_executor.py`: new branch ahead of the
      existing `ASK_USER:` handling. Parses the token, prefixes the
      Hephaestus emoji (`AGENT_EMOJI["hephaestus"]`) so the host's
      `_maidenify_status` renders as a comms window, appends a
      tier-specific suffix (Metis-muttering hint on smart, forge-cools
      hint on clarify), then calls `send_input_required`.
- [x] Fail-safe: malformed CONFIRM_ORDER tokens log a warning and
      surface a generic ask — never auto-execute.
- [x] Resume is implicit: the next user message lands in the same
      context_id, the LLM sees the CONFIRM_ORDER + player response in
      memory, and emits the agent list on the resumed routing call.
      No explicit "resume metadata" plumbing needed.
- [x] `tests/unit/test_confirmation_protocol.py` `TestDeterminePipeline*`
      and `TestExecutorEmits*`: 8 tests covering tier forwarding +
      executor INPUT_REQUIRED emission + emoji-prefix + tier suffixes
      + malformed fail-safe + pipeline-not-running guard.

### T3 — CLI render confirmation card + `/yolo` toggle ✅ 2026-04-26

Skipped the plan's `format_confirmation_card` invention — the executor's
emoji-prefixed message already routes through the existing
`_maidenify_status` → `_comms_window` pipeline and renders correctly
via M10's italic-on-quoted convention. One less abstraction.

- [x] `hosts/cli/settings.py`: `yolo_enabled: bool = False` field.
      Plus a forward-compat fix to `CLISettings.load()` that drops
      unknown JSON keys silently (regression that pre-existed M13 — a
      hypothetical future settings upgrade would have crashed otherwise).
- [x] `hosts/cli/completer.py`: `/yolo` registered.
- [x] `hosts/cli/__main__.py`: `/yolo` handler toggles, persists, prints
      a state line. The text-tag `[yolo: on]\n` prepends to outgoing
      `forge_msg` when enabled.
- [x] `agents/hephaestus/agent.py::extract_yolo`: strips the tag,
      returns `(clean_text, yolo_bool)`. Same convention as
      `extract_project_root` and `extract_relationship_tiers`.
- [x] `determine_pipeline`: when yolo is set, augments the system prompt
      with `YOLO MODE: skip CONFIRM_ORDER, emit agent list directly`.
- [x] `tests/unit/test_confirmation_protocol.py` `TestYoloBypass` and
      `TestCLISettingsYoloField`: 9 tests — extraction (case-insensitive,
      tag-only not bare-word match), system-prompt augmentation, default
      OFF, toggle persists, unknown-keys-don't-crash.

### T4 — Forge session captures confirmed-spec → memoir (DEFERRED)

Scoped out of this PR. The gate is functional without it because the
LLM router on the resume turn already sees the CONFIRM_ORDER + player
response in context_id memory and emits the agent list informed by
that context. Specialists today receive the player's resume message as
the user_request; the original ask is implicit but not explicitly
fielded into a `[forge_intent]` block.

Adding the explicit `[forge_intent tier=X ORIGINAL: ... PLAYER_CONFIRMED:
...]` block (per the plan's T4) would let Metis / Techne / Dokimasia /
Kallos work against the structured confirmed scope rather than the
inferred one. Worth a follow-up PR once we feel whether the implicit
context is sufficient in dogfooding.

### T5 — Voice regression tests ✅ 2026-04-26

- [x] `tests/integration/test_confirmation_voice.py`: 31 tests across
      4 parametrised cases. Curated GOOD_CLEAR / GOOD_SMART /
      GOOD_CLARIFY corpora; `BANNED_PHRASES` list catches mocking /
      condescending tones (`"really?"`, `"that's all"`, `"obviously"`,
      etc.); tier-1 verbosity cap (≤15 words); no-quoted-quotes hygiene
      so read-backs round-trip through the parser cleanly. Voice drift
      is now a test failure, not a vibe-check.

### T6 — SMOKE_TODO Round 7 ✅ 2026-04-26

- [x] `SMOKE_TODO.md`: Round 7 appended after Round 6. Three tier
      exercises with intentionally chosen prompts (tier-1 quadruple,
      tier-2 divide, tier-3 "make my codebase faster"). `/yolo`
      verification. Save terminal output to
      `assets/poster/forge-order-tier-{1,2,3}.txt` for the conference
      poster figure.

### Step 7 — Live smoke (queued for next interactive `/project` session)

- [ ] Round 7 from `SMOKE_TODO.md` — three-tier walkthrough + `/yolo`
      verification + poster artifact capture. ~10 min interactive.

---

## Notes / open questions

- **Why prefix the read-back with the Hephaestus emoji in the
  executor (vs adding a new format_confirmation_card)?** The host's
  existing `_maidenify_status` already renders emoji-prefixed status
  text as a comms window for the matched agent. Adding a new
  card-renderer would have duplicated that convention. Server-side
  composition keeps the CLI side a no-op for this feature.

- **Why text-tag `[yolo: on]` instead of A2A message metadata?**
  Because `[project_root: …]` and `[relationship_tiers: …]` already
  use the text-tag convention in this codebase, and message metadata
  isn't guaranteed to be forwarded by every transport per the comment
  in `extract_project_root`. Following the established pattern is
  cheaper than adding a transport-dependent metadata field.

- **The `CLISettings.load()` unknown-keys fix is in passing.** Before
  this PR, adding a new field to `CLISettings` and trying to load an
  older `cli_settings.json` would crash because `cls(**data)` errors
  on unknown keys. That used to be silently OK because the dataclass
  fields have all been there forever. Now that we're adding fields
  more often, the forward-compat fix prevents a future-rolled-back
  build from breaking the player's settings. Asserted in
  `test_load_tolerates_unknown_keys`.

---

## Up next (queued, not yet active)

- **Phase 2 of the M13/M14 plan** — Metis-first parallel routing
  (T7-T9): spawn Metis's `discuss_tradeoffs` in parallel with the
  classifier so the dead zone becomes engaging architectural dialogue.
  Builds on M13's CONFIRM_ORDER primitives. Separate PR.
- **T4 follow-up** — `[forge_intent]` block on the user message
  passed to specialists, so Metis / Techne / Dokimasia / Kallos see
  the confirmed scope explicitly rather than via implicit context_id
  memory. Tractable as a small standalone PR once we feel whether
  the implicit context is sufficient.
- **M9** (Opus 4.6 → 4.7 in `MODELS_SMART["metis"]`) — one-line
  bump, unblocked by Round 6.
- **M2** (`kourai-forge-mcp` server) — unblocked by Round 6.
- **M15** (forge logging architecture) — operational hygiene.
- **M5** (UID alignment for forge worktrees) — quality-of-life.
- **M7** (a2a-sdk 1.0.x migration) — properly scoped.
- **M12** (dynamic sizing across the GUI) — biggest GUI refactor.
