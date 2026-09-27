# Web GUI (Host B) — Scope & Design

**Status:** Proposed · **Date:** 2026-06-14 · **Decisions baked in:** frontend = vanilla + [lit](https://lit.dev) Web Components; v1 = full interactive GUI.

This scopes a browser-based GUI host for Kourai Khryseai: a third front-end alongside the CLI and the pygame GUI that runs the *same* forges, served locally with zero install for the frontend. It is deliberately a **client** of the existing backend — it adds no orchestration.

---

## 1. Goal & non-goals

**Goal.** From a browser, a player can: type a request; watch Hephaestus route it and the maidens stream their plan → code → test → review → commit in real time with portraits and handoffs; answer decision points (the `CONFIRM_ORDER` gate and planner questions); manage projects and accept/discard git-worktree forge sessions; and toggle `yolo`/permissions — with the affinity HUD and (optional) neural TTS the GUI already has.

**Non-goals (v1).** No new agent logic. No remote/multi-tenant hosting, no auth, no TLS (localhost trust boundary, per `docs/security.md`). No AgentRQ-style persistent task board or phone notifications — that is v2 and pulls in the remote/auth layer.

---

## 2. Key insight — the bridge is already the backend

The agents speak **A2A 1.0 (JSON-RPC + protobuf wire shape) over HTTP** via `shared/src/kourai_common/server.py:build_a2a_app()`, served by uvicorn (Hephaestus on `:10000`, specialists `:10001–10009`). Reimplementing an A2A client in the browser would be heavy and brittle — that SDK is Python-centric.

We don't have to. **`agents/vn_bridge` (`:10010`) already exposes a browser-friendly facade** that the Ren'Py VN consumes today:

- `POST /message` → **NDJSON stream** of `{agent, message, portrait, action}` (the forge, sentence-paginated), and accepts `{action:"choice", choice:"…"}` for decisions.
- `POST /action` → synchronous JSON ops (`get_profiles`, `create_profile`, `resume`, `get_virtue_context`).
- `POST /tts` → WAV bytes + `X-TTS-Duration-Seconds` header (Kokoro/Edge).
- `POST /gossip` → idle single-agent chatter.
- `POST /health` → liveness (`503` if A2A unreachable).

It already forwards forge metadata (`project_root`, `relationship_tiers`) to Hephaestus. So the web GUI is **"another client of the bridge,"** exactly like the VN — not a new transport.

**Recommendation:** evolve `agents/vn_bridge` into a shared **host gateway** consumed by both the VN and the web GUI. The web GUI then needs almost no new backend: CORS, static-file serving, a handful of project/session actions wrapping the existing `ProjectManager`/`ForgeSession`, and one explicit "decision required" stream event.

---

## 3. Architecture

```
        Browser (lit SPA, static bundle)
   forge terminal · pipeline rail · affinity HUD
   prompt box · decision modal · project tray
                  │  fetch + ReadableStream (NDJSON)   ┌ /message  (stream)
                  │  fetch JSON                        ├ /action   (projects, profiles)
                  ▼                                    ├ /tts      (WAV)
        Host Gateway  (evolved vn_bridge, :10010)      └ /health
   CORS · serves the web bundle · projects/sessions
                  │  A2A 1.0 (RemoteAgentConnection)
                  ▼
        🔥 Hephaestus :10000  ──A2A──▶  Metis…Mneme :10001–10009
                  │
        MCP (forge · shell · memory · context7) · OTel → Jaeger/Prometheus/Dozzle
```

The functional app is **served by the gateway** (same origin, `http://localhost:10010/`), so there is no CORS or mixed-content problem at runtime (see §9). GitHub Pages keeps only the public **(A) demo**.

---

## 4. Transport decision

| Option | Verdict | Why |
|---|---|---|
| **Extend the bridge; browser ↔ NDJSON/JSON** | **Chosen** | Bridge already does 90%; plain JSON is trivial from `fetch`; the VN proves the shape; one place to maintain. |
| Browser → raw A2A at `:10000` | Rejected | A2A JSON-RPC + protobuf is SDK/Python-centric; reimplementing in JS is large and fragile; needs CORS on every agent. |
| New standalone web-gateway service | Defer | This *is* the bridge, refactored. Do the refactor in-place (§5) rather than add a parallel service. |

**Streaming on the wire:** keep NDJSON over a single `POST /message` read with `ReadableStream` + `TextDecoderStream` (works through the existing response, no SSE reconnect semantics needed for a request-scoped forge). Offer an SSE variant later only if we want server-initiated pushes (that's the v2 notifications path).

---

## 5. Backend changes (small, DRY)

All additive; none touch agent logic.

1. **CORS for dev** — add Starlette `CORSMiddleware` to the gateway, allow-list `http://localhost:5173` (and the gateway's own origin). Production is same-origin, so this only matters for hot-reload dev.
2. **Static serving** — mount the built web bundle at `/` (e.g. `StaticFiles(directory="web/dist", html=True)`), so the gateway serves the GUI same-origin.
3. **Project/session actions** on `/action`, thin wrappers over existing `shared/src/kourai_common/projects.py` and `forge_session.py`: `list_projects`, `new_project{name,template}`, `use_project{id}`, `list_sessions{project_id}`, `accept_session{session_id}`, `discard_session{session_id}`. Logic already exists (CLI uses it) — reuse, don't reimplement.
4. **Explicit decision event** — ensure `/message` emits a typed event when Hephaestus returns `INPUT_REQUIRED`, e.g. `{action:"input_required", kind:"confirm_order"|"question", prompt, order?, options?}`, so the web modal has structured data instead of parsing prose. Reply path already exists (`{action:"choice"}` / a follow-up `{text}` with the same `context_id`).
5. **Carry `content_kind`** — surface the existing `content_kind` tag (`dialogue|status|code|spec`) on stream events so the client can route bubbles vs. monospace vs. TTS without re-sniffing emoji.

To keep the VN and web in lockstep, factor the A2A→event translation through the existing `shared/src/kourai_common/a2a_events.py` extractors (single source of truth). Consider renaming `vn_bridge` → `host_gateway` once the web client lands (keep an alias to avoid breaking the VN launcher).

---

## 6. Frontend (vanilla + lit, buildless)

**Stack.** lit Web Components, ES modules, no framework runtime. **Buildless by default** to match periplus: an import-map resolves `lit` to **vendored, offline ESM** under `web/vendor/lit/` (no CDN at runtime). Shipped 2026-06-15 via `web/scripts/vendor-lit.sh` — an `esbuild` split-bundle (not the single file first sketched here) so the `lit` core and the `lit/directives/repeat.js` subpath share one lit-html copy; separate bundles would duplicate lit-html and break directive recognition.

**Reuse what's built.** The (A) demo's forge theme (gold/charcoal CSS variables), the streaming/typewriter feel, the pipeline rail, the affinity HUD, and the real portraits (`docs/assets/avatars/*_neutral.png`) all carry straight over — the demo was effectively the visual prototype for this host.

**Components (custom elements):**

- `<kk-app>` — shell, routing, gateway base-URL config, health banner.
- `<kk-terminal>` — the fixed-height forge window (same lock as the demo: internal scroll, no page jump) rendering the live transcript.
- `<kk-pipeline-rail>` — Metis→Mneme nodes; active/done from stream events.
- `<kk-message>` — portrait + name + role + body; variants for `dialogue|status|code|spec`.
- `<kk-prompt>` — request input, image attach, `@agent` targeting, speed/voice toggles.
- `<kk-decision>` — modal for `input_required` (CONFIRM_ORDER order text + approve/deny; planner questions + options/free text).
- `<kk-affinity-hud>` — per-maiden meters; animates on `action:"jealousy"`.
- `<kk-projects>` — project switcher + template picker; `<kk-session-tray>` — active worktrees with accept/discard.
- `<kk-settings>` — `yolo`, `auto_approve_reads`, TTS on/off, reduced-motion.

**State.** A small reactive store (a lit `ReactiveController` or a ~50-line signal store) holding `connection`, `transcript`, `pipeline`, `affinity`, `activeProject`, `sessions`, `settings`. Persist `settings` + `affinity` in `localStorage`, or via gateway player profiles (`/action get_profiles`) for cross-device parity later.

**Streaming client** (`web/src/gateway.js`) mirrors `hosts/gui/client.py`'s queue/event loop in JS: `POST /message`, read the NDJSON via `ReadableStream`+`TextDecoderStream`, dispatch typed events to the store. `INPUT_REQUIRED` opens `<kk-decision>`; the reply re-posts with the same `context_id`.

**Audio.** Optional TTS: on a `dialogue` line, `POST /tts` → play the WAV via Web Audio, gated by a settings toggle and `X-TTS-Duration` for caption sync.

---

## 7. Backend event → UI mapping

| Stream event | UI effect |
|---|---|
| `{agent, message, portrait, content_kind:"dialogue"}` | `<kk-message>` speech bubble; portrait state; eligible for TTS |
| `content_kind:"status"` (e.g. "🔥 Pipeline: metis → techne…") | rail advance + faint status line |
| `content_kind:"code"|"spec"` / artifact text | monospace diff/spec block |
| `action:"input_required"` | open `<kk-decision>` (approve/deny or answer); reply via `context_id` |
| `action:"jealousy" {agent, score}` | bump/animate affinity meter |
| `action:"status"` final / Task complete | mark pipeline done; enable replay/new request |
| `action:"error"` / `/health` 503 | error banner; offer retry / "is the backend up?" |

---

## 8. Projects & sessions UX

`<kk-projects>` lists projects (`/action list_projects`), creates from a template (`empty|python|node|backend|frontend`), and sets the active one (its `project_root`/`project_id` ride along on every `/message`). Each forge runs in a `forge/…` worktree; `<kk-session-tray>` shows active sessions with **Accept** (fast-forward into `main`) and **Discard** (drop the worktree) — the same `ForgeSession.accept()/discard()` the CLI uses. This makes the human-on-the-loop merge gate visual, which the terminal CLI can't.

---

## 9. Deploy & the mixed-content rule

The one hard browser constraint: an `https://` GitHub Pages page **cannot** call `http://localhost:10010` (mixed content, and cross-origin). Resolution:

- **Functional app:** served by the gateway itself at `http://localhost:10010/` — same origin, same scheme → no mixed content, no CORS. Launch with a new `uv run kourai-dev web` (starts the stack if needed, opens the browser).
- **GitHub Pages:** hosts only the public **(A) demo** + a landing that explains "to run the real thing locally, `uv run kourai-dev web`." Pages never tries to reach localhost.

This is the same split I recommended earlier: Pages = shopfront, gateway = the working kitchen.

---

## 10. Security posture

Consistent with `docs/security.md` (single-host, single-developer today):

- Bind the gateway to `127.0.0.1` only; do not expose `0.0.0.0` by default.
- CORS allow-list is dev-only; production is same-origin.
- The browser holds **no secrets** — API keys stay server-side in the agents.
- `yolo` and `auto_approve_reads` are powerful: keep them **off by default**, surface the confirm gate prominently, and show a persistent "YOLO on" banner when enabled. The web UI must not make auto-approval the path of least resistance — that's the exact guardrail that separates Kourai from the AgentRQ pitch.
- Remote access (approve-from-phone, hosted) is **out of scope**; when wanted, it gates on OAuth 2.1 + PKCE + a tunnel/relay (the doc's §13 v2), aligning with the `docs/security.md` TLS/OAuth target — and is the point where "Sign in with Google" finally earns its place.

---

## 11. Milestones

| # | Deliverable | Effort | Acceptance |
|---|---|---|---|
| **M1** | Gateway-ready: CORS + static mount + `/health`; `host_gateway` alias | S | Browser loads a page served by the gateway; `/health` green; VN still works |
| **M2** | Live viewer: lit shell + streaming client; rail, transcript, portraits, affinity | M | Type a prompt, watch a real forge stream end-to-end in the browser |
| **M3** | Interactive control: prompt box, `<kk-decision>` for `input_required`, yolo/permissions | M | Complete a forge that hits a CONFIRM_ORDER **and** a planner question, fully from the browser |
| **M4** | Projects & sessions: `/action` ops + `<kk-projects>`/`<kk-session-tray>` | M | Create a project, forge into a worktree, accept/discard from the browser |
| **M5** | Polish: TTS toggle, reduced-motion, mobile layout, `kourai-dev web`, offline shell | S–M | Install-quality UX; a11y pass; one-command launch |
| **M6** | (Optional) trimmed demo build to Pages + deep-link to local | S | Pages landing links cleanly to the local app |

Rough order-of-magnitude: a working **M1–M3 vertical slice** is the bulk of the value (watch + drive a real forge in the browser); M4–M5 make it a true GUI replacement.

---

## 12. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Mixed-content / CORS | Serve the app from the gateway (same-origin); Pages hosts demo only (§9) |
| Bridge becomes critical path for VN **and** web | Share the `a2a_events` extractors; add contract tests for the NDJSON shape; keep the VN green in CI |
| Event fidelity vs. CLI (content_kind, input_required) | Add the typed events in §5; parity-test against `hosts/cli` output |
| Buildless lit drift / offline | Vendor lit as a single ESM file; optional service worker for offline shell |
| Security footgun (browser exposes yolo/auto-approve) | Off by default, visible banner, confirm gate stays (§10) |
| Scope creep into board/notifications/remote | Hard line: v1 = full interactive local; everything else is v2 |

---

## 13. v2 and beyond

Once the local GUI lands, the AgentRQ-good-ideas slot in naturally on top of the same gateway: a persistent **task board** + run history (needs durable storage — the in-memory A2A task store becomes SQLite), **async notifications** ("Metis needs a decision") via SSE/Web Push for approve-from-phone, **remote access** (tunnel + OAuth 2.1/PKCE), and **cross-device VN/affinity sync** via player profiles — the first place "Sign in with Google" is worth the cost.

---

## 14. Open decisions

- **Buildless vs. esbuild:** ship buildless (vendored lit) first; add esbuild only if bundle size/DX warrants.
- **Rename `vn_bridge` → `host_gateway`:** do it with the web client, keep an alias for the VN launcher — or defer to avoid churn. (Recommend: rename, alias.)
- **App location:** `web/` at repo root (sibling to the demo `app/`), or `hosts/web/`. (Recommend: `web/`, since it's not a uv/Python package.)
- **Affinity persistence:** `localStorage` (simplest) vs. gateway player profiles (cross-device, reuses VN's profile DB). (Recommend: profiles, reusing existing infra.)
