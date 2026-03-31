# Ecosystem Roadmap

This page tracks the dependency versions Kourai Khryseai relies on, why each version is pinned where it is, and what breaking changes are expected in upcoming major releases. It is the canonical reference for upgrade planning.

---

## 📌 Version Pin Summary

| Dependency | Pinned Range | Current Stable | Next Major | Status |
|---|---|---|---|---|
| `a2a-sdk` | `>=0.3.0,<1.0` | 0.3.25 | 1.0.0 (alpha) | ⚠️ Breaking changes documented |
| `mcp` | `>=1.26.0,<2` | 1.26.0 | 2.0 (pre-alpha) | ⚠️ Transport rework pending |
| `litellm` | unpinned | 1.82.x | — | ✅ Safe to track latest |
| `starlette` | unpinned | 0.46.x | — | ✅ Safe to track latest |
| `uvicorn` | unpinned | 0.34.x | — | ✅ Safe to track latest |
| `httpx` | unpinned | 0.28.x | — | ✅ Safe to track latest |

---

## 🤝 A2A Protocol

### Current State (0.3.x)

The Agent-to-Agent protocol is under the Linux Foundation's **AAIF** governance umbrella (since June 2025, 150+ member organisations). The Python SDK is stable at `0.3.25`.

Key patterns we rely on:

- `A2AStarletteApplication` — mounts the A2A server onto Starlette
- `AgentExecutor` + `TaskUpdater` — three-phase task lifecycle (working → artifact → complete)
- SSE via `message/stream` — real-time status updates to the CLI and VN bridge
- `/.well-known/agent.json` — agent card auto-handled by the application class
- `blocking=True` on `SendMessage` — synchronous specialist calls from Hephaestus

### What Changes in 1.0

`1.0.0a0` was published 2026-03-17. It is **alpha** — the upper-bound pin `<1.0` excludes it automatically. Confirmed breaking changes:

| Area | 0.3.x | 1.0 |
|---|---|---|
| `kind` field | present on all types | **removed** |
| Push notifications | `callback` parameter | renamed to `push_notification_config` |
| Types | Python dataclasses | **proto-based** generated types |
| Backward compat | — | Helpers for 0.3 ↔ 1.0 interop included in SDK |
| gRPC transport | optional | First-class alongside HTTP+SSE |

The `async with` client lifecycle pattern (added in 0.3.23) carries forward unchanged.

### Migration Checklist (when 1.0 stabilises)

- [ ] Remove `kind` field references from all `agent_executor.py` files
- [ ] Rename `callback` → `push_notification_config` in any push notification config
- [ ] Audit proto-based type imports — replace dataclass-style construction where needed
- [ ] Run test suite against `1.0.0` before removing the upper-bound pin
- [ ] Update the pin to `>=1.0,<2.0`

!!! note "Joint A2A + MCP interoperability spec expected Q3 2026"
    Google ADK already provides a `to_a2a(root_agent)` helper and an `MCPToolset` for building agents that speak both protocols natively.

---

## 🔌 MCP SDK

### Current State (1.26.x)

The Model Context Protocol is under the Linux Foundation's **AAIF** governance umbrella (since December 2025). The Python SDK is stable at `1.26.0`.

Key patterns we rely on:

- `FastMCP` from `mcp.server.fastmcp` — **bundled in the SDK, do not install the separate `fastmcp` PyPI package** (that is Prefect's unrelated fork)
- Stdio transport — recommended for local and subprocess MCP connections
- `ClientSession` — the main client class; manage one session per server manually (no built-in `MultiServerSession`)

The MCP spec shifted to **Streamable HTTP** as the primary transport on 2026-03-26, replacing SSE. SSE is deprecated but still functional throughout 1.x.

### What Changes in 2.0

v2.0 is pre-alpha. The upper-bound pin `<2` excludes all pre-releases. The `main` branch of the SDK repo is v2 development; `v1.x` is maintenance-only.

Confirmed scope of breaking changes:

| Area | 1.x | 2.0 |
|---|---|---|
| Primary transport | SSE (deprecated in spec) | Streamable HTTP |
| Server class | `FastMCP` | `McpServer` (rename) |
| SDK branching | stable | `v1.x` maintenance, `main` = v2 |
| `.well-known` discovery | not in spec | Planned for next spec release (est. June 2026) |
| Stateless scaling | not supported | Planned |

### Migration Checklist (when 2.0 stabilises)

- [ ] Replace all `FastMCP` imports with `McpServer` across agent and MCP server files
- [ ] Migrate any SSE transport configuration to Streamable HTTP
- [ ] Update `memory-mcp-server.js` sidecar transport if applicable
- [ ] Re-verify all MCP server healthchecks in `docker-compose.yml`
- [ ] Update the pin to `>=2.0,<3.0`

!!! warning "Do not install `fastmcp` from PyPI"
    The `fastmcp` package on PyPI is Prefect's independent fork and has diverged significantly from the bundled version in `mcp.server.fastmcp`. Installing it alongside `mcp` will cause import conflicts.

---

## 🧠 LiteLLM

LiteLLM is **not upper-bound pinned** — it releases near-daily and rarely introduces breaking changes to the interface we use (`litellm.acompletion`).

### Current State (1.82.x)

Notable additions in 2026:

- 6.5× faster SDK initialization
- Dynamic Rate Limiter v3
- Built-in guardrails (zero additional cost)
- MCP proxy support
- New models: Gemini 2.5 Flash/Pro, Grok Code Fast, GPT-5, GPT-5.3-Codex, DeepSeek-v3.1

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
| `edge-tts` | 7.2.7 | MIT | Microsoft Edge voices, no API key, 40K weekly downloads |
| Kokoro | latest | Apache 2.0 | CPU-capable, self-hosted, competitive with commercial APIs |
| Coqui XTTS v2.5 | — | CPML | Voice cloning |
| Piper | — | MIT | Edge / real-time, lowest latency |

---

## 🏛️ Protocol Governance

Both A2A and MCP are under the **AI Alliance Infrastructure Foundation (AAIF)**, a Linux Foundation project. This means:

- Stable, vendor-neutral governance
- Long deprecation windows before breaking changes ship
- Public roadmaps and RFCs
- No single company can unilaterally break the protocol

The joint A2A + MCP interoperability specification is expected **Q3 2026** and will define how agents that speak both protocols discover and communicate with each other natively.

---

## 📚 References

| Resource | Link |
|---|---|
| A2A Python SDK | [github.com/a2aproject/a2a-python](https://github.com/a2aproject/a2a-python) |
| A2A Protocol Spec | [a2a-protocol.org](https://a2a-protocol.org/latest) |
| A2A Changelog | [CHANGELOG.md](https://github.com/a2aproject/a2a-python/blob/main/CHANGELOG.md) |
| MCP Python SDK | [github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) |
| MCP Spec | [modelcontextprotocol.io](https://modelcontextprotocol.io/) |
| LiteLLM | [github.com/BerriAI/litellm](https://github.com/BerriAI/litellm) |
| AAIF Governance | [lfaidata.foundation](https://lfaidata.foundation/) |
