# Ecosystem Roadmap

This page tracks the dependency versions Kourai Khryseai relies on, why each version is pinned where it is, and what breaking changes are expected in upcoming major releases. It is the canonical reference for upgrade planning.
Last web validation: **2026-04-15**.

---

## 📌 Version Pin Summary

| Dependency | Pinned Range | Current Stable | Next Major | Status |
|---|---|---|---|---|
| `a2a-sdk` | `>=0.3.0,<1.0` | 0.3.26 | 1.0.0-alpha.1 | ⚠️ Keep `<1.0` pin until 1.0 GA |
| `mcp` | `>=1.26.0,<2` | 1.27.0 | 2.x (not published on PyPI) | ✅ 1.x stable, keep `<2` guard |
| `litellm` | unpinned | 1.83.x | — | ✅ Safe to track latest |
| `starlette` | unpinned | 1.0.0 | 2.x (not announced) | ⚠️ Major jump landed; monitor release notes |
| `uvicorn` | unpinned | 0.44.x | 1.0 (not announced) | ✅ Safe to track latest |
| `httpx` | unpinned | 0.28.1 | 1.0 (not announced) | ✅ Safe to track latest |

---

## 🤝 A2A Protocol

### Current State (0.3.x)

The **A2A protocol spec latest release is `1.0.0`**, while the Python SDK stable line remains `0.3.x` (currently `0.3.26`). The SDK's `1.0` track is still pre-release (`1.0.0-alpha.1`).

Key patterns we rely on:

- `A2AStarletteApplication` — mounts the A2A server onto Starlette
- `AgentExecutor` + `TaskUpdater` — three-phase task lifecycle (working → artifact → complete)
- SSE via `message/stream` — real-time status updates to the CLI and VN bridge
- `/.well-known/agent.json` — agent card auto-handled by the application class
- `blocking=True` on `SendMessage` — synchronous specialist calls from Hephaestus

### What Changes in 1.0

`1.0.0-alpha.1` was published 2026-04-10. It is still **pre-release** — the upper-bound pin `<1.0` correctly excludes it.

| Area | 0.3.x | 1.0 |
|---|---|---|
| `kind` field | present on all types | **removed** |
| Push notifications | `callback` parameter | renamed to `push_notification_config` |
| Types | Python dataclasses | **proto-based** generated types |
| Server wiring | application wrappers in 0.3.x examples | route-based endpoints in 1.0 alpha track |
| Client API | prior `ClientFactory` shape | reorganized in alpha track |

### Migration Checklist (when 1.0 stabilises)

- [ ] Remove `kind` field references from all `agent_executor.py` files
- [ ] Rename `callback` → `push_notification_config` in any push notification config
- [ ] Audit proto-based type imports — replace dataclass-style construction where needed
- [ ] Review `ClientFactory` usage against 1.0 alpha API changes
- [ ] Plan migration from wrapper-style server setup to route-based endpoints when moving to 1.0
- [ ] Run test suite against `1.0.0` before removing the upper-bound pin
- [ ] Update the pin to `>=1.0,<2.0`

---

## 🔌 MCP SDK

### Current State (1.27.x)

The Python MCP SDK is currently `1.27.0`.
The spec latest protocol line is `2025-11-25`.

Key patterns we rely on:

- `FastMCP` from `mcp.server.fastmcp` — **bundled in the SDK, do not install the separate `fastmcp` PyPI package** (that is Prefect's unrelated fork)
- Stdio transport — recommended for local and subprocess MCP connections
- `ClientSession` — the main client class; manage one session per server manually (no built-in `MultiServerSession`)

Transport status in latest spec:

- Two standard transports are defined: **stdio** and **Streamable HTTP**
- Under Streamable HTTP, servers can return either `application/json` or `text/event-stream`
- SSE remains a supported mechanism within Streamable HTTP workflows (including resumability and polling guidance)

### What Changes in 2.0

As of 2026-04-15, **no 2.x MCP SDK releases are published on PyPI**. Keep the `<2` upper bound and treat 2.0 migration items as watchlist work until concrete release notes are published.

### Migration Checklist (when 2.0 stabilises)

- [ ] Re-check MCP 2.0 release notes for concrete API renames before making code changes
- [ ] Re-validate transport behavior for Streamable HTTP and SSE compatibility
- [ ] Update `memory-mcp-server.js` sidecar transport if applicable
- [ ] Re-verify all MCP server healthchecks in `docker-compose.yml`
- [ ] Update the pin to `>=2.0,<3.0`

!!! warning "Do not install `fastmcp` from PyPI"
    The `fastmcp` package on PyPI is Prefect's independent fork and has diverged significantly from the bundled version in `mcp.server.fastmcp`. Installing it alongside `mcp` will cause import conflicts.

---

## 🧠 LiteLLM

LiteLLM is **not upper-bound pinned** — it releases near-daily and rarely introduces breaking changes to the interface we use (`litellm.acompletion`).

### Current State (1.83.x)

Current stable on PyPI is `1.83.8`.

Notable ecosystem capabilities reflected in current docs:

- Unified OpenAI-format gateway for 100+ providers
- Native A2A gateway surface (`/a2a`) and A2A client helpers
- MCP bridge/gateway support in both SDK and proxy workflows

### Provider Selection

Controlled by `KOURAI_PROVIDER` and `KOURAI_MODEL_TIER` in `.env`:

| Provider | Use Case |
|---|---|
| `anthropic` (default) | Production — Claude Haiku / Sonnet / Opus |
| `google` | Alternative — Gemini Flash / Pro |
| `local` | Free offline dev — Ollama (llama3.3) |

---

## 🎙️ TTS Ecosystem

| Engine | Version | Licence | Notes |
|---|---|---|---|
| `edge-tts` | 7.2.8 | LGPLv3 | Microsoft Edge voices, no API key |
| Kokoro | latest | Apache 2.0 | CPU-capable, self-hosted, competitive with commercial APIs |
| Coqui XTTS v2.5 | — | CPML | Voice cloning |
| Piper | — | MIT | Edge / real-time, lowest latency |

---

## 🏛️ Protocol Governance

A2A and MCP are both open, versioned specifications with public release notes and reference SDKs. In practice this gives us:

- Stable, vendor-neutral governance
- Long deprecation windows before breaking changes ship
- Public roadmaps and spec repositories
- Explicit version negotiation and compatibility notes in the specs
- Multi-SDK ecosystems that reduce vendor lock-in

---

## 📚 References

| Resource | Link |
|---|---|
| A2A Python SDK | [github.com/a2aproject/a2a-python](https://github.com/a2aproject/a2a-python) |
| A2A Protocol Spec | [a2a-protocol.org](https://a2a-protocol.org/latest) |
| A2A Releases | [github.com/a2aproject/a2a-python/releases](https://github.com/a2aproject/a2a-python/releases) |
| MCP Python SDK | [github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) |
| MCP Spec | [modelcontextprotocol.io](https://modelcontextprotocol.io/) |
| LiteLLM | [github.com/BerriAI/litellm](https://github.com/BerriAI/litellm) |
| PyPI (a2a-sdk) | [pypi.org/project/a2a-sdk](https://pypi.org/project/a2a-sdk/) |
| PyPI (mcp) | [pypi.org/project/mcp](https://pypi.org/project/mcp/) |
