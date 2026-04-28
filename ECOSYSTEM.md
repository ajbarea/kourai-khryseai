# kourai-khryseai — Dependency Rationale

Why each dep exists, what it's load-bearing for, and when to reconsider.
The `pyproject.toml` files (plural — see "Workspace layout") are the source
of truth for *what*; this file is the source of truth for *why*.

Shared toolchain-pin rationale (pytest 9.0.3 floor, ruff/ty floors,
`requires-python = ">=3.12,<3.14"`) lives with the
[aj-sisters](.claude/skill-context.md) drift-detection skill — those are
cross-repo policy, not kourai-specific decisions.

kourai is the cleanest-layered of the three sisters. The root
`pyproject.toml` is a uv workspace container (`package = false`) with no
runtime deps; everything lives in workspace members, which stack:

- **`shared/`** (kourai-common): the shared runtime baseline — agent
  protocols, LLM abstraction, observability, HTTP.
- **`agents/*`**: 10 specialised agents; most just depend on `kourai-common`.
- **`hosts/{cli, gui, vn}`**: presentation layers (CLI, Pygame, Ren'Py VN).
- **`mcp_servers/shell`**: one-off MCP server surface.

This layered structure is intentional: each agent is thin (just
`kourai-common`), presentation specifics (TTS, UI toolkits, VN runtime)
stay in hosts, and the shared spine keeps the baseline disciplined.

---

## Workspace layout

Defined under `[tool.uv.workspace]` in the root. Members are:

```
shared
agents/{aidos, aletheia, cupid, dokimasia, hephaestus,
        kallos, metis, mneme, puck, techne}
hosts/{cli, gui}
mcp_servers/shell
```

`hosts/vn` is a workspace member by convention but has no `pyproject.toml`
because Ren'Py is its own non-Python runtime; the bridge logic lives in
`agents/vn_bridge.py` and pulls Hephaestus's deps for TTS (see "Cross-cutting
quirks").

All workspace members are built with `hatchling` as the build backend
(except the root, which isn't a package).

---

## Root workspace — dev deps only

The root `pyproject.toml` has `dependencies = []` and `package = false`. All
its listed deps are dev tooling, grouped under `[dependency-groups]`.

### Test + build stack

- **`pytest>=9.0.3`** / **`pytest-asyncio>=0.24`** / **`pytest-cov>=6.0.0`** /
  **`pytest-xdist>=3.6.1`** — sister-aligned pytest stack. `pytest-xdist`
  is the only plugin present in all three sisters; phalanx uses a
  richer set.
- **`hypothesis>=6.151.9`** — property tests. Not heavily used yet; kept
  available for future invariant-testing.
- **`httpx>=0.27.0`** — duplicated from `kourai-common` so tests can
  import `httpx` without needing the workspace lock resolved against
  a specific agent. Mildly redundant but harmless.
- **`mcp>=1.26.0,<2`** — duplicated from `kourai-common` + `mcp_servers/shell`
  for the same reason. The `<2` upper bound pre-empts a future
  MCP 2.0 with breaking protocol changes.
- **`testcontainers>=4.9.1`** — integration tests that need real external
  boundaries (containers / network / protocols, per the `integration`
  pytest marker in `[tool.pytest.ini_options]`).

### Lint

- **`ruff>=0.9`** — `target-version = "py312"`, floor matches sisters. The
  lint rule set is the widest of the three sisters
  (`E F I UP B SIM W C4 S ASYNC T20 PERF RUF PTH N PIE FURB LOG TCH FLY`) —
  reflects kourai's "style agent eats its own dogfood" discipline (see
  `agents/kallos`, which imports ruff as a runtime dep). `fixable = ["ALL"]`
  with `unfixable = ["T20"]` means every rule autofixes *except* print
  statements, which we leave visible for review.
- **`ty>=0.0.25`** — Astral type checker. The
  `[tool.ty.analysis.replace-imports-with-any]` list is project-specific:
  `pygame.**`, `a2a.**`, `litellm.**`, `kokoro.**` — these are the
  vendor libraries without complete type stubs, so ty gracefully treats
  them as `Any` rather than erroring.

### Docs

- **`zensical>=0.0.24`** — docs generator; floor pinned because earlier
  versions had broken nav-ordering behavior. Same tool lives in
  phalanx-fl and vFL; aj-sisters audits for drift.

### uv-specific: the aiohttp override

```toml
[tool.uv]
override-dependencies = ["aiohttp>=3.13.4"]
```

A transitive dep in the `litellm` provider chain requests an older
`aiohttp` with a known CVE. The override forces `>=3.13.4` globally to
pull the fix. The `pyproject.toml` carries an inline comment with the
verification recipe — every few months, remove the override, run
`uv lock`, and check whether the upstream culprit has updated its pin.
If yes, the override is dead weight and should go.

---

## Shared baseline (`shared/` = `kourai-common`)

This is the runtime spine. Every agent and every host either imports from
it directly or depends on it transitively.

- **`a2a-sdk[http-server]>=0.3.25,<1.0`** — Agent-to-Agent protocol SDK.
  The core abstraction for agents talking to each other over HTTP. The
  `[http-server]` extra pulls the server-side bindings (uvicorn +
  ASGI glue). Upper-bounded `<1.0` because a2a-sdk is pre-1.0 and the
  protocol is still evolving; 1.0 will be a deliberate upgrade.
- **`litellm>=1.80.0`** — LLM provider abstraction. One interface,
  many providers (OpenAI / Anthropic / Google / open-weight via
  Ollama). Avoids hardcoding a specific LLM vendor across agents.
  The 1.80 floor tracks a specific provider-config improvement we rely on.
- **`uvicorn[standard]>=0.34.0`** — ASGI server for the a2a-sdk HTTP
  surface. `[standard]` includes httptools + uvloop for production perf.
- **`httpx>=0.27.0`** — async HTTP client. Agents use it directly for
  any non-a2a HTTP calls (e.g., fetching resources, GitHub API).
- **`mcp>=1.26.0,<2`** — Model Context Protocol SDK. Agents can act as
  MCP clients (consuming tool servers) or servers (exposing their own
  tools). FastMCP ships *inside* this package as `mcp.server.fastmcp` —
  do **not** install the standalone `fastmcp` PyPI package, which is
  Prefect's unrelated fork and will conflict on import. `<2` is a
  pre-emptive upper bound against the MCP 2.0 protocol bump.
- **`python-dotenv>=1.0.0`** — `.env` loading for API keys and local
  config. Standard across all three sisters.
- **`huggingface-hub>=1.5.0`** — model-repo access for any agent that
  pulls weights directly (rare; most go through `litellm`).
- **`opentelemetry-api>=1.20.0`** / **`opentelemetry-sdk>=1.20.0`** /
  **`opentelemetry-exporter-otlp-proto-http>=1.20.0`** — distributed
  tracing across agent-to-agent calls. Essential for debugging
  multi-hop agent workflows where a user-visible failure could have
  originated two or three agents up the chain.

---

## Agents (`agents/*`)

Most agents are thin wrappers: they import `kourai-common` and contribute
their own domain logic (planning, testing, style, etc.). A few have
extra deps specific to their role:

- **`agents/dokimasia`** (testing agent) — adds `pytest>=8.0` (it *runs*
  pytest suites on behalf of the user). The `pytest>=8.0` floor is
  looser than the workspace's `>=9.0.3` intentionally — dokimasia targets
  whatever pytest the *user's* project is on.
- **`agents/hephaestus`** (orchestrator) — adds `edge-tts>=0.30.0` with
  a comment:
  `# VN TTS: vn-bridge uses hephaestus deps (PACKAGE_NAME=hephaestus)`.
  This is load-bearing: the Ren'Py VN bridge in
  `agents/vn_bridge.py` imports via Hephaestus's package namespace, so
  its TTS dep has to live here, not in `hosts/gui` or `hosts/vn`. See
  "Cross-cutting quirks" below.
- **`agents/kallos`** (style agent) — adds `ruff>=0.9` and `ty>=0.0.25`
  as **runtime** deps. Kallos lints and style-fixes code on behalf of
  users, so ruff/ty move from dev-tool to runtime-dependency for this
  single agent. Cleanest instance of "eat your own dogfood" in the
  tree.
- All other agents (aidos, aletheia, cupid, metis, mneme, puck, techne)
  just declare `kourai-common` and contribute logic via Python modules.

---

## Hosts (`hosts/{cli, gui, vn}`)

Hosts are the presentation-layer entry points. Each chooses its own
deps for UI toolkit + any host-specific I/O.

### `hosts/cli`

```
kourai-common
a2a-sdk>=0.3.0,<1.0
asyncclick>=8.0
httpx>=0.27
prompt-toolkit>=3.0
pillow>=10.0
```

- **`asyncclick>=8.0`** — async-capable Click fork. Chosen because the
  CLI's commands are async-first (they orchestrate agents over
  `httpx`/a2a-sdk). Plain Click would force sync wrappers everywhere.
- **`prompt-toolkit>=3.0`** — the REPL / slash-completer menu
  (e.g., `/project` commands). prompt-toolkit is the canonical choice
  for interactive CLI UIs in Python.
- **`pillow>=10.0`** — image display in the terminal (sixel/kitty
  protocols) when agents return image outputs.
- **`a2a-sdk` duplicated** — also declared here (rather than inheriting
  through `kourai-common`) because the CLI talks directly to a2a
  servers and pins its own compat floor.

### `hosts/gui`

```
kourai-common
a2a-sdk>=0.3.0,<1.0
pygame-ce>=2.5.0      # Community edition with enhanced audio support
pillow>=10.0
httpx>=0.27
kokoro>=0.4.0         # Local neural TTS (Apache 2.0, 82M params)
soundfile>=0.13.0     # WAV I/O for Kokoro audio output
edge-tts>=0.30.0      # Fallback cloud TTS (remove once Kokoro is stable)
emoji>=2.15.0
numpy>=1.26
```

- **`pygame-ce>=2.5.0`** over plain `pygame` — pygame-ce is the
  community-maintained fork with a more active release cadence and
  better audio. Standard modern choice.
- **`kokoro>=0.4.0`** — local neural TTS, 82M params, Apache 2.0. The
  GUI speaks agent responses aloud; Kokoro is the default path today.
  **Migration in progress:** Kokoro is being replaced by ElevenLabs
  (matching the stack in the sibling `tools/voice` Next.js app). Once
  the migration lands, both `kokoro` and `edge-tts` come out of the
  dep tree; see ROADMAP.
- **`edge-tts>=0.30.0`** — Microsoft's cloud TTS, currently the
  fallback when Kokoro can't load a voice. Goes away with the
  ElevenLabs migration — it was only ever there to cover Kokoro's
  stability gaps.
- **`soundfile>=0.13.0`** — WAV encode/decode for Kokoro's audio output.
- **`emoji>=2.15.0`** — emoji rendering in agent messages.
- **`numpy>=1.26`** — explicit dep for audio buffer math and some
  pygame surfaces. Already pulled transitively by several deps, but
  pinned here for clarity.

### `hosts/vn`

No `pyproject.toml`. Ren'Py ships its own Python runtime and manages its
own dep tree via game-dir layout; pip is the wrong tool. The bridge that
talks from Ren'Py into the Kourai agent world is
`agents/vn_bridge.py`, which is a regular Python module in the `agents`
workspace tree despite serving the VN.

---

## MCP servers (`mcp_servers/shell`)

```
mcp>=1.26.0,<2
```

The simplest workspace member: a single dep, exposing shell-command
execution as an MCP tool server. Kept deliberately minimal so the
trust surface is auditable — this server runs arbitrary shell commands
on behalf of an agent, so any transitive dep here would be a security
concern. One dep makes that easy to reason about.

---

## Cross-cutting quirks

These are decisions that make sense but are non-obvious from reading a
single `pyproject.toml`. Documented here so a new contributor (or a
future you) doesn't re-derive them.

### edge-tts lives with Hephaestus, not the GUI

The Ren'Py VN bridge (`agents/vn_bridge.py`) identifies itself to agents
as `PACKAGE_NAME=hephaestus` (the orchestrator is the "voice" of the
VN). Ren'Py loads TTS via the hephaestus package namespace, so edge-tts
has to be declared in `agents/hephaestus/pyproject.toml` rather than
`hosts/gui`. Moving the dep without also changing the PACKAGE_NAME
indirection would break VN audio.

### `a2a-sdk` declared in both `shared` and hosts

`hosts/cli` and `hosts/gui` both declare `a2a-sdk>=0.3.0,<1.0` *and*
inherit it transitively through `kourai-common>=0.3.25`. The duplication
is intentional: hosts pin their own minimum compatibility separately
from shared, so a shared-only version bump doesn't silently require
host changes. Minor belt-and-suspenders cost; clearer upgrade semantics.

### Workspace-declared deps without workspace sources

`[tool.uv.sources]` only lists three agents — `kourai-common`,
`kourai-aidos`, `kourai-aletheia` — as `{ workspace = true }`. Other
workspace members *could* need this but don't yet; the entries are
added as cross-agent dep wiring grows.

---

## Major-version watchlist

The dep-pinning rationale above explains *why each upper bound exists today*.
This section is the upgrade-planning counterpart: what's coming in the next
major, when to revisit the pin, and what concrete migration work that means.
Originally tracked on GitHub issue #1; folded in here so the rationale and
the watchlist live next to each other.

### Version pin summary

| Dependency | Pinned range | Current stable | Next major | Status |
|---|---|---|---|---|
| `a2a-sdk` | `>=0.3.0,<1.0` | 0.3.26 | 1.0.0-alpha.1 | Keep `<1.0` until 1.0 GA |
| `mcp` | `>=1.26.0,<2` | 1.27.0 | 2.x (not on PyPI) | Keep `<2` guard; nothing actionable yet |
| `litellm` | unpinned | 1.83.x | — | Safe to track latest |
| `starlette` | unpinned | 1.0.0 | 2.x (not announced) | 1.0 already landed; monitor release notes |
| `uvicorn` | unpinned | 0.44.x | 1.0 (not announced) | Safe to track latest |
| `httpx` | unpinned | 0.28.1 | 1.0 (not announced) | Safe to track latest |

### a2a-sdk 1.0 migration

`1.0.0-alpha.1` is published but pre-release; the `<1.0` upper bound
correctly excludes it. Differences vs the 0.3.x line we ship today:

| Area | 0.3.x | 1.0 |
|---|---|---|
| `kind` field | present on all types | removed |
| Push notifications | `callback` parameter | renamed to `push_notification_config` |
| Types | Python dataclasses | proto-based generated types |
| Server wiring | application wrappers (`A2AStarletteApplication`) | route-based endpoints |
| Client API | prior `ClientFactory` shape | reorganised in alpha track |

Concrete work when 1.0 stabilises:

- Strip `kind` field references from every `agent_executor.py`
- Rename `callback` → `push_notification_config` in any push-notification config
- Audit proto-based type imports — replace dataclass-style construction
- Re-check `ClientFactory` usage against 1.0's API
- Plan the move from `A2AStarletteApplication` wrappers to route-based endpoints
- Run the test suite against 1.0 GA before lifting the upper bound
- Bump the pin to `>=1.0,<2.0`

### mcp 2.0 watchlist

No 2.x MCP SDK release is on PyPI yet. Keep the `<2` upper bound and treat
2.0 migration items as pure watchlist work until concrete release notes
exist. When they do:

- Re-check release notes for concrete API renames before changing code
- Re-validate Streamable HTTP and SSE compatibility — the latest spec
  defines stdio + Streamable HTTP as the two standard transports, and
  servers can return either `application/json` or `text/event-stream`
  under Streamable HTTP (SSE remains supported within that workflow,
  including resumability and polling)
- Update the `memory-mcp-server.js` sidecar transport if applicable
- Re-verify all MCP server healthchecks in `docker-compose.yml`
- Bump the pin to `>=2.0,<3.0`

---

## Open questions

- **`asyncclick` vs `click`** — asyncclick is a community maintained
  fork. If upstream Click ever ships async natively, migrate. Track
  the [click #2033](https://github.com/pallets/click/issues/2033)-era
  discussions.
- **Kokoro vs edge-tts** — the planned cleanup (drop edge-tts once
  Kokoro is stable) has been on the plan long enough to bake. Decision
  point: drop it, or lock in the dual-provider pattern as intentional?
- **`litellm` provider surface** — litellm pulls optional provider SDKs
  as transitive deps; the aiohttp override exists because of one of
  them. As LiteLLM evolves its provider-gating model, revisit whether
  the override is still needed.
- **Empty `dependencies = []` in the root** — correct for a uv
  workspace container, but can confuse tools that don't understand
  `package = false`. If we ever add non-uv tooling that walks the
  root, document this in-place.
