<div align="center">

<img src="docs/assets/golden-maidens.png" width="800" alt="Kourai Khryseai Hero Image">

# 🏛️ Κοῦραι Χρύσεαι

### **Kourai Khryseai** — *The Golden Maidens*

*Ten specialized AI agents that collaborate with you on development—you guide each step, they show their work, iterate in real-time.*

[![A2A Protocol](https://img.shields.io/badge/A2A_Protocol-v1-4285F4?style=flat-square&logo=google&logoColor=white)](https://a2a-protocol.org)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![uv](https://img.shields.io/badge/uv-package_manager-DE5FE9?style=flat-square)](https://docs.astral.sh/uv/)
[![codecov](https://codecov.io/gh/ajbarea/kourai-khryseai/graph/badge.svg?token=bNiUvETLLU)](https://codecov.io/gh/ajbarea/kourai-khryseai)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

**Collaborate, don't automate. See your agents think. Guide them in real-time.**

```
$ uv run kourai-dev cli

❯ add user authentication

🔥 Hephaestus: Analyzing request...
🔥 Hephaestus: "Metis! Lay out the path. What does this forge need?"
📐 Metis: Specification in progress...
   → Should we use JWT or sessions?

❯ JWT with refresh tokens

📐 Metis: Got it. Full spec: 8 steps, edge cases noted ✅
🔥 Hephaestus: "Well forged, Metis. Techne! Take what she's built and make it real."
⚙️ Techne: Writing files... (streaming changes live) ✅
🔥 Hephaestus: "Dokimasia — put it through the fire."
🧪 Dokimasia: Running tests... 12/12 passing ✅
🔥 Hephaestus: "Kallos. Standards."
✨ Kallos: Code review complete, no issues ✅
🔥 Hephaestus: "Mneme — seal the work."
📜 Mneme: Commits ready
```

</div>

---

## What is this?

Kourai Khryseai is an **interactive multi-agent development system** where ten specialized AI agents work *with* you, not *for* you. Instead of running autonomously in the background, agents stream their work in real-time, show their reasoning, and ask for guidance when decisions matter.

You describe your goal. **Hephaestus** acts as the Forge Master — narrating in-character between each step while maintaining a running **Forge Transcript** that every specialist reads. No agent works from a decontextualized stub: each sees the full conversation history and all prior reasoning before contributing.

**Access it three ways:**
- **CLI** — Real-time agent output in your terminal
- **GUI** — Interactive dialogue with personality-matched voices and visual agent profiles
- **Ren'Py VN** — Visual novel with affinity system and romance routes

---

## The Agents

**Core Specialists**

| Agent | Role | Strength |
|-------|------|----------|
| 🔥 **Hephaestus** | Orchestrator | Forge Master — routes pipelines, narrates handoffs, maintains Forge Transcript |
| 📐 **Metis** | Planner | Breaks goals into detailed specs, identifies edge cases |
| ⚙️ **Techne** | Coder | Reads existing patterns, writes clean changes |
| 🧪 **Dokimasia** | Tester | Writes comprehensive test suites, validates coverage |
| ✨ **Kallos** | Stylist | Enforces code quality, cleans comments and docstrings |
| 📜 **Mneme** | Scribe | Generates organized commit messages from diffs |

**Companion Spirits**

| Agent | Role | When they appear |
|-------|------|----------|
| 🎭 **Puck** | Guide | Tutorial, idle nudges, minigame facilitation |
| 💘 **Cupid** | Romance | Relationship coaching and confession scenes (0.7+ affinity, Tier 3 Bonded) |

**Quality Validators**

| Agent | Role | When they activate |
|-------|------|----------|
| 🪞 **Aidos** | Anti-Slop | Detects vague, corporate, or passive language in agent output |
| 📚 **Aletheia** | Research | Validates citations and checks factual accuracy |

Each is an independent HTTP server communicating via the open [A2A protocol](https://a2a-protocol.org). They can be deployed separately, tested independently, or swapped for custom implementations.

---

## How It Works

### 1. You Start a Conversation

**CLI (interactive REPL):**
```bash
$ uv run kourai-dev cli

❯ implement CSV export with tests
```

**Or GUI (visual interface):**
```bash
$ uv run kourai-dev gui
```

**Or VN (Ren'Py visual novel):**
```bash
$ uv run kourai-dev vn   # resolves Ren'Py SDK from KOURAI_RENPY_EXE or local install
```

### 2. Hephaestus Orchestrates

Hephaestus routes your request through a pipeline and acts as **Forge Master** throughout. Before each specialist is called, Hephaestus narrates an in-character handoff line and passes the **full Forge Transcript** — every message from every agent so far — to the next specialist. Most requests flow: **Metis → Techne → Dokimasia → Kallos → Mneme**. Quick fixes skip planning. Pure styling requests skip coding.

### 3. Agents Stream Their Work

Each agent shows you:
- **What they're thinking** — Real-time reasoning and planning
- **What they're building** — Code diffs, test runs, lint results
- **What they need** — Questions when decisions matter

```
📐 Metis: Analyzing requirements...
   → "Should CSV use streaming for large files?" (Option A: yes, Option B: no)

❯ Option A, streaming

📐 Metis: Confirmed. Here's the spec:
   - Parser with iterator interface
   - Chunked I/O for >100MB files
   - Tests cover edge cases...

✅ Spec complete. Routing to Techne
```

### 4. Human-on-the-Loop

When agents face meaningful choices, they ask. You provide direction. This prevents wasted tokens on speculation and keeps you in control of trade-offs:
- Architecture decisions (sync vs async, database strategy)
- Scope boundaries (what counts as "done")
- Validation rules (what passes, what fails)

### 5. Feedback Loops

If Kallos finds issues Techne can fix, they iterate up to 5 rounds automatically (tunable via `KOURAI_MAX_ITERATIONS`). Otherwise, they report what remains. Nothing silent.

---

## Quick Start

> Every `uv run kourai-dev <cmd>` below has a `make <cmd>` shorthand if you prefer — the Makefile is a thin compatibility wrapper around the same dev CLI.

### 1. Install

```bash
git clone https://github.com/ajbarea/kourai-khryseai.git
cd kourai-khryseai

uv sync --all-packages    # Install all workspace dependencies
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY
```

**Using Ollama instead (free, local)?**
```bash
# Install Ollama, pull models, then:
KOURAI_PROVIDER=local uv run kourai-dev cli
```

### 2. Start the Agents

```bash
uv run kourai-dev up        # Build images and start all 10 agents + vn-bridge + observability stack
uv run kourai-dev status    # Check health
```

### 3. Your First Conversation

**CLI:**
```bash
uv run kourai-dev cli

❯ implement CSV export with tests
```

**GUI (richer experience with voices and visuals):**
```bash
uv run kourai-dev gui
```

**VN (Ren'Py visual novel with affinity, romance routes, save/load):**
```bash
uv run kourai-dev vn        # see hosts/vn/README.md for Ren'Py SDK resolution
```

See [Getting Started](docs/getting-started.md) for detailed setup and troubleshooting.

### 4. Player Projects (optional)

Create a real on-disk git project that the maidens forge into. Each player turn runs in a git worktree on a `forge/...` branch — accept to fast-forward into `main`, discard to throw it away.

```bash
uv run kourai-dev cli

❯ /project new hello-forge --template python
❯ /project use hello-forge
❯ add a function that returns "hello world" with tests
❯ /project status
❯ /project accept <session_id>     # or /project discard <session_id>
```

Projects live under `~/.kourai_khryseai/projects/<player_id>/`. Templates: `empty`, `python`, `node`, `backend`, `frontend`.

**Sandboxed execution (opt-in):** route every agent-issued command through a locked-down container.

```bash
uv run kourai-dev sandbox-image                  # one-time: build the kourai-sandbox image
KOURAI_SANDBOX=container uv run kourai-dev cli   # pytest, ruff, etc. now run in --network=none containers
```

If `docker` isn't on your PATH, the CLI logs a warning and falls back to host execution — devs aren't blocked.

---

## Architecture

```
              YOU  (CLI · GUI · Ren'Py VN)
                     │            │
                A2A · SSE     HTTP/NDJSON
                     │            ▼
                     │      vn-bridge :10010
                     ▼            │
              🔥 HEPHAESTUS  ◄────┘
              (Orchestrator)
                  :10000
        ┌────┬────┼────┬────┐
        ▼    ▼    ▼    ▼    ▼              Companions / Validators
     📐 METIS  ⚙️ TECHNE  🧪 DOKIMASIA      🎭 PUCK    💘 CUPID
     :10001    :10002    :10003             :10006    :10007
     ✨ KALLOS  📜 MNEME                     🪞 AIDOS   📚 ALETHEIA
     :10004    :10005                        :10008    :10009
        │
        ▼
  MCP servers — forge + shell (in-repo) · memory-mcp + context7-mcp (sidecars)
        │
        ▼
  OpenTelemetry → Jaeger :16686 · Prometheus :9090 · Dozzle :8888
```

**Key points:**
- Each of the 10 agents is an independent HTTP server with its own model assignment.
- A2A protocol enables peer-to-peer communication without a central broker; Ren'Py speaks through `vn-bridge`, a synchronous-to-async HTTP/NDJSON shim on `:10010`.
- Hephaestus maintains a **Forge Transcript** and passes the full history to every specialist — each agent sees all prior reasoning before contributing.
- Real-time streaming via SSE allows agents to show work as it happens.
- MCP layer: two in-repo servers (`mcp_servers/forge`, `mcp_servers/shell`) for filesystem / git / shell access; two Docker sidecars (`memory-mcp`, `context7-mcp`) for knowledge graph + library docs.
- Jaeger + Prometheus + Dozzle cover traces, metrics, and live logs (`uv run kourai-dev observe` opens all three).

---

## Multi-Mode Access

### CLI (Terminal)

Fast, scriptable, works over SSH. See real-time agent output with emoji progress.

```bash
❯ add authentication to /api/users

🔥 Hephaestus: Routing to [techne, dokimasia, kallos, mneme]...
🔥 Hephaestus: "Techne! We've skipped the planning — get to work."
⚙️  Techne: Analyzing existing auth patterns...
   ↳ Found JWT middleware in src/middleware/auth.py
   ↳ Writing changes to 2 files... ✅
🔥 Hephaestus: "Dokimasia — put it through the fire."
🧪 Dokimasia: Running tests...
   ↳ [5/5 passing] ✅
🔥 Hephaestus: "Kallos. Standards."
✨ Kallos: Code review complete, no issues ✅
📜 Mneme: Commits ready
```

### GUI (Desktop)

Visual interface with agent portraits, dialogue bubbles, and neural text-to-speech. Each agent has a personality-matched voice. Dialogue history is saved per session.

- 🎨 Full-color agent portraits (JRPG aesthetic)
- 💬 Real-time dialogue with streaming responses
- 🔊 Neural voice synthesis (**Kokoro-82M local SLM** + Edge-TTS fallback)
- ⚡ **~3s to first audio chunk** on streaming `RealtimeTTS.play()` (measured 2026-05-03; full latency table in [ROADMAP M20](./ROADMAP.md#m20--audio-text-synchronization-across-cli--gui--vn))
- ⚙️ Settings for accessibility and voice customization
- 📜 Scrollable chat history

### VN (Ren'Py Visual Novel)

Dating-sim inspired interface where the Golden Maidens are characters with personality, affinity tiers, and romance routes. Connects to the same agent backend through the `vn-bridge` Docker service (`:10010`). Built on Ren'Py 8.5.2.

- 🏛️ Warm forge aesthetic — gold, cream, charcoal
- 💛 Affinity HUD — tracks your relationship tier with each maiden
- 💬 Gossip system — idle agents share personality-driven flavor text
- 🎭 Choice events — agents present choices that affect affinity
- 💘 Romance routes — Cupid coaches confession scenes at Tier 3 Bonded (0.7+ affinity)
- 💾 Full save/load — portrait thumbnails, conversation context, bridge reconnect

See [VN Reference](docs/vn.md) for architecture and [`hosts/vn/README.md`](hosts/vn/README.md) for SDK resolution and per-platform launcher notes.

---

## Configuration

### LLM Models

Choose model tiers per environment. Default uses Haiku (fast, cheap). Upgrade to Sonnet or Opus as needed:

```bash
# .env
KOURAI_PROVIDER=anthropic     # anthropic | google | local (Ollama)
KOURAI_MODEL_TIER=standard    # cheap | standard | smart
```

| Tier | Hephaestus | Metis | Techne | Dokimasia | Kallos | Mneme |
|------|-----------|-------|--------|-----------|--------|-------|
| **cheap** | Haiku | Haiku | Haiku | Haiku | Haiku | Haiku |
| **standard** | Sonnet | Sonnet | Sonnet | Haiku | Haiku | Haiku |
| **smart** | Sonnet | Opus | Sonnet | Sonnet | Sonnet | Sonnet |

Companion spirits (Puck, Cupid, Aidos, Aletheia) and tier overrides are detailed in [Configuration → LLM Models](docs/configuration.md#llm-models).

### TTS Backends

Kourai Khryseai prioritizes local execution for privacy and speed.

- **Kokoro-82M (Default)**: High-quality, Apache 2.0 local TTS. CPU inference supported; ~4GB system RAM per upstream guidance ([hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)).
- **Edge-TTS (Fallback)**: Microsoft Azure Neural voices (requires internet).

See [Configuration](docs/configuration.md) for full environment variable reference.

---

## Development

```bash
uv run kourai-dev validate    # Quick pre-push gate: lint + unit tests
uv run kourai-dev lint        # ruff format --check + ruff check + ty (CI-equivalent)
uv run kourai-dev fix         # Auto-apply ruff format + safe/unsafe fixes
uv run kourai-dev test        # Full suite: unit + integration + performance (~73% project coverage, 80% patch-coverage target)
uv run kourai-dev observe     # Open Jaeger, Prometheus, Dozzle in browser
uv run kourai-dev docs        # Serve docs locally at http://localhost:8000
uv run kourai-dev help        # Show all available commands
```

### Live observed dev session (`make theoros`)

Spins up a 3-pane tmux session in **autopilot mode**: an autonomous `claude` CLI in the middle pane drives `make cli` (top pane) through a curated prompt library at `tests/fixtures/theoros_prompts.md`, while the bottom pane tails docker logs. Run `make theoros`, then attach from another terminal:

```bash
tmux attach -t kourai-theoros -r
```

You watch all three panes — REPL, Claude's reasoning, agent logs. `make theoros-down` tears it down. `make theoros-status` shows the JSON state file. For manual driving (no autopilot pane), run `bash scripts/theoros.sh up --no-autopilot`. See [docs/theoros.md](docs/theoros.md) for the role split, the prompt library, and troubleshooting.

**Stack:**
- **Framework** — [a2a-sdk](https://github.com/a2a-org/a2a-sdk) + [Starlette](https://www.starlette.io/)
- **Language** — Python 3.12+ with modern type hints
- **LLM** — [LiteLLM](https://docs.litellm.ai/) (pluggable: Claude, Gemini, Ollama, etc.)
- **TTS** — **Kokoro-82M** (Local) / **Edge-TTS** (Cloud) with real-time streaming
- **MCP** — [MCP](https://modelcontextprotocol.io/) (filesystem, git, shell, context7)
- **Linting** — [Ruff](https://docs.astral.sh/ruff/) + [ty](https://docs.astral.sh/ty/) (Python)
- **Packaging** — [uv](https://docs.astral.sh/uv/) workspaces
- **Observability** — [OpenTelemetry](https://opentelemetry.io/) → [Jaeger](https://www.jaegertracing.io/) + [Prometheus](https://prometheus.io/)
- **Containers** — Docker + Docker Compose
- **Docs** — [Zensical](https://zensical.dev)

---

## Pipelines

Hephaestus auto-selects the right pipeline based on your request:

| You say | Pipeline |
|---------|----------|
| *"implement feature X"* | Metis → Techne → Dokimasia → Kallos → Mneme |
| *"fix bug in X"* | Techne → Dokimasia → Kallos → Mneme |
| *"add tests for X"* | Dokimasia → Kallos → Mneme |
| *"clean up X"* | Kallos → Mneme |
| *"commit prep"* | Mneme |
| *"plan feature X"* | Metis |
| *"@techne, explain this function"* | Techne (1-on-1) |

---

## Observability

Every request creates a distributed trace across all agents. `uv run kourai-dev observe` opens the three-pane diagnostic surface in your browser:

- **Jaeger** ([`localhost:16686`](http://localhost:16686)) — traces: A2A hops, MCP tool calls, full pipeline timing. RED metrics (Rate, Error, Duration) via the spanmetrics connector.
- **Prometheus** ([`localhost:9090`](http://localhost:9090)) — metrics: latency percentiles, rates, error counts.
- **Dozzle** ([`localhost:8888`](http://localhost:8888)) — live per-container log tail with trace IDs stamped on every span-bound line.

Trace → flow. Metric → aggregate. Log → narrative. See [Observability docs](docs/observability.md) for the cross-tool linking pattern and triage runbook.

---

## Trust + security

Kourai sits in the same conceptual neighborhood as [Anthropic's Project Glasswing](https://www.anthropic.com/glasswing) (April 2026): trustworthy software in the AI era, with frontier models autonomously modifying code at scale. Glasswing's frame is vulnerability discovery; Kourai's is multi-agent development. The shared posture is the same: code that AI agents emit and modify needs to be auditable, trust boundaries between agents need to be explicit, and transport between agents and MCP tools should follow current best practice (TLS 1.3, OAuth 2.1 + OIDC, RBAC, RFC 8707 resource indicators) rather than be reinvented. See [Security posture](docs/security.md) for what holds today, where the implicit trust boundaries are, and what to harden before opening the Docker network to a multi-tenant deploy.

---

## Documentation

Full docs are available at [Kourai Khryseai](https://ajbarea.github.io/kourai-khryseai/), built with [Zensical](https://zensical.dev).

**Key sections:**
- [Overview](docs/overview.md) — The vision and how requests flow
- [Getting Started](docs/getting-started.md) — Installation and first requests
- [Agents](docs/agents/index.md) — What each specialist does
- [Architecture](docs/architecture/index.md) — System design and patterns
- [CLI Reference](docs/cli.md) — Commands and options
- [GUI Reference](docs/gui.md) — Interface and voice settings
- [VN Reference](docs/vn.md) — Ren'Py architecture, bridge protocol, save/load
- [Observability](docs/observability.md) — Jaeger / Prometheus / Dozzle triage runbook
- [Security posture](docs/security.md) — Trust boundaries, TLS 1.3 + OAuth 2.1 + RBAC target, PQC watcher
- [Configuration](docs/configuration.md) — Environment variables and model assignment
- [Pricing](docs/pricing.md) — Per-tier cost structure for Anthropic / Google / Ollama

---

## Coverage

<div align="center">

[![codecov sunburst](https://codecov.io/gh/ajbarea/kourai-khryseai/graphs/sunburst.svg?token=bNiUvETLLU)](https://app.codecov.io/gh/ajbarea/kourai-khryseai)
</div>

---

## Citation

If you use Kourai Khryseai or its findings in academic work, please
cite the NE AI Agents Day 2026 poster + extended abstract:

```bibtex
@inproceedings{barea2026kourai,
  author    = {Arnaldo Barea},
  title     = {Kourai Khryseai: Transparent Human-on-the-Loop Multi-Agent Software Development},
  booktitle = {North-East AI Agents Day 2026},
  address   = {New York, NY, USA},
  year      = {2026},
  month     = {5},
  url       = {https://ajbarea.github.io/kourai-khryseai/research/ne-agents-day-2026/},
}
```

GitHub renders a copy-paste citation widget from
[`CITATION.cff`](CITATION.cff) on the right sidebar of the repo
homepage.

---

## License

[MIT](LICENSE)

---

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://res.cloudinary.com/dumwa1w5x/image/upload/q_auto,f_auto,e_negate/v1779302138/brand_gwqy8l.png">
  <img src="https://res.cloudinary.com/dumwa1w5x/image/upload/q_auto,f_auto/v1779302138/brand_gwqy8l.png" alt="" height="16" />
</picture>&nbsp;&nbsp;2026 <a href="https://ajbarea.github.io/">AJ Barea</a>

</div>
