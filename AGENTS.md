# AGENTS.md — Kourai Khryseai

Repository conventions for agentic coding tools (Claude Code, Cursor,
Codex, Aider). For human contributors, start with the
[docs site](https://ajbarea.github.io/kourai-khryseai/) and
[`README.md`](README.md). For deeper Copilot-specific architecture
notes, see [`.github/copilot-instructions.md`](.github/copilot-instructions.md).

## Build & run

`uv run kourai-dev <command>` is the canonical entrypoint; `make`
targets wrap it.

| Goal | Command |
|---|---|
| Install workspace deps | `make setup` |
| Start full stack (10 agents + vn-bridge + Jaeger / Prometheus / MCP sidecars) | `make up` |
| Stop / rebuild / status | `make down` / `make rebuild` / `make status` |
| Interactive hosts | `make cli` · `make gui` · `make vn` |
| Local docs server | `make docs` |

`make help` enumerates all targets.

## Testing

| Goal | Command |
|---|---|
| Unit tests (parallel, hermetic) | `make test-unit` |
| Integration tests (boots Docker compose) | `make test-integration` |
| Performance tests (latency-sensitive) | `make test-performance` |
| Combined with lint pre-flight | `make test` |

Single test invocation: `uv run pytest tests/unit/test_X.py::test_name -q`.
Integration tests are marked `@pytest.mark.integration`.

## Lint, format, types

`make lint` runs **ruff format --check + ruff check + ty check** in
sequence. **Skipping the wrapper skips ty.** `make fix` auto-applies
ruff format + safe + unsafe fixes (ty has no auto-fix). Use `make
validate` (= `lint + test-unit`) before pushing.

## Conventions

- **Type hints**: modern (`X | None`, lowercase `list` / `dict`); 100-char lines.
- **Docstrings**: Google style — public = one-liner + Args/Returns; private = one-liner; inner = none.
- **Comments**: WHY not WHAT. Use the kourai-specific `# research(YYYY-MM): ...` inline tag when citing the period a design choice was researched.
- **No marketing language** — `robust`, `comprehensive`, `elegant`, `best-practice`, `production-ready`, `seamless`, `effortlessly`. Aidos enforces this on every prompt.
- **Specific exceptions only** — never bare `except`; `raise from None` when appropriate.
- **No `pip` / no `python -m venv`** — `uv` only. Workspace pyproject is at the root.
- **No git commits from inside agent runs** — Mneme drafts messages but never executes; `git commit` / `git push` / `git tag` are forbidden mid-pipeline.

## Architecture in three lines

10 agents on A2A (`agents/*`) + 1 Ren'Py bridge (`agents/vn_bridge`) +
3 hosts (`hosts/{cli,gui,vn}`) + shared library
(`shared/src/kourai_common/`) + 2 MCP servers (`mcp_servers/`).
Hephaestus is the orchestrator; specialists hold the **Forge
Transcript** the whole way through. Detailed patterns in
[`docs/architecture/`](docs/architecture/index.md), including the
**Monitor / Communicate / Control** pillar mapping that the poster
abstract names.

## Security & performance

- **API keys** via `.env`; `.env.example` is the placeholder template. Never commit a real key.
- **Sandboxed forge tools** via `KOURAI_SANDBOX=container` route every agent-issued shell call through a locked-down `--network=none` container.
- **Performance harness**: `tests/performance/test_performance_profiler.py` is the single source of truth for any quantitative perf claim. Anything else is unsupported.
- **Prompt caching**: split into `[truly-static (1h TTL), player-dynamic (5m TTL)]` blocks per [Anthropic's caching guidance](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) (verified May 2026; the 1h TTL is opt-in since the 2026-03-06 default change).
