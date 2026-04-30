# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-04-30 · Working on: **M18 Phase 1 SHIPPED 2026-04-30
(eight PRs: #99/#100/#101/#102/#103/#104/#105/#106 — contract + 10
specialist producers + 1 consumer migration). All eleven agents
participate in the URI-namespaced extension key
``"https://kourai.khryseai/ext/streaming/v1"`` with
``{"content_kind": "dialogue" | "status" | "code" | "spec"}`` nested
under it. Active focus: validate Phase 1 end-to-end via live smoke
(blocked on smoke-driver update to pre-seed project facts via
``/preferences set`` so metis skips the M17 PAUSE), then proceed to
Phase 2 (SSML inside dialogue bodies) — Kokoro doesn't natively consume
SSML so transitional strip-then-synthesize, ElevenLabs migration on M6
unblocks full SSML downstream.**

## M18 Phase 1 — what shipped (eight PRs, 2026-04-30)

| PR | Subject | Sites | Notes |
|---|---|---|---|
| #99 (`8658013`) | content-kind contract + hephaestus pilot | n/a + 6 | URI extension key, ``KIND_*`` constants, helpers, optional ``kind=`` kwarg on every ``TaskUpdater`` helper. Hephaestus tags CONFIRM_ORDER / INPUT_REQUIRED forward / parallel-discussion as ``KIND_DIALOGUE``; routing + pipeline status as ``KIND_STATUS``. Host CLI gates TTS on ``kind is None or kind == KIND_DIALOGUE``. |
| #100 (`31f846c`) | metis | 7 | "Analyzing project structure...", git status, "Drafting spec...", "Planning: <latest>" snippets, "Spec complete" → ``STATUS``; M17 recall narration + M17 PAUSE input_required → ``DIALOGUE``. |
| #101 (`5e6d603`) | techne | 5 | All ``STATUS`` — "Reading existing code...", git status, "Generating code changes...", per-tool-call results, "Applied N code changes". |
| #102 (`c0f6fd0`) | dokimasia + shared ``fix_loop`` | 5 + 4 | All ``STATUS``. fix_loop is shared with kallos so the helper's iteration beats are tagged once. |
| #103 (`6af8545`) | kallos | 3 | All ``STATUS`` — lint output, fix tool calls, Aidos slop relay. |
| #104 (`cde587c`) | mneme | 7 | First specialist after hephaestus to use both kinds — 6 ``STATUS`` (analyzing / drafting / Aidos relay / Aletheia relay / PR-creation status) + 1 ``DIALOGUE`` (the ``spoken_intro`` line that ``_split_response`` deliberately separates from artifact body). |
| #105 (`fb5e9c5`) | puck + cupid + aletheia + aidos (bundled) | 1+1+2+2 | All ``STATUS``. Companions and post-process specialists; their player-facing content flows through ``add_artifact``, not status emissions. |
| #106 (`859a28b`) | vn_bridge consumer routing | 1 site rewritten | Replaces vn_bridge's prose-keyword DIALOGUE_KEYWORDS heuristic with ``get_content_kind``-based routing, mirroring the host CLI predicate shape. ``kind is None`` legacy fallback retained as a safety net. |

Audit-cleanup commits that landed on the same branches:
- ``5ffa4cb chore(ci): silence ty warnings + transitive pydub noise`` —
  two `ty: ignore[code]` comments + filterwarnings entries for pydub.
- ``927d464 chore(ci): bump actions/cache v4 → v5.0.5 for sister-repo parity``
  — flagged by ``/aj-sisters`` audit; v5 runs Node 24 + cache-service v2
  backend.

## Live-smoke evidence

**2026-04-30 morning re-run (URI shape, against rebuilt M18 containers
post-#99):** Wire shape verified end-to-end. Targeted grep across all
11 specialist container logs for ``KOURAI_STREAMING_EXT_URI`` /
``content_kind`` / ``set_content_kind`` / ``get_content_kind`` /
``kourai.streaming`` / ``kourai/ext/streaming`` returned zero hits in
error contexts — protobuf ``Struct`` round-trip works under live
container load. M13 baseline preserved (metis "Streaming spec for:
[User]: ..."). M17 dialogue gate fires through
``send_input_required(kind=KIND_DIALOGUE)`` URI emission.

**Pending (full-pipeline post-#100..#106 smoke):** end-to-end run with
all eleven specialists on the URI shape. Requires:
1. Container rebuild against latest main (8 commits ahead of the
   morning rebuild)
2. Smoke driver update (pre-seed project facts via ``/preferences set``
   so metis skips the M17 PAUSE — see "100% round-trip" finding below)
3. Voice-off smoke gives functional verification (no exceptions,
   pipeline reaches "Forged in" through all specialists, kind-routing
   logs in vn_bridge confirm metadata flow). Audio-on cadence-diff
   measurement still blocked on WSL2 PortAudio crackling
   (``feedback_drive_smoke_yourself.md``,
   ``shared/src/kourai_common/audio.py`` comment).

## "100% round-trip" finding — investigated 2026-04-30

The smoke driver's "answer the metis dialogue gate with '100%'"
assumption was wrong. Per ROADMAP §M17, M17 is **future-run preference
recall**, not in-flight pipeline resume. Designed flow:
1. Metis hits ``PAUSE: <kind>`` token, stashes preference_kind via
   ``pause_state.stash_preference_kind``
2. Metis emits INPUT_REQUIRED, the metis task TERMINATES
3. Hephaestus catches ``AgentInputRequired``, yields INPUT_REQUIRED to
   CLI, the pipeline run ENDS at that state
4. Player answers; CLI synthesizes a project-scoped fact via
   ``synthesise_fact_from_pause``
5. The **next** development request in this project sees the fact via
   ``build_fact_context``; metis no longer needs to ask

So the ``Forged in 1.6s`` outcome was the EXPECTED endpoint on a fresh
project — the pipeline doesn't continue mid-flight. To drive
metis → techne → dokimasia → kallos → mneme end-to-end in one run, the
project facts must be pre-seeded so metis doesn't pause at all. Two
paths in priority order:

- **Pre-seed via ``/preferences set``** (M17 Phase 2 CRUD CLI) before
  the smoke prompt. Sets ``test_framework=pytest`` /
  ``coverage_target=100%`` etc. as project-scoped facts; metis reads
  them via ``build_fact_context`` and skips the PAUSE.
- **Two-run smoke**: first run pauses, stashes the fact; second run
  benefits from recall narration ("Metis remembers...") and runs
  through.

## Phase 2 — SSML inside dialogue bodies (next architectural work)

Each ``KIND_DIALOGUE`` Part text body becomes an SSML document —
``<speak>...<break time="200ms"/>...<emphasis>...</emphasis>...</speak>``.
Standard W3C markup, supported declaratively by Google / Azure /
Amazon / ElevenLabs. Kokoro doesn't natively consume SSML; we
strip-then-synthesize as a transitional layer. ElevenLabs migration on
M6 unblocks full SSML downstream.

Open questions for Phase 2 (web-search before any implementation, per
standing rule):
- **Where does SSML get added — at producer, consumer, or both?**
  Producer side (specialist's ``send_input_required`` / dialogue
  emissions) means each specialist owns its prosody. Consumer side
  (host CLI / vn_bridge wraps in default SSML) means a single layer
  controls the cadence baseline.
- **Strip-then-synthesize layer placement.** Current Kokoro path is
  via ``kourai_common.tts_realtime.RealtimeTTSEngine``. SSML strip
  could live in the engine itself (so callers stay SSML-agnostic) or
  in the host (so SSML is end-to-end visible in logs).
- **Per-specialist persona prosody** (e.g., Hephaestus gruff vs Kallos
  lilting) — defer to a follow-on once structural plumbing is in.

## Phase 3 — KIND_CODE / KIND_SPEC distinct render paths

Once Phase 1 is fully validated end-to-end (full-pipeline smoke
passes) and Phase 2 is in:
- Drop the ``or kind is None`` legacy fallback in
  ``hosts/cli/streaming.py`` (line 230) and
  ``agents/vn_bridge/__main__.py`` — every specialist tags now, the
  fallback should never execute in production.
- Distinct render paths for ``KIND_CODE`` (monospace, no TTS) and
  ``KIND_SPEC`` (wide markdown render, no TTS) — currently both
  collapse to "not dialogue, render as status". Phase 3 splits them so
  spec output renders in a wide markdown panel (vs the narrow status
  box) and code output renders in a monospace block with syntax
  highlighting.

Today only ``KIND_DIALOGUE`` and ``KIND_STATUS`` are emitted by any
specialist. ``KIND_CODE`` and ``KIND_SPEC`` are reserved tokens — their
producer-side adoption is part of Phase 3 work.

## Open issues — independent UX bugs (small focused PRs each)

**Solved by completing M18:** comms-window streaming as discrete narrow
boxes, final-render wide-box only-some-agents, TTS gating universal,
FACT-tag leakage into status, Mneme reading 905-char dialogue including
markdown markup aloud.

**Independent UX bugs:**
- `Pipeline complete` + `commit_count: 0` together with no soft-fail
  surface (#17)
- Per-agent CLI color coding via colored-background "badge" pattern
  (Okabe-Ito CVD-safe, NO_COLOR-aware) (#10)
- Music playlist sparse — 2 tracks (#11)
- Agent-card poll storm — 30+ GET ``/.well-known/agent-card.json`` per
  minute on idle agents (#12)
- Context7 MCP integration broken: ``MCP error -32602: Tool
  get-library-docs not found`` AND URL template emits literal
  ``[User]:`` placeholder (#14)
- Duplicate empty `Project root:` field at end of metis enriched
  prompt (#15)
- Phonemizer warning spam on every TTS call — downgrade to DEBUG (#22)
- Pre-warm Kokoro per-language at engine init (#23)
- Explicit captions / TTS subtitle toggle for accessibility (#19)

## Notes / open questions

- **MCP elicitation deferred-by-design.** Real-caller-driven only.
  Architectural notes from closed
  [PR #74](https://github.com/ajbarea/kourai-khryseai/pull/74) capture
  the round-trip design when the first forge MCP tool wants
  ``ctx.elicit()``.
- **MCP spec version pinned to 2025-11-25.** Spec drift watcher cron
  (``scripts/watch_protocols.py``, runs Sundays 13:00 UTC) flags any
  subsequent revision.
- **``run_post_task_hooks`` orchestration unwired.** Layer is fully
  tested but no production call sites; ``synthesise_fact_from_pause``
  lives directly in ``streaming.py`` as the pragmatic answer.
  Promotion is sibling work flagged for M5/M6.
- **Specialist parity for fact recall.** Today only metis reads
  ``build_fact_context`` with project scope; techne / kallos /
  dokimasia / hephaestus inherit the gap. Defer until a non-metis
  PAUSE caller surfaces.
- **Sisters audit weekly cron** (``trig_013uP9ryCLYscBKS7X6PB5og``,
  Mondays 12:00 UTC) opens drift PRs and a rollup issue automatically
  for action-pin / toolchain-pin / merge-setting / open-PR / local-main
  divergence findings.

## Up next — priority order

UX/DX is the default between milestones. Pre-release perfection
stance: no workarounds, web-search 2026 best practice before any
implementation, architectural fix over expedient patch.

1. **Update smoke driver** to pre-seed project facts via
   ``/preferences set`` so metis skips the M17 PAUSE; full-pipeline
   smoke then runs end-to-end in one shot.
2. **Full-pipeline live smoke** against latest main (post-#106) with
   the updated driver — first end-to-end run with all eleven
   specialists on the URI shape.
3. **M18 Phase 2 — SSML inside dialogue bodies.** Web-search 2026 SSML
   best practice (W3C SSML 1.1 status, ElevenLabs/Azure provider
   subset compatibility) before any implementation. Decide
   producer-vs-consumer SSML wrapping.
4. **M18 Phase 3 — KIND_CODE / KIND_SPEC distinct render paths.** Drop
   the ``or kind is None`` legacy fallback once full-pipeline smoke
   confirms no untagged emissions in production. Wide markdown render
   for spec, monospace + syntax highlighting for code.
5. **M20 — Audio-text synchronization.** Builds on M18 (kind routing)
   + M19 (RealtimeTTS word-timing API already wired via ``on_word=``
   callback). 9-14s text-precedes-audio gap is a player-notices UX
   issue.
6. **Independent UX bugs** from the smoke (above).
7. **Live VN smoke** — exercises the new vn_bridge ``/tts`` →
   ``RealtimeTTSEngine.synthesize_to_wav`` path AND the new
   metadata-based dialogue routing.
8. **``docs/architecture/puck-first-run-tutorial.md``** — pairs with
   the M6 player-onboarding theme.
9. **M5 / M12 / M15 / M6 follow-ons** — see ROADMAP for scope.
