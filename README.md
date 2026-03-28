<div align="center">

# 🏛️ Κοῦραι Χρύσεαι

### **Kourai Khryseai** — *The Golden Maidens*

*Six specialized AI agents that collaborate with you on development—you guide each step, they show their work, iterate in real-time.*

[![A2A Protocol](https://img.shields.io/badge/A2A_Protocol-v0.4-4285F4?style=flat-square&logo=google&logoColor=white)](https://a2a-protocol.org)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![uv](https://img.shields.io/badge/uv-package_manager-DE5FE9?style=flat-square)](https://docs.astral.sh/uv/)
[![codecov](https://codecov.io/gh/ajbarea/kourai-khryseai/graph/badge.svg?token=bNiUvETLLU)](https://codecov.io/gh/ajbarea/kourai-khryseai)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE.md)

---

**Collaborate, don't automate. See your agents think. Guide them in real-time.**

```
$ make cli

❯ add user authentication

🔥 Hephaestus: I'm thinking through the approach...
📐 Metis: Specification drafted. Should we use JWT or sessions?

❯ JWT with refresh tokens

✅ Metis: Got it. Full spec: 8 steps, edge cases noted
⚙️ Techne: Writing files... (streaming changes live)
🧪 Dokimasia: Running tests... 12/12 passing
✨ Kallos: Code review complete, no style issues
📜 Mneme: Ready for commits
```

</div>

---

## What is this?

Kourai Khryseai is an **interactive multi-agent development system** where six specialized AI agents work *with* you, not *for* you. Instead of running autonomously in the background, agents stream their work in real-time, show their reasoning, and ask for guidance when decisions matter.

You describe your goal. The agents break it down, show you options, and execute your feedback. You see everything—from planning through testing through review—and can redirect at any step.

**Access it two ways:**
- **CLI** — Real-time agent output in your terminal
- **GUI** — Interactive dialogue with personality-matched voices and visual agent profiles

---

## The Agents

| Agent | Role | Strength |
|-------|------|----------|
| 🔥 **Hephaestus** | Orchestrator | Routes requests to the right specialists, manages feedback loops |
| 📐 **Metis** | Planner | Breaks goals into detailed specs, identifies edge cases |
| ⚙️ **Techne** | Coder | Reads existing patterns, writes clean changes |
| 🧪 **Dokimasia** | Tester | Writes comprehensive test suites, validates coverage |
| ✨ **Kallos** | Stylist | Enforces code quality, cleans comments and docstrings |
| 📜 **Mneme** | Scribe | Generates organized commit messages from diffs |

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

The orchestrator routes your request through a pipeline. Most requests flow: **Metis → Techne → Dokimasia → Kallos → Mneme**. Quick fixes skip planning. Pure styling requests skip coding. Hephaestus routes intelligently.

### 3. Agents Stream Their Work

Each agent shows you:
- **What they're thinking** — Real-time reasoning and planning
- **What they're building** — Code diffs, test runs, lint results
- **What they need** — Questions when decisions matter

```
📐 Metis: Analyzing requirements...
   → Should CSV use streaming for large files? (Option A: yes, Option B: no)

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
cd kourai_khryseai

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
make up           # Builds Docker images, starts all 6 agents + Jaeger + Prometheus
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
⚙️  Techne: Analyzing existing auth patterns...
   ↳ Found JWT middleware in src/middleware/auth.py
   ↳ Writing changes to 2 files...
   ↳ [100%] Complete
🧪 Dokimasia: Running tests...
   ↳ [5/5 passing]
...
```

### GUI (Desktop)

Visual interface with agent portraits, dialogue bubbles, and neural text-to-speech. Each agent has a personality-matched voice. Dialogue history is saved per session.

- 🎨 Full-color agent portraits (JRPG aesthetic)
- 💬 Real-time dialogue with streaming responses
- 🔊 Neural voice synthesis (Microsoft Edge TTS)
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
| **standard** | Sonnet | Opus | Sonnet | Sonnet | Haiku | Haiku |
| **smart** | Opus | Opus | Opus | Sonnet | Sonnet | Sonnet |

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
- **Tools** — [MCP](https://modelcontextprotocol.io/) (filesystem, git, shell)
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

[MIT](LICENSE)

---

<div align="center">
<sub>Built by <a href="https://github.com/ajbarea">AJ Barea</a> · Forged in the workshop of Hephaestus</sub>
</div>
