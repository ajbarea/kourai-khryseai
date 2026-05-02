# Kourai Khryseai — Implementation scratchpad

The active TODO list for whatever we're working on right now. When the
milestone lands, the matching detail block in [ROADMAP.md](./ROADMAP.md)
collapses to a one-liner under "Shipped" and this file gets reset to the
next milestone.

Updated: 2026-05-02 · Working on: **M18 Phase 1 SHIPPED 2026-04-30
(eight PRs: #99/#100/#101/#102/#103/#104/#105/#106). Phase 1 verified
GREEN end-to-end via the 2026-05-01 ``make smoke-m18`` run (full
specialist cascade through hephaestus → metis → techne → dokimasia
→ kallos → mneme, ``✨ Forged in 57.4s``). DX cleanup batch shipped
2026-05-01: ``[#114]`` honest rebuild-failure timer, ``[#115]`` no-voice
flag + KOURAI_TTS env + virtues fail-soft + smoke gate-ack regex,
``[#116]`` soft-fail banner also fires on pipeline abort before
mneme, ``[#117]`` uvicorn.access filter (silences Docker healthcheck
log noise — 44 lines/min cluster-wide → 0). UX/DX + CI + security
batch shipped 2026-05-02 (eleven PRs): ``[#118]`` dead
``AGENT_METADATA`` color fields dropped, ``[#119]`` Okabe-Ito CVD-safe
agent badges (closes #10), ``[#120]`` captions toggle for audio-only
dialogue mode (closes #19), ``[#121]`` apt cache for
``portaudio19-dev``, ``[#122]`` GHA layer cache for MCP Docker
builds, ``[#123]`` NO_COLOR honored across the rest of the CLI
palette, ``[#124]`` ``/aj-deslop`` sweep on recent justification
prose (-73 LoC), ``[#125]`` migrate ten agents + vn_bridge + sandbox
+ 2 MCP sidecars from python:3.12-slim → Chainguard Wolfi (closes
#98; 0 HIGH CVEs vs 1H baseline), ``[#127]`` migrate
templates/backend/Dockerfile to Wolfi so Techne-scaffolded player
projects inherit the 0-CVE base, ``[#128]`` ``/aj-deslop`` sweep on
streaming + log soft-fail + filter blocks (-24 LoC), ``[#129]``
``/aj-deslop`` sweep on CI workflow comment blocks (-21 LoC, closes
the IMPL TODO). Active focus: M18 Phase 2
(SSML inside dialogue bodies — Kokoro doesn't natively consume
SSML so transitional strip-then-synthesize, ElevenLabs migration
on M6 unblocks full SSML downstream; web-searched 2026-05-02
provider compat findings recorded in the Phase 2 section below).**

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

**Web-searched 2026-05-02 — provider compatibility constraints:**
- **W3C SSML 1.1** has been a stable Recommendation since 2010. No
  spec drift to plan against; the markup itself is durable.
- **Kokoro has zero native SSML support** (multiple open feature
  requests on `hexgrad/kokoro` and `Kokoro-FastAPI`). Strip-then-
  synthesize is the only viable path while Kokoro is the engine.
- **ElevenLabs** supports `break`, `phoneme`, `prosody`, `emphasis`
  on most models — but **NOT on Eleven v3** (their current flagship).
  If the M6 migration targets v3, SSML support is a regression vector;
  if it targets Flash V2 / Turbo V2 / English V1, full subset works.
- **Azure + Google Cloud** both support the full subset including
  `prosody` (rate/pitch/range/volume/contour), `break`, `emphasis`,
  `say-as`, `phoneme`, `sub`, `p`, `s`, `audio`.
- **Portable subset** (works across ElevenLabs-non-v3 + Azure + Google,
  i.e., the safe baseline if we want provider-fungibility): `break`,
  `prosody`, `emphasis`, `say-as`. Avoid `phoneme` if v3-on-ElevenLabs
  is on the roadmap; avoid `audio` (provider-side resource fetch).

Open questions for Phase 2:
- **Where does SSML get added — at producer, consumer, or both?**
  Producer side (specialist's ``send_input_required`` / dialogue
  emissions) means each specialist owns its prosody — Kallos's lilt
  versus Hephaestus's gruff cadence stays a per-agent concern,
  matching the Phase 1 content-kind tagging architecture. Consumer
  side (host CLI / vn_bridge wraps in default SSML) means a single
  layer controls the cadence baseline; specialists stay text-only and
  prosody is uniform. Producer-side composes better with the existing
  per-agent persona work; consumer-side is faster to ship.
- **Strip-then-synthesize layer placement.** Current Kokoro path is
  via ``kourai_common.tts_realtime.RealtimeTTSEngine``. SSML strip
  could live in the engine itself (so callers stay SSML-agnostic and
  any future engine swap inherits the strip layer) or in the host
  (so SSML is end-to-end visible in logs and the strip is explicit
  at the engine boundary). Engine-side parallels how Azure/Google SDKs
  handle SSML internally.
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

**Shipped 2026-04-30 (post-M18 Phase 1) UX/DX cleanup:**
- ``[#107]`` (#15) — empty trailing ``Project root:`` listing dropped
  from metis enriched prompt when iterdir returned no listable entries.
- ``[#108]`` (#22) — phonemizer "words count mismatch" WARN spam silenced
  via surgical filter on the ``phonemizer`` logger; only the specific
  benign-but-noisy message is dropped, other phonemizer warnings remain
  audible.
- ``[#109]`` (#17) — host CLI now renders an explicit ``⚠ No commits
  produced`` banner before "Forged in" when mneme reports
  ``commit_count: 0``. Soft-fail surface lifted from buried prose into
  a visible warning.
- ``[#110]`` — ``test_kallos`` / ``test_techne`` ``TestRunCommand`` use
  ``sys.executable`` instead of literal ``"python"``; tests pass on
  WSL2 hosts where only ``python3`` is on PATH.
- ``[#111]`` (#23) — KokoroEngine pre-warms one ``KPipeline`` per unique
  agent ``lang_code`` at init; first Techne ``bf_emma`` speech no
  longer pays the lazy-pipeline-build pause. Forward-compat — derives
  language codes from ``AGENT_VOICE_MAP`` so new languages auto-prewarm.
- ``[#112]`` (#14) — Context7 MCP wrapper updated to v2.x tool name
  (``query-docs`` not ``get-library-docs``) + new param shape
  (``libraryId``+``query``). Transcript prefixes (``[User]:``,
  ``[Hephaestus]:``) stripped from doc-lookup queries before library
  extraction so Context7 stops emitting ``[User]:`` URL placeholders.

**Shipped 2026-05-01 (DX cleanup):**
- ``[#114]`` — ``make rebuild`` no longer prints
  ``[TIMER] Target rebuild completed in 0 seconds`` when ``down`` /
  ``prune`` / ``clean`` fail in under half a second. Now: stderr names
  the failing sub-step + exit code, the timer line says
  ``aborted at '<step>'`` instead of ``completed``, elapsed prints
  with sub-second precision (``0.42s`` not ``0 seconds``). Same fix
  applied to every COMPOSITE_TASKS target (yolo, restart, dev,
  dev-vn) — the bug was copy-pasted in five places. Bonus: leaf timed
  tasks (e.g. ``make down``) report ``failed (exit N)`` instead of
  ``completed`` when the underlying command exits non-zero. Found
  while investigating a WSL2 docker daemon hiccup that was masked as
  a no-op rebuild.
- ``[#115]`` — four bundled fixes uncovered by the first M18
  full-pipeline live smoke:
  - ``hosts/cli/__main__.py``: ``--voice`` becomes
    ``--voice/--no-voice`` (Click negation idiom). The smoke driver
    had been setting ``KOURAI_TTS=off`` for unattended runs, but that
    env var was a fiction the smoke invented — the real CLI was
    gated only by ``--voice`` with no negation, so PortAudio crashed
    on first speech under WSL2 (no audio device).
  - ``shared/src/kourai_common/dev_cli.py``: ``_cli_command`` helper
    reads ``KOURAI_TTS`` env at invocation. ``off`` / ``0`` /
    ``false`` / ``no`` → ``--no-voice``; anything else → ``--voice``.
    Default behavior of bare ``make cli`` unchanged.
  - ``scripts/smoke_m18_full_pipeline.py``: gate-pattern regex
    narrowed. Previously matched ``Analyzing`` and ``Forging`` as
    "gate signals," but those are routine orchestrator status text
    that fires BEFORE the gate, causing the driver to false-skip the
    ``yes`` ack and time out at 15min. Now scoped to actual gate
    surfaces (``Light the forge?`` / ``Approve?`` / ``CONFIRM_ORDER``
    / ``Forge cooled``) with a 5-min ceiling that falls through to
    a /yolo passthrough assumption.
  - ``shared/src/kourai_common/virtues.py``: ``update_virtue`` and
    ``_get_virtues_db`` are now resilient to a readonly database. The
    Dockerfile (lines 127-133) acknowledges that container UID 1000
    writing to a host-owned UID 1001 bind-mount file is a known M5
    deferred-design issue, and patched it for git via
    ``safe.directory '*'`` — but never patched the virtues sqlite
    layer. Dokimasia's post-success ``update_virtue("arete", delta)``
    call would crash with ``sqlite3.OperationalError: attempt to
    write a readonly database``, the executor decorator wrapped it as
    ``InternalError``, and Hephaestus aborted the pipeline mid-flight
    so kallos and mneme never ran. Now: catches OperationalError,
    logs a warning identifying the M5 cause, returns the *current*
    score so callers see a sane value, pipeline continues. Virtue
    tracking is bookkeeping; a perms hiccup must not abort an
    otherwise-successful pipeline run.
- ``[#116]`` — soft-fail banner now also fires when the pipeline
  aborts before reaching mneme. The original ``[#109]`` banner only
  caught ``commit_count == 0`` (mneme ran and reported empty); the
  "mneme never reached" code path was silent. Discriminator added:
  ``commit_count is None`` AND ``final_state == TASK_STATE_FAILED``
  fires the banner with a distinct ``the forge aborted before Mneme
  could commit`` message. A legitimate non-mneme run (e.g. metis-only
  spec discussion) lands COMPLETED, so the FAILED gate separates
  "crash" from "by design." Also handles the artifact-less abort
  path: when the pipeline crashes early enough that no final artifact
  lands, the banner plus a ``Forge aborted at N.Ns`` red closing
  line surface so the stream doesn't trail off silently after the
  last specialist's status.
- ``[#117]`` (#12) — Docker healthcheck access-log noise silenced.
  Each agent's uvicorn served ``GET /.well-known/agent-card.json``
  (15s healthcheck) → ``200 OK`` INFO line, ~4 lines/min/agent × 11
  agents = 44 lines/min cluster-wide of pure chatter that drowned
  real events in ``docker logs``. Investigation found the polling is
  the right cadence for liveness recovery — only the access-log
  noise was the actual problem. New ``_UvicornAccessPathFilter`` in
  ``kourai_common.log`` installed on the ``uvicorn.access`` logger
  (logger-level, not handler-level — uvicorn configures its own
  StreamHandler outside the kourai root chain). Records at WARNING+
  pass through so a 5xx healthcheck still surfaces. Path comparison
  strips query string. Live-verified: restarted aletheia → 0
  healthcheck access lines in 30s vs 2 lines on idle peer.

**Shipped 2026-05-02 (UX/DX wins):**
- ``[#118]`` — dropped dead ``color`` and ``hex_color`` fields from
  ``shared/src/kourai_common/agents.py:AGENT_METADATA``. Three
  separate dicts independently tracked agent colors
  (``AGENT_METADATA``, ``hosts/gui/maidens.py:AGENTS``,
  ``hosts/gui/agent_personality_indicators.py``) and they all
  disagreed; nothing actually read the canonical pair. Tightened
  type annotation, updated module docstring to point at the live
  GUI palette locations. Net -19 dead lines, no behavior change.
- ``[#119]`` (#10) — per-agent Okabe-Ito CVD-safe badges in the
  comms-window header. Each maiden's name now renders as a colored-
  background chip — ``hephaestus`` orange, ``metis`` sky blue,
  ``techne`` green, ``dokimasia`` yellow (with bold-black fg for
  WCAG contrast), ``kallos`` blue, ``mneme`` mauve, ``cupid``
  vermillion, ``puck`` shares green, ``aletheia``/``aidos`` gray.
  Standards honored: NO_COLOR (no-color.org spec — strips bg+fg
  but keeps bold per spec), ``_has_truecolor`` (16-color terminals
  fall back to bold-only — no degraded approximation). Web-search
  confirmed Okabe-Ito remains the 2026 categorical-accessibility
  standard; March-2026 Claude Code issue #34702 surfaced exactly
  the "hardcoded RGB bypasses theme" failure mode the truecolor +
  NO_COLOR gates avoid. 8 new unit tests; live-rendered preview
  for all 11 agents.
- ``[#120]`` (#19) — captions toggle for audio-only dialogue mode.
  New ``captions_enabled`` setting (default ON, settings panel
  slot ``[4]``) gates whether KIND_DIALOGUE emissions render in
  the comms-window when TTS is on. Off + voice on = audio-only
  mode (dialogue still speaks, no visual clutter); voice off
  forces effective ON so dialogue is never silently dropped.
  Status / code / spec emissions and the artifact block are
  unaffected. Web-searched WCAG 2.1 + video-game accessibility
  best practices; description-density toggle deferred until
  non-dialogue audio events exist. 4 new unit tests covering
  the four-cell behavior matrix.
- ``[#121]`` — CI: ``portaudio19-dev`` apt install cached via
  ``awalsh128/cache-apt-pkgs-action@v1.6.0``. A live PR run took
  15+ min stuck on ``apt-get update`` because GitHub's Azure
  mirror was flaking; the install repeats across 4 jobs in
  ``tests.yml`` + 1 in ``nightly.yml``. Now: ~5s on cache hit
  vs. 60-120s cold (or pathological 15+ min when mirrors flake).
  Cache key ``version: 1.0`` invalidates manually.
- ``[#122]`` — CI: GHA layer cache for MCP sidecar Docker builds
  via ``docker/build-push-action@v7.1.0`` + ``docker/setup-buildx-action@v4.0.0``.
  The integration job rebuilds context7-mcp + memory-mcp images
  every run; ``cache-from: type=gha`` + ``mode=max`` reuses the
  ``FROM cgr.dev/chainguard/node:latest-dev`` and ``npm install`` layers
  across runs unless Dockerfile content changes. Separate ``scope=`` per
  image so they don't evict each other. Expected ~1-2 min saved
  per integration run on warm cache.
- ``[#123]`` — NO_COLOR honored across the rest of ``styling.py``.
  ``[#119]`` added the gate for ``agent_badge`` only; gold
  separators, red error banners, cyan emphasis still ignored
  the env var. Now: ``_GOLD`` / ``_GOLD_BRIGHT`` / ``_GREEN`` /
  ``_RED`` strip to empty under NO_COLOR; combined-style
  ``_GOLD_BOLD`` / ``_CYAN`` collapse to plain ``_BOLD`` so
  emphasis survives. ``_BOLD`` / ``_ITALIC`` / ``_DIM`` /
  ``_RESET`` unchanged per no-color.org spec.
- ``[#124]`` — ``/aj-deslop``-style sweep on the long
  justification prose in recent contributions (``#117`` log
  filter, ``#119`` badges). -73 LoC across 3 files, no
  behavior change. Kept behavior warnings + non-obvious
  invariants + env-var enumerations; cut WCAG framing
  repetition + bug-number prose + "the visible signal that
  lets the player scan a transcript" rationale. Pre-release
  stance from
  ``feedback_terse_field_comments.md``: only keep comments
  that help a reader execute, drop "why we picked this".
- ``[#125]`` (closes #98) — migrated ten agent containers +
  vn_bridge + sandbox + the two MCP sidecars from
  ``python:3.12-slim`` / ``node:20-slim`` to
  ``cgr.dev/chainguard/wolfi-base:latest`` and
  ``cgr.dev/chainguard/node:latest-dev``. CVE-2026-5435 glibc HIGH
  was unfixed in Debian's security pipeline; Chainguard's daily
  rebuild moves us to a 0-HIGH baseline. ``docker scout cves`` now
  reports ``0C 0H 0M 0L`` on every Python image vs the ``0C 1H 0M
  0L`` baseline on ``python:3.12-slim``. Architectural notes
  recorded inline as ``# research(2026-05):`` markers (new
  convention — see
  ``feedback_research_comment_convention.md``):
  ``wolfi-base`` chosen over ``cgr.dev/chainguard/python:latest-dev``
  because the free public-tier python image tracks 3.14 and our
  pyproject pins ``<3.14``; ``espeakng-loader`` manylinux wheel
  bundles ``libespeak-ng.so`` so vn_bridge runs without the
  missing-from-Wolfi system espeak-ng. Filed issue #126 for
  ``@xmldom/xmldom@0.8.12`` HIGH CVE bundled inside ``npm
  11.13.0`` itself — upstream-blocked, not exploitable in our
  threat model (xmldom only sees npm-internal config XML, never
  agent / network input).
- ``[#127]`` — migrated ``templates/backend/Dockerfile`` to the
  same Wolfi shape so every Techne-scaffolded player project
  inherits the 0-CVE base. Smoke-built in a tmp dir + ``uv
  lock``; image builds clean, ``python --version`` reports
  3.12.13 in the runtime, ``docker scout`` reports ``0C 0H 1M
  0L`` (one medium on pip 26.0.1, no high). Plus the two stale
  ``node:20-slim`` references the parent migration left behind
  in ``IMPL.md`` and the ``.github/workflows/tests.yml`` GHA
  layer-cache comment.
- ``[#128]`` — ``/aj-deslop`` sweep on
  ``hosts/cli/streaming.py`` soft-fail + M18 TTS comment blocks
  and ``shared/src/kourai_common/log.py`` format-string
  commentary. Same pre-release stance as ``[#124]``. Cuts
  task-context rot (``# M13 fix —``, ``# Soft-fail surface
  (#17, #109 follow-up):``), narrative restatement (``the two
  ways that can happen:`` followed by an enumeration the
  ``if``/``elif`` already shows), and what-comments
  (``# Handle input_required —``, ``# Post-output suggestions``,
  ``# Extract the status message``). Keeps non-obvious
  invariants — COMPLETED + 0 commits is a legitimate non-mneme
  run; FAILED + no commit_count is the crash discriminator;
  ``Path.cwd()`` = ``/app`` fall-through if ``project_root``
  metadata is dropped; 32-char hex matches Jaeger UI for Dozzle
  grep. -24 LoC.
- ``[#129]`` — ``/aj-deslop`` sweep on
  ``.github/workflows/tests.yml`` + ``nightly.yml``. The
  apt-cache rationale was duplicated five times across the two
  files (one per job); the GHA layer-cache comment in the
  integration job carried the same self-evident "first run
  populates, subsequent runs reuse" framing. Cuts cache-hit
  timings that don't trace to ``tests/performance/`` (per
  ``slop_ground_truth``); keeps PyAudio/PortAudio dep,
  ``mode=max`` rationale (npm install is its own layer we want
  back across runs), and the ``-m "not slow"`` Kokoro-skip
  explanation. -21 LoC. Closes the ``/aj-deslop`` IMPL TODO
  across all three originally-noted targets (#124 + #128 + #129).

**2026-05-01 full-pipeline smoke — GREEN end-to-end:** First
successful run of ``make smoke-m18`` against M18-Phase-1-rebuilt
containers. All five specialists fired:

| Specialist | Panel hits | Outcome |
|---|---|---|
| Hephaestus | 10 | analyzed, gated, routed, narrated handoffs |
| Metis | 12 | full spec output |
| Techne | 11 | wrote ``src/math.py`` + ``tests/test_math.py`` |
| Dokimasia | 12 | ``1 passed in 0.02s`` |
| Kallos | 9 | "All linting checks passed!" |
| Mneme | 6 | generated 2 commit groups |

Final signature: ``✨ Forged in 57.4s``. Full transcript at
``logs/smoke-m18-20260501-091432Z.log``.

The defensive virtues code (``[#115]``) fired exactly as designed —
both dokimasia (arete) and kallos (techne_v) hit the readonly-DB
write path, both logged the M5-cause warning, both continued. Pipeline
survived; previously this was where the forge crashed.

This run validates:
- M18 Phase 1 content-kind metadata flow end-to-end (all 11
  agent-card surfaces verified earlier; this run confirms the
  structural pipeline)
- ``[#107]`` empty Project root, ``[#108]`` phonemizer noise (TTS off
  for unattended), ``[#109]`` soft-fail banner (correctly NOT firing
  because the run produced 2 commit groups), ``[#111]`` Kokoro
  pre-warm (N/A under voice-off), ``[#112]`` Context7 wrapper
- ``[#114]`` "failed (exit N)" timer on the credit-error abort path
  earlier in the night
- ``[#115]`` no-voice flag + KOURAI_TTS env honor + smoke gate-ack
  + virtues fail-soft

Open follow-ups surfaced by the smoke (small PR shapes each):
- M5 root-cause UID alignment is still the proper architectural
  fix; ``[#115]`` makes the application layer resilient in the
  meantime.

**Independent UX bugs (still open):**
- Music playlist sparse — 2 tracks (#11) — content-driven; AJ
  adds tracks to ``assets/audio/music/`` over time. No code work.

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

1. **M18 Phase 2 — SSML inside dialogue bodies.** Web-search 2026 SSML
   best practice (W3C SSML 1.1 status, ElevenLabs/Azure provider
   subset compatibility) before any implementation. Decide
   producer-vs-consumer SSML wrapping.
2. **M18 Phase 3 — KIND_CODE / KIND_SPEC distinct render paths.** Drop
   the ``or kind is None`` legacy fallback now that the 2026-05-01
   GREEN smoke confirmed no untagged emissions in production. Wide
   markdown render for spec, monospace + syntax highlighting for code.
3. **M20 — Audio-text synchronization.** Builds on M18 (kind routing)
   + M19 (RealtimeTTS word-timing API already wired via ``on_word=``
   callback). 9-14s text-precedes-audio gap is a player-notices UX
   issue.
4. **Remaining independent UX bugs** — playlist expansion (#11)
   only, and that's content-driven (AJ adds tracks over time, no
   code). Per-agent badges (#10) and captions toggle (#19) closed
   by [#119] and [#120].
5. **Live VN smoke** — exercises the new vn_bridge ``/tts`` →
   ``RealtimeTTSEngine.synthesize_to_wav`` path AND the new
   metadata-based dialogue routing.
6. **``docs/architecture/puck-first-run-tutorial.md``** — pairs with
   the M6 player-onboarding theme.
7. **M5 / M12 / M15 / M6 follow-ons** — see ROADMAP for scope.
