# skill-context — kourai-khryseai

Repo-specific facts for canonical skills under `~/.claude/skills/`. Injected
into each skill at invocation via `!cat .claude/skill-context.md`. Update on
toolchain / path / tooling changes.

## repo

- name: kourai-khryseai
- package_root: multi-module — `agents/` (`dokimasia`, `hephaestus`, `kallos`, `techne`), `hosts/cli/`, `hosts/gui/`, `mcp_servers/`, `shared/src/`, `scripts/`
- language: Python
- cli_entrypoint: `kourai-dev` (invokes make/dev targets)
- runner_module: `kourai-dev` session logger (writes `logs/dev-<ts>-<cmd>.log`)
- has: docker-compose stack, GUI host, MCP servers; no Rust, no frontend

## audit

Full audit = 10 `make` targets, in order:

### Phase 1 — Setup
1. `make clean` — wipes `__pycache__`, `.ruff_cache`, `.pytest_cache`, build/dist, old `logs/dev-*-*.log` archives.
2. `make check-env` — uv, Python, Docker on PATH.

**Do not** run `make setup` / `make setup-artifacts` as part of the audit — they are interactive (HF Storage Bucket stdin prompt) and mutate external state.

### Phase 2 — Fix (one-way door)
3. `make fix` — `ruff format`, `ruff check --fix --unsafe-fixes`. (`ty` has no auto-fix; only runs in the check pass.)

### Phase 3 — Granular lint (single archive; no lint-py / lint-rs split since kourai is Python-only)
4. `make lint` — `ruff format --check`, `ruff check`, `ty check` across `agents`, `hosts/cli`, `hosts/gui`, `mcp_servers`, `scripts`, `shared/src`, `tests`.

### Phase 4 — Granular test
5. `make test-unit` — `pytest -m "not integration and not performance"`, parallel. Fast, hermetic.
6. `make test-integration` — `pytest -m integration`. **Side-effectful**: auto-starts Docker via `docker compose up` and may leave containers running. Skip if user said "don't touch Docker" or `check-env` reported Docker missing.
7. `make test-performance` — `pytest -m performance`. Latency-dependent; only `rc ≠ 0` is a failure.
8. `make test` — combined suite. Redundant with 5+6+7 but catches ordering / fixture-leakage issues.

### Phase 5 — End-to-end gates
9. `make validate` — `lint + test-unit`. "Am I ready to push" probe.
10. `make audit` — `pip-audit` (falls back to `uv audit`) for CVEs. **Informational**, not a gate — report counts.

Fast audit = `clean → check-env → fix → validate`. Four commands.

Stop-early phase: Phase 1 (clean / check-env). Also: if `make fix` fails with a real tool error (not "nothing to fix"), stop — the check pass won't have a clean baseline.

Log archive: `logs/dev-<YYYYMMDDTHHMMSS>-<cmd>.log` + pointer `logs/dev-runner-latest.log`.
Do **not** read `dev-runner-latest.log` (overwritten each invocation).

Do-not-run targets (interactive, long-running, or destructive):
- `make docs` (zensical serve), `make gui`, `make cli`, `make vn`, `make dev`, `make dev-vn`
- `make up` / `make down` / `make restart` / `make rebuild` / `make prune` / `make status` (docker-compose lifecycle — `test-integration` already exercises the container path)
- `make setup` / `make setup-artifacts` / `make upgrade` (interactive or lock-mutating)
- `make yolo` (destructive)

Cross-archive sweep also looks for `CVE-` hits from step 10 — report counts, informational only.

## ci_audit

Referenced configs a CI failure can trace to:
- `pyproject.toml`
- `Makefile`
- `scripts/*.py`
- `docker-compose.yml`, `docker/sandbox.Dockerfile`

Tool error markers (extend the default grep set):
- `pytest`, `ruff`, `ty` (lint/test)
- `pip-audit` (advisory findings; informational)
- `docker` / `compose` (integration-test container errors)

## slop_ground_truth

Source of truth for numeric performance / scale claims:

- Performance harness: `tests/performance/test_performance_profiler.py` (primary, and currently the only measured source — no `make baselines` equivalent)

Any quantitative perf/scale claim not traceable there is slop.

## scan_scope

Skip paths:
- `.venv/`, `node_modules/`, `dist/`, `build/`, `site/`, `out/`
- `__pycache__/`, `.ruff_cache/`, `.pytest_cache/`, `.hypothesis/`
- `uv.lock`, `assets/`, `templates/` (if user-generated content only), `docs/assets/`, `logs/`
- `tools/` if vendored third-party; audit case-by-case

Subagent scan-area split:
- Agents: `agents/**/*.py` (one subagent per agent dir if large: `dokimasia/`, `hephaestus/`, `kallos/`, `techne/`)
- Hosts: `hosts/cli/**/*.py`, `hosts/gui/**/*.py`
- MCP servers: `mcp_servers/**/*.py`
- Shared: `shared/src/**/*.py`
- Scripts and tests: `scripts/**/*.py`, `tests/**/*.py`
- Config/build: `pyproject.toml`, `Makefile`, `.github/workflows/**`, `zensical.toml`, `docker-compose*.yml`, `docker/**/Dockerfile`, `.vscode/**`
- Docs (opt-in): `docs/**/*.md`

## theoros

```yaml
repl_command: make cli
session_name: kourai-theoros
ops_command: docker compose logs -f --tail 0 metis mneme hephaestus
prerequisites:
  - command: docker compose ps --status running --quiet | grep -q .
    message: "Core containers not running. Run 'make up' first."
```

**Aesthetic vs operational responsibility** — the human judges left column, Claude observes right column:

| Aesthetic (AJ's eyes/ears) | Operational (Claude via logs) |
|---|---|
| Does Metis's voice sound natural? | Did Metis receive the request? |
| Does recall narration feel earned? | Did `narration emitted` fire? |
| Does audio crackle / clip? | What sample rate did pygame init at? |
| Does the comms-window layout look right? | What was the box width / content length? |
| Does the chat feel coherent across turns? | What did Hephaestus's user-message body contain? |

The `ops_command` services list is curated per session — adjust for the agents you're exercising. The full agent set is `metis mneme kallos dokimasia puck cupid aidos aletheia hephaestus vn-bridge`.

## working_docs

- **ROADMAP.md** and **IMPL.md** in this repo are editable working docs — the "Kourai creative latitude" rule. Rewrite anything that doesn't feel perfect; treat them as persistent scratchpads, not read-only canon. (Cross-project rule lives in `~/.claude/CLAUDE.md`; this section confirms it for kourai.)
- **Demo targets vs interactive targets**: `make cli-demo` / `gui-demo` / `vn-demo` are **scripted** (used for poster screenshots, deterministic output) — those are the right invocations for a demo capture. `make cli` / `gui` / `vn` are **interactive** (player REPL / pygame loop / Ren'Py loop) — listed under "Do-not-run" for skill use, but right for live development. Never confuse them when generating poster artifacts.

## ci_pipeline

- **Pre-push gate is `make lint`** — not file-scoped `uv run ruff check <files>`. The wrapper at `scripts/lint.py` runs `ruff format --check`, `ruff check`, AND `ty check` in sequence; skipping the wrapper skips `ty` entirely, and file-scoped invocations miss repo-wide drift in unrelated files. Always run `make lint` (or `make validate` for lint + unit tests) before `git push`. Both write a SUMMARY block in `logs/dev-<ts>-<cmd>.log` — verify `overall rc : 0` and `steps failed : 0` before pushing.
- **Both `ruff format --check` AND `ruff check` are separate gates** — `make lint` runs both. Even if I only ran `ruff format` locally, the check pass can still fail and CI will catch it.
- **Nightly threshold:** any CI suite >5 min belongs in `nightly.yml` (cron-scheduled). The push/PR fast lane stays under that. The nightly job already covers integration tests; new heavy suites should follow the same pattern (see `.github/workflows/nightly.yml`).

## design_north_stars

- **Player experience is load-bearing** — every system change should be evaluated against "does this make the player journey better." Architectural moves that don't reach the player aren't worth the same scrutiny.
- **DE/ME inspirations are explicit** — Dating-Sim and Mecha-Engineer reference points (comms windows, callsign labels, romance arcs, READY/WAIT semaphores) should be obvious in design choices. Don't bury them.
- **Search latest FL practice constantly** when touching M11+ paper work — Kourai is FL-research-adjacent and the field moves weekly. Re-grep recent papers / framework releases before committing to a design.
- **No system is too late to redesign.** If a feature isn't carrying its weight, rip it out — even shipped ones. Sunk-cost is not a reason to keep code.

## observability

- The dev-loop observability triad is **Jaeger** (traces, `:16686`) + **Prometheus** (metrics, `:9090`) + **Dozzle** (per-container live tail, `:8888`). `make observe` opens all three.
- Before designing any observability change (new spans, metrics, log enrichment, dashboard layout, or container-grouping decision), read [`docs/observability.md`](../docs/observability.md) — it carries the mental model (trace=flow / metric=aggregate / log=narrative), the four-pattern triage runbook, and the "what's currently populated, and what's not" honesty section. Avoids re-deriving design rationale that was load-bearing in M16.
- Jaeger is on `jaegertracing/jaeger:2.17.0` (OTel-Collector-shape config in `docker/jaeger-config.yaml`); Prometheus on `prom/prometheus:v3.11.3-distroless`; spanmetrics connector emits RED metrics on `:8889`. Bumping any of these pins → web-search current best practice first (caught two deprecations in M16 that recall would have missed).
- Trace-ID injection into log lines is shipped (`shared/src/kourai_common/log.py::_OtelTraceFilter`); a span found in Jaeger is grep-findable in Dozzle as `trace=<id>` without code changes between observation and search.

## renpy

- VN host (`hosts/vn/`) targets **Ren'Py 8.5.x**. My recall keeps producing Ren'Py 6.x APIs that crash. **Always resolve API questions via context7** (`mcp__claude_ai_Context7__query-docs` against `renpy`) before writing `config.*` settings, init priorities, or special screen overrides (`screen main_menu`, `screen game_menu`, etc.). Don't trust my pattern-match for anything 6.x-vs-8.x sensitive.

## docs_site

- config: `zensical.toml`
- workflow: `.github/workflows/docs.yml`
- css_files: modular — `docs/stylesheets/variables.css`, `base.css`, `mermaid.css`, plus `components/hero.css`, `components/landing.css`, `components/lightbox.css`
- js_files: `docs/javascripts/particles.js`
- build_command: `uv run zensical build --clean`
- site_url: `https://<owner>.github.io/kourai-khryseai/`
- action_pins (expected current): `actions/checkout@v6.0.2`, `astral-sh/setup-uv@v8.1.0`, `actions/setup-python@v6.2.0`, `actions/configure-pages@v6.0.0`, `actions/upload-pages-artifact@v5.0.0`, `actions/deploy-pages@v5.0.0`
- nav structure: nested ("Agents", "Architecture", "Interfaces" each with sub-pages)
