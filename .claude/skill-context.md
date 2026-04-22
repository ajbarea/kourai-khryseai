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

## audit (aj-audit)

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

Log archive: `logs/dev-<YYYYMMDDTHHMMSS>-<cmd>.log` + pointer `logs/dev-latest.log`.
Do **not** read `dev-latest.log` (overwritten each invocation).

Do-not-run targets (interactive, long-running, or destructive):
- `make docs` (zensical serve), `make gui`, `make cli`, `make vn`, `make dev`, `make dev-vn`
- `make up` / `make down` / `make restart` / `make rebuild` / `make prune` / `make status` (docker-compose lifecycle — `test-integration` already exercises the container path)
- `make setup` / `make setup-artifacts` / `make upgrade` (interactive or lock-mutating)
- `make yolo` (destructive)

Cross-archive sweep also looks for `CVE-` hits from step 10 — report counts, informational only.

## ci_audit (aj-ci-audit)

Referenced configs a CI failure can trace to:
- `pyproject.toml`
- `Makefile`
- `scripts/*.py`
- `docker-compose.yml`, `docker/sandbox.Dockerfile`

Tool error markers (extend the default grep set):
- `pytest`, `ruff`, `ty` (lint/test)
- `pip-audit` (advisory findings; informational)
- `docker` / `compose` (integration-test container errors)

## slop_ground_truth (aj-deslop / aj-reslop / aj-docsync)

Source of truth for numeric performance / scale claims:

- Performance harness: `tests/performance/test_performance_profiler.py` (primary, and currently the only measured source — no `make baselines` equivalent)

Any quantitative perf/scale claim not traceable there is slop.

## scan_scope (aj-deslop / aj-reslop)

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

## docs_site (aj-docs-site)

- config: `zensical.toml`
- workflow: `.github/workflows/docs.yml`
- css_files: modular — `docs/stylesheets/variables.css`, `base.css`, `mermaid.css`, plus `components/hero.css`, `components/landing.css`, `components/lightbox.css`
- js_files: `docs/javascripts/particles.js`
- build_command: `uv run zensical build --clean`
- site_url: `https://<owner>.github.io/kourai-khryseai/`
- action_pins (expected current): `actions/checkout@v6.0.2`, `astral-sh/setup-uv@v8.0.0`, `actions/setup-python@v6.2.0`, `actions/configure-pages@v6.0.0`, `actions/upload-pages-artifact@v5.0.0`, `actions/deploy-pages@v5.0.0`
- nav structure: nested ("Agents", "Architecture", "Interfaces" each with sub-pages)
