# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When a
milestone lands, its detail block in [ROADMAP.md](./ROADMAP.md) collapses
to a one-liner under "Shipped" and this file resets to the next milestone.
Git history is the archive — these docs are plans + scratchpad, not a
historical record.

Updated: 2026-05-03 · Active focus: **M6 ElevenLabs hybrid as
pre-player-release blocker** (promoted from "future-future").
SSML markup investment reverted [#152]; defensive strip helpers
stay. main is clean; issue #126 (upstream-blocked
`@xmldom/xmldom@0.8.12` HIGH bundled inside npm 11.13.0) is
auto-managed by `.github/workflows/issue-126-rescan.yml` —
Saturdays 14:17 UTC from 2026-05-16, auto-closes once upstream
lands `>=0.8.13`.

## M18 Phase 2 — walked back to plain-text dialogue (closed)

The original Phase 2 plan was producer-side SSML emission with
engine-side strip-then-synthesize, anticipating an M6 ElevenLabs swap.
PRs [#147] (strip layer), [#149] (hephaestus pilot), and [#150]
(handoff/victory rollout) shipped that direction; closed PR #151
(greetings/gossip) was queued. **All dialogue-content SSML reverted
in [#152] after verifying ElevenLabs's actual May 2026 docs:**

- **Eleven v3 (M6 high-impact-line target per VOICE_CASTING_PLAN.md)**
  does NOT support SSML break tags. Their idiom is `[bracket]` audio
  tags (`[whispers]`, `[sarcastic]`) + ellipses + natural punctuation.
- **Eleven Flash V2.5 (M6 routine-dialogue target)** supports `<break>`
  in theory but ElevenLabs explicitly warns *"too many break tags can
  cause instability"* and recommends ellipses/dashes anyway.
- **Kokoro mainline (current engine)** has zero native SSML
  (`hexgrad/kokoro#36` open).

So `<speak>...<break time="200ms"/>...</speak>` was the wrong markup
for both Kokoro AND the planned M6 target. Original strings already
had natural punctuation that BOTH engines honor for pauses without
any tagged markup.

**What stays as defensive infrastructure (not reverted):**
- `kourai_common.ssml.strip_ssml` + defusedxml dep — guards against
  any future LLM output that might wrap text in `<speak>` or other
  XML-shaped markup.
- `_comms_window` strip chokepoint, `_maidenify_status` strip,
  `RealtimeTTSEngine.speak()` + `synthesize_to_wav()` strips,
  vn_bridge NDJSON yield strip — idempotent and fast on plain text
  via the `<`-substring early return.
- Cross-platform TTS auto-mute [#146], uvicorn-takeover sweep [#148],
  vn_bridge headless unblock [#145] — unrelated to the SSML walk-back.

**Lesson logged in memory** ([feedback_websearch_before_arch_decision.md](
../../.claude/projects/-home-ajbar-ajsoftworks/memory/feedback_websearch_before_arch_decision.md)):
web-search the SPECIFIC target's primary docs at the IMPL/ROADMAP
planning step, not just at implementation time. The "portable subset"
claim from generic SSML web-search wasn't enough — verifying against
ElevenLabs's actual best-practices page would have flagged this on
day 1 instead of after 5 PRs.

## M6 — ElevenLabs hybrid (pre-player-release blocker)

Promoted from "future-future" based on 2026-05-03 strategic discussion.
Character voice is the product (Hephaestus gruff vs Kallos lilting);
Kokoro can't deliver per-character emotional control; ElevenLabs can.
[VOICE_CASTING_PLAN.md](../tools/voice-lab/VOICE_CASTING_PLAN.md)
already has voice IDs + settings cast for each maiden.

**Model strategy** (per VOICE_CASTING_PLAN.md):
- `eleven_flash_v2_5` for routine live dialogue + handoffs (low latency,
  $0.06 / 1k chars).
- `eleven_v3` for high-impact lines — victory lines, key handoffs,
  onboarding moments ($0.12 / 1k chars, audio-tag emotional control).

**Cost projections (2026-05 ElevenLabs API pricing):**
- Pre-release dev (~200 lines/day × 50 chars): ~$22/month.
- 100 active players (~200 lines/session × 30 sessions): ~$2,160/month.
- 1000 active players: scales linearly to ~$21,600/month — needs the
  audio caching add-on below to cut billed chars 50-80%.

**Required add-ons before player release:**
- **Audio caching layer.** Static dialogue (HANDOFF_LINES,
  VICTORY_LINES, greetings) repeats constantly across players —
  render WAV bytes ONCE per (text, voice) pair, cache on disk / CDN,
  serve from cache. Probably 50-80% reduction in billed chars at
  player scale.
- **Per-engine markup adapter** at the engine boundary, replacing the
  reverted SSML approach. Producers emit plain text; the adapter
  layer adds engine-specific formatting (`[bracket]` audio tags for
  v3, ellipses for both, optional `<break>` for Flash V2.5 if cost
  testing shows benefit). Keeps producers engine-agnostic.
- **Per-persona prosody design pass.** With actual ElevenLabs voices
  and audio tags, decide which maidens get which emotional defaults
  ([whispers] for Kallos when teasing, [sarcastic] for Dokimasia,
  etc.). Was deferred under the SSML plan; now design-tractable
  against real reference audio.

**Open question:** does ElevenLabs's API support response-level audio
caching (caching by request hash) or do we have to build it
client-side? Web-search at implementation start.

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

Pre-release perfection stance: no workarounds, web-search May 2026
best practice **at the planning step** (not just at implementation —
see [feedback_websearch_before_arch_decision](../../.claude/projects/-home-ajbar-ajsoftworks/memory/feedback_websearch_before_arch_decision.md)),
architectural fix over expedient patch. Pick by impact + caller
reality, not file-of-origin.

1. **M20 sub-task 2 — audio-led text reveal.** Confirmed load-bearing
   on both surfaces by the 2026-05-03 measurement (3s streaming, 4-7s
   vn_bridge full-WAV). **Tier 2 (CLI surface) shipped [#153]:**
   `_format_greeting` (startup banner) and the streaming.py KIND_DIALOGUE
   path now defer the comms-window echo until the engine's
   `on_audio_start` trampoline fires, eliminating the
   "text-precedes-audio" disconnect. Auto-mute / engine-error / muted
   paths echo via the finally-fallback so dialogue is never lost.
   **Tier 1 (word-by-word reveal via RealtimeTTS `on_word` callback)
   for English voices follows next.** Sub-task 3 (GUI + VN surfaces)
   reuses the same plumbing. Worth driving on Kokoro now since the
   callback API path is engine-agnostic — any work here carries to
   ElevenLabs unchanged.
2. **Live VN smoke** — exercises the vn_bridge `/tts` →
   `RealtimeTTSEngine.synthesize_to_wav` path + metadata-based
   dialogue routing end-to-end. Needs AJ at the keyboard.
3. **`docs/architecture/puck-first-run-tutorial.md`** — pairs with
   the M6 player-onboarding theme. Tractable autonomously.
4. **M6 ElevenLabs hybrid prep** — investigate response-level audio
   caching (web-search ElevenLabs API at start), spec the per-engine
   markup adapter, prototype voice-lab → production wiring. Don't
   ship the actual swap until M20 + VN smoke land — character voice
   quality matters most when the rest of the dialogue UX is dialed.
5. **M18 Phase 3 Part B** — distinct render paths for `KIND_CODE` /
   `KIND_SPEC`. Blocked on a specialist actually emitting either kind.
6. **GUI `hosts/gui/maidens.py` dialogue dedup** — separate copy
   diverged from `shared/src/kourai_common/agents.py`. Consolidation
   needs design pass on which copy is canonical (GUI has more entries).
7. **M5 / M12 / M15 follow-ons** — see ROADMAP for scope.

Music playlist (#11) — content-driven; AJ adds tracks to
`assets/audio/music/` over time. No code work.
