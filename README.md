<div align="center">

<img src="docs/assets/golden-maidens.png" width="800" alt="Kourai Khryseai Hero Image">

# 🏛️ Κοῦραι Χρύσεαι

### **Kourai Khryseai** — *The Golden Maidens*

*Ten specialized AI agents that collaborate with you on development—you guide each step, they show their work, iterate in real-time.*

[![A2A Protocol](https://img.shields.io/badge/A2A_Protocol-v0.4-4285F4?style=flat-square&logo=google&logoColor=white)](https://a2a-protocol.org)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![uv](https://img.shields.io/badge/uv-package_manager-DE5FE9?style=flat-square)](https://docs.astral.sh/uv/)
[![codecov](https://codecov.io/gh/ajbarea/kourai-khryseai/graph/badge.svg?token=bNiUvETLLU)](https://codecov.io/gh/ajbarea/kourai-khryseai)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

---

**Collaborate, don't automate. See your agents think. Guide them in real-time.**

```
$ make cli

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
| 💘 **Cupid** | Romance | Relationship coaching and confession scenes (0.6+ affinity) |

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
$ make cli

❯ implement CSV export with tests
```

**Or GUI (visual interface):**
```bash
$ make gui
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

If Kallos finds issues Techne can fix, they iterate up to 3 rounds automatically. Otherwise, they report what remains. Nothing silent.

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/ajbarea/kourai-khryseai.git
cd kourai-khryseai

make setup        # Install dependencies (equivalent: uv sync --all-packages)
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY
```

**Using Ollama instead (free, local)?**
```bash
# Install Ollama, pull models, then:
KOURAI_PROVIDER=local make cli
```

### 2. Start the Agents

```bash
make up           # Build images and start all 10 agents + vn-bridge + observability stack
make status       # Check health
```

### 3. Your First Conversation

**CLI:**
```bash
make cli

❯ implement CSV export with tests
```

**GUI (richer experience with voices and visuals):**
```bash
make gui
```

See [Getting Started](docs/getting-started.md) for detailed setup and troubleshooting.

### 4. Player Projects (optional)

Create a real on-disk git project that the maidens forge into. Each player turn runs in a git worktree on a `forge/...` branch — accept to fast-forward into `main`, discard to throw it away.

```bash
make cli

❯ /project new hello-forge --template python
❯ /project use hello-forge
❯ add a function that returns "hello world" with tests
❯ /project status
❯ /project accept <session_id>     # or /project discard <session_id>
```

Projects live under `~/.kourai_khryseai/projects/<player_id>/`. Templates: `empty`, `python`, `node`, `backend`, `frontend`.

**Sandboxed execution (opt-in):** route every agent-issued command through a locked-down container.

```bash
make sandbox-image                    # one-time: build the kourai-sandbox image
KOURAI_SANDBOX=container make cli     # pytest, ruff, etc. now run in --network=none containers
```

If `docker` isn't on your PATH, the CLI logs a warning and falls back to host execution — devs aren't blocked.

---

## Architecture

```
                    YOU (CLI or GUI)
                           │
                      A2A · SSE
                           ▼
                  🔥 HEPHAESTUS (Orchestrator)
                         :10000
                    ┌─────┼─────┐
         A2A        │     │     │      A2A
      ┌──────────┬──┤     │     ├──┬──────────┐
      │          │  │     │     │  │          │
   📐 METIS  ⚙️ TECHNE  🧪 DOKIMASIA  ✨ KALLOS  📜 MNEME
   :10001     :10002     :10003      :10004    :10005
      │          │  │     │     │  │          │
      └──────────┴──┤     │     ├──┴──────────┘
                  │     │     │
                 MCP Servers
              (filesystem, git, shell)
                     │
              OpenTelemetry → Jaeger ◄──► Prometheus
                   :16686 (UI)         :9090 (UI)
```

**Key points:**
- Each agent is an independent HTTP server with its own model assignment
- A2A protocol enables peer-to-peer communication without a central broker
- Hephaestus maintains a **Forge Transcript** and passes the full history to every specialist — each agent sees all prior reasoning before contributing
- Real-time streaming via SSE allows agents to show work as it happens
- MCP servers handle filesystem, git, and shell access
- Jaeger + Prometheus trace every request and monitor performance

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
- 🔊 Low-latency neural voice synthesis (**Kokoro-82M local SLM** + Edge-TTS fallback)
- ⚡ **170ms "Human-Like" Latency** via real-time audio chunk streaming
- ⚙️ Settings for accessibility and voice customization
- 📜 Scrollable chat history

---

## Configuration

### LLM Models

Choose model tiers per environment. Default uses Haiku (fast, cheap). Upgrade to Sonnet or Opus as needed:

```bash
# .env
KOURAI_PROVIDER=claude        # or 'local' for Ollama
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

- **Kokoro-82M (Default)**: High-quality, Apache 2.0 local TTS. Runs on CPU with ~350MB RAM.
- **Edge-TTS (Fallback)**: Microsoft Azure Neural voices (requires internet).

See [Configuration](docs/configuration.md) for full environment variable reference.

---

## Development

```bash
make test       # Run unit and integration tests (80%+ coverage)
make lint       # Run ruff, ty, formatters
make docs       # Serve docs locally at http://localhost:8000
make help       # Show all available commands
```

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

Every request creates a distributed trace across all agents. Open Jaeger at [`localhost:16686`](http://localhost:16686) or Prometheus at [`localhost:9090`](http://localhost:9090) to see:

- Full request flow as a single trace
- Per-agent LLM call latency
- Error locations and context
- **RED metrics** (Rate, Error, Duration) via Jaeger SPM
- Real-time performance visualization

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
- [Configuration](docs/configuration.md) — Environment variables and model assignment

---

## Coverage

<div align="center">

[![codecov sunburst](https://codecov.io/gh/ajbarea/kourai-khryseai/graphs/sunburst.svg?token=bNiUvETLLU)](https://app.codecov.io/gh/ajbarea/kourai-khryseai)
</div>

---

## License

[Apache 2.0](LICENSE)

---

<div align="center">
<sub>Built by <a href="https://github.com/ajbarea">AJ Barea</a> · Forged in the workshop of Hephaestus</sub>
</div>
