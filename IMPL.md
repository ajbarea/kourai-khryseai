# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-26 · Working on: **M14 — Metis-First Parallel Routing**
(Phase 2 of `plans/2026-04-26-forge-order-confirmation.md`)

---

## Plan-of-record

End state: Metis discusses architectural tradeoffs in parallel with
Hephaestus's order classification, surfaced to the player on tier-2
(smart) and tier-3 (clarify) confirmations. Together with M13 the
player-experience load-bearing pair is complete: M13 makes the gate
legible (read-back-then-confirm), M14 fills the dead zone with
useful context.

Following the plan's TDD flow inline. T7 + T9 land in this PR with a
batch-parallel architecture (Metis runs concurrently, output buffered,
emitted at end). T8 (ParallelContext shared buffer feeding Metis's
partial output back into the classifier prompt to enrich the read-back
text) is deferred — the player still sees both panels independently.

### T7 part 1 — `discuss_tradeoffs` entry point on Metis ✅ 2026-04-26

- [x] `agents/metis/agent.py::discuss_tradeoffs`: new async function
      doing one `chat()` call with a focused "DISCUSSION MODE" system
      prompt — 1-2 short paragraphs, NOT a full spec, no FACT tags.
      `max_tokens=400` to bound runaway output.
- [x] Runs at whatever `KOURAI_MODEL_TIER` is active (no per-call
      tier override today). Future optimization: pin to `cheap`
      regardless of pipeline tier — would require `chat()` to grow a
      tier kwarg. Documented in the function docstring.

### T7 part 2 — Spawn Metis discussion in parallel ✅ 2026-04-26

- [x] `agents/hephaestus/agent_executor.py`: `_maybe_spawn_metis_discussion`
      kicks off `asyncio.create_task(discuss_tradeoffs(...))` BEFORE
      awaiting `determine_pipeline`. Skip entirely when `[yolo:` is in
      the input (power-user opt-out skips the parallel chatter too —
      no point burning tokens on chatter that won't reach the player).
- [x] `_cancel_metis` swallows `CancelledError` cleanly. Used on every
      route the player won't see Metis's output: CHAT, ASK_USER,
      malformed CONFIRM_ORDER, tier-1 confirmation, yolo pipeline.
- [x] Exception path: classifier raising → cancel Metis → re-raise
      so the executor's error handler sees the original exception.

### T9 — Surface Metis to player on tier 2/3 ✅ 2026-04-26

- [x] `_await_and_emit_metis(metis_task, updater, task, timeout=8.0)`
      awaits Metis with a deadline, emits the result as one
      `send_working_status` event with the Metis emoji prefix
      (`📐 \U0001f4d0`) so the host's existing `_maidenify_status`
      renders it as a Metis comms window. Italicized speech per M10
      kicks in automatically (Metis's discussion-mode prompt instructs
      her to quote player-directed lines).
- [x] Wired into the CONFIRM_ORDER branch: tier `smart` and `clarify`
      → `_await_and_emit_metis`; tier `clear` → `_cancel_metis`.
- [x] Timeout dropped silently — confirmation card still ships even
      if Metis dragged. The player never waits longer than the
      classifier required just because Metis is being verbose.

### T8 — DEFERRED

The plan's T8 (`ParallelContext` shared async buffer letting the
classifier read Metis's partial output during prompt construction)
is scoped out. M14 ships meaningful value without it: player sees
Metis's full discussion panel + the confirmation card on tier 2/3.
What T8 would add: the smart-tier read-back text would itself
mention Metis's specific concerns (vs. mentioning them via Metis's
panel and then again via the read-back). Worth a follow-up PR after
we feel whether the two-panel rendering is sufficient in dogfooding.

### M14 tests ✅ 2026-04-26

- [x] `tests/unit/test_metis_parallel.py`: 13 tests across 4 classes:
      - `TestDiscussTradeoffs` (4) — chat_response shape, agent name
        is "metis", DISCUSSION MODE marker present, `max_tokens` capped.
      - `TestParallelDispatch` (1) — Metis starts within 50ms of
        classifier (true `asyncio.gather`-style parallelism, not
        sequential).
      - `TestCancellationMatrix` (4) — CHAT / ASK_USER / clear-tier /
        yolo all take the cancel path (asserted via `_cancel_metis`
        spy; checking inside the patched `discuss_tradeoffs` doesn't
        work because the task can be cancelled before it ever
        schedules).
      - `TestSurfacing` (4) — smart + clarify emit Metis with the
        📐 emoji prefix; clear does NOT; Metis timeout doesn't block
        the confirmation card from firing.
      - Whole file passes in 2.78 s.

### Step 5 — Live smoke (queued for next interactive session)

- [ ] Send a tier-2 prompt (e.g., "add a divide function") → confirm
      Metis's discussion appears as a 📐 comms window BEFORE
      Hephaestus's confirmation card.
- [ ] Send a tier-1 prompt (e.g., "add quadruple(n)") → confirm
      Metis stays silent; only Hephaestus's card appears.
- [ ] `/yolo` → confirm Metis is not even spawned (no token spend).
- [ ] Compare wall-clock tier-2 latency before/after — should be
      ~max(metis, classifier) instead of sequential sum (~5s saved
      on tier-2 confirmations).
- [ ] Add a tier-2 capture to `assets/poster/forge-order-tier-2.txt`
      (per Round 7 in `SMOKE_TODO.md`) showing Metis's panel + the
      Hephaestus card together — that's the conference poster figure.

---

## Notes / open questions

- **Why batch-parallel, not live-streaming?** Streaming Metis's chunks
  to the player as they arrive (rather than buffering until classifier
  decides) would fill the dead zone live, but introduces ugly edge
  cases: if the classifier decides CHAT mid-stream, the player sees
  half a Metis sentence then a chat response. Buffer-then-emit at end
  is cleaner UX. Trade-off: the dead zone is shorter (max(metis,
  classifier) instead of sum) but still present in absolute terms.

- **Tier-1 silently drops Metis's work.** ~5 seconds of LLM compute
  goes nowhere on every clear-tier confirmation. Tradeoff: spawning
  Metis later (only after classifier returns smart/clarify) would
  make the smart/clarify path SLOWER (sequential), defeating the
  parallel-latency benefit. The waste on tier-1 is the price for
  the win on tier-2/3. If the cheap-tier override lands later
  (T7-future), the cost on tier-1 drops to near-zero.

- **No A2A round-trip for Metis discussion.** `discuss_tradeoffs` is
  called directly from Hephaestus's process via the in-process
  `chat()` helper, not via A2A to Metis's container. Saves the A2A
  hop latency. Metis's container still handles the actual `create_spec`
  call later in the pipeline — this is just a lightweight brainstorm.

- **T8 (ParallelContext) is a real refinement worth shipping.** The
  smart-tier read-back today is generated by the classifier without
  Metis's input. T8 would let the classifier prompt include Metis's
  partial notes ("Metis is flagging zero-division — fold into your
  read-back if relevant"). Smaller surface than the M14 work itself.

---

## Up next (queued, not yet active)

- **T8 follow-up** (ParallelContext shared buffer) — feed Metis's
  partial output into the classifier prompt so smart-tier read-backs
  reference her specific concerns.
- **T4 follow-up from M13** (`[forge_intent]` block on user message
  to specialists) — paired well with T8.
- **M9** (Opus 4.6 → 4.7 in `MODELS_SMART["metis"]`) — one-line bump.
- **M2** (`kourai-forge-mcp` server).
- **M15** (forge logging architecture).
- **M5** (UID alignment for forge worktrees).
- **M7** (a2a-sdk 1.0.x migration).
- **M12** (dynamic sizing across the GUI).
