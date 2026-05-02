# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When a
milestone lands, its detail block in [ROADMAP.md](./ROADMAP.md) collapses
to a one-liner under "Shipped" and this file resets to the next milestone.
Git history is the archive — these docs are plans + scratchpad, not a
historical record.

Updated: 2026-05-02 · Active focus: **M18 Phase 2 (SSML inside dialogue
bodies)**. M18 Phase 3 Part A (strict kind routing) shipped today. main
is clean; issue #126 (upstream-blocked `@xmldom/xmldom@0.8.12` HIGH
bundled inside npm 11.13.0) is auto-managed by
`.github/workflows/issue-126-rescan.yml` — Saturdays 14:17 UTC from
2026-05-16, auto-closes once upstream lands `>=0.8.13`.

## M18 Phase 2 — SSML inside dialogue bodies (active)

Each `KIND_DIALOGUE` Part text body becomes an SSML document —
`<speak>...<break time="200ms"/>...<emphasis>...</emphasis>...</speak>`.
Standard W3C markup, supported declaratively by Google / Azure / Amazon /
ElevenLabs. Kokoro doesn't natively consume SSML; we strip-then-synthesize
as a transitional layer. ElevenLabs migration on M6 unblocks full SSML
downstream.

**Provider compatibility (web-searched 2026-05-02):**
- **W3C SSML 1.1** — stable Recommendation since 2010, no spec drift to plan against.
- **Kokoro** — zero native SSML support (multiple open feature requests on
  `hexgrad/kokoro` and `Kokoro-FastAPI`). Strip-then-synthesize is the only
  viable path while Kokoro is the engine.
- **ElevenLabs** — supports `break`, `phoneme`, `prosody`, `emphasis` on
  most models, but **NOT on Eleven v3** (current flagship). If M6 targets v3,
  SSML support is a regression vector; if it targets Flash V2 / Turbo V2 /
  English V1, full subset works.
- **Azure + Google Cloud** — full subset including `prosody` (rate/pitch/range/
  volume/contour), `break`, `emphasis`, `say-as`, `phoneme`, `sub`, `p`, `s`, `audio`.
- **Portable subset** (works across ElevenLabs-non-v3 + Azure + Google):
  `break`, `prosody`, `emphasis`, `say-as`. Avoid `phoneme` if v3-on-ElevenLabs
  is on the roadmap; avoid `audio` (provider-side resource fetch).

**Open questions:**
- **Producer vs consumer SSML wrapping?** Producer-side (each specialist's
  emissions) means each specialist owns its prosody — Kallos's lilt vs
  Hephaestus's gruff cadence stays per-agent, matching the Phase 1 content-
  kind tagging architecture. Consumer-side (host CLI / vn_bridge wraps in
  default SSML) means a single layer controls the cadence baseline;
  specialists stay text-only and prosody is uniform. Producer-side composes
  better with per-agent persona work; consumer-side ships faster.
- **Strip-then-synthesize layer placement.** SSML strip in
  `kourai_common.tts_realtime.RealtimeTTSEngine` keeps callers SSML-agnostic
  and a future engine swap inherits the strip layer; SSML strip in the host
  keeps it end-to-end visible in logs and explicit at the engine boundary.
  Engine-side parallels how Azure/Google SDKs handle SSML internally.
- **Per-specialist persona prosody** (Hephaestus gruff vs Kallos lilting) —
  defer to a follow-on once structural plumbing is in.

## M18 Phase 3 — KIND_CODE / KIND_SPEC distinct render paths (deferred)

**Part A — strict kind routing** shipped ahead of Phase 2 since it stood
on its own. The two surviving forwarders (hephaestus's pipeline-status
re-emitter; `BaseAgentExecutor`'s empty-input prompt) now tag explicitly,
so the `kind is None or` fallback is gone from `hosts/cli/streaming.py`
and the prose-keyword `DIALOGUE_KEYWORDS` heuristic is gone from
`agents/vn_bridge/__main__.py`. Untagged messages are now routed as
not-dialogue everywhere.

**Part B — distinct render paths for `KIND_CODE` / `KIND_SPEC`** is
deferred. Both kinds are reserved tokens with no producer; building host-
side render paths before any specialist emits them is anticipatory infra.
Re-enter Part B once a specialist (likely techne for code, metis for spec)
opts into emitting these kinds.

## Notes / open invariants

- **MCP elicitation deferred-by-design.** Real-caller-driven only.
  Architectural notes from closed
  [PR #74](https://github.com/ajbarea/kourai-khryseai/pull/74) capture
  the round-trip design when the first forge MCP tool wants `ctx.elicit()`.
- **MCP spec version pinned to 2025-11-25.** Spec drift watcher cron
  (`scripts/watch_protocols.py`, runs Sundays 13:00 UTC) flags any
  subsequent revision.
- **`run_post_task_hooks` orchestration unwired.** Layer is fully tested
  but no production call sites; `synthesise_fact_from_pause` lives
  directly in `streaming.py` as the pragmatic answer. Promotion is sibling
  work flagged for M5/M6.
- **Specialist parity for fact recall.** Today only metis reads
  `build_fact_context` with project scope; techne / kallos / dokimasia /
  hephaestus inherit the gap. Defer until a non-metis PAUSE caller surfaces.
- **Sisters audit weekly cron** (`trig_013uP9ryCLYscBKS7X6PB5og`,
  Mondays 12:00 UTC) opens drift PRs and a rollup issue automatically.
- **Issue #126 auto-rescan** (`.github/workflows/issue-126-rescan.yml`)
  fires Saturdays 14:17 UTC from 2026-05-16 until the bundled
  `@xmldom/xmldom` lands `>=0.8.13` across our three npm-bearing images.

## Up next — priority order

Pre-release perfection stance: no workarounds, web-search 2026 best
practice before any implementation, architectural fix over expedient patch.
Pick by impact + caller reality, not file-of-origin.

1. **M18 Phase 2 — SSML inside dialogue bodies** (active focus above).
2. **M20 — Audio-text synchronization.** Builds on M18 (kind routing) +
   M19 (RealtimeTTS word-timing API already wired via `on_word=` callback).
   9-14s text-precedes-audio gap is a player-notices UX issue.
3. **Live VN smoke** — exercises the new vn_bridge `/tts` →
   `RealtimeTTSEngine.synthesize_to_wav` path AND metadata-based dialogue
   routing.
4. **`docs/architecture/puck-first-run-tutorial.md`** — pairs with the M6
   player-onboarding theme.
5. **M18 Phase 3 Part B** — distinct render paths for `KIND_CODE` /
   `KIND_SPEC`. Blocked on a specialist actually emitting either kind.
6. **M5 / M12 / M15 / M6 follow-ons** — see ROADMAP for scope.

Music playlist (#11) — content-driven; AJ adds tracks to
`assets/audio/music/` over time. No code work.
