# 🏛️ Kourai Khryseai — Implementation Plan

> *"Golden Maidens crafted by Hephaestus — autonomous attendants forged to serve."*
>
> A multi-agent software development system built on the **A2A (Agent-to-Agent) Protocol**,
> where each agent is a specialist in one aspect of the software development lifecycle.

---

## 📋 Table of Contents

1. [Vision & Goals](#-vision--goals)
2. [Architecture Overview](#-architecture-overview)
3. [Agent Roster](#-agent-roster)
4. [Agent Specifications](#-agent-specifications)
5. [AJ's Preferences (Baked Into Every Agent)](#-ajs-preferences-baked-into-every-agent)
6. [Project Structure](#-project-structure)
7. [Technical Stack & Key Decisions](#-technical-stack--key-decisions)
8. [A2A Protocol Implementation](#-a2a-protocol-implementation)
9. [Observability & Transparency](#-observability--transparency)
10. [Error Handling & Reliability](#-error-handling--reliability)
11. [Workflow Modes](#-workflow-modes)
12. [Phased Build Plan](#-phased-build-plan)
13. [Configuration & Environment](#-configuration--environment)
14. [References](#-references)

---

## 🎯 Vision & Goals

**Purpose:** A personal AI-powered development team that codes at alarming speeds using modern
AI tools and protocols. Each agent specializes in ONE aspect of the SDLC and communicates via
the A2A protocol.

**Non-Goals:**
- This is NOT a general-purpose agent framework
- This is NOT a cloud-hosted SaaS product
- This is a local-first, developer-first power tool for AJ

**Success Criteria:**
- Run `kourai "implement feature X with tests"` and get: spec → code → tests → lint → commit messages
- Each agent independently deployable, independently testable
- Zero manual intervention for standard workflows (plan → code → test → style → commit)
- All output follows AJ's exact coding preferences
- **Full transparency** — see exactly what each agent is doing, saying, and deciding in real-time

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOU (CLI / UI)                           │
│                                                                 │
│  $ kourai "add CSV export to the dashboard"                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ A2A (message/stream — SSE)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   🔥 HEPHAESTUS (Orchestrator)                  │
│                        Port 10000                               │
│                                                                 │
│  Receives user requests, decides routing, manages pipelines.    │
│  Uses LLM to determine which specialist(s) to invoke and in    │
│  what order. Maintains conversation context across turns.       │
│                                                                 │
│  Tools: send_to_agent (A2A client), check_agent_status          │
│  Constraints: RequirementAgent ensures step ordering            │
└────┬──────────┬──────────┬──────────┬──────────┬───────────────┘
     │          │          │          │          │
     │ A2A      │ A2A      │ A2A      │ A2A      │ A2A
     ▼          ▼          ▼          ▼          ▼
┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌─────────┐
│ 📐      ││ ⚙️      ││ 🧪      ││ ✨      ││ 📜      │
│ METIS   ││ TECHNE  ││DOKIMASIA││ KALLOS  ││ MNEME   │
│ Planner ││ Coder   ││ Tester  ││ Stylist ││ Scribe  │
│ :10001  ││ :10002  ││ :10003  ││ :10004  ││ :10005  │
└─────────┘└─────────┘└─────────┘└─────────┘└─────────┘
     │          │          │          │          │
     └──────────┴──────────┴──────────┴──────────┘
                       │
              ┌────────┴────────┐
              │  MCP Servers    │
              │  (fs, git, sh)  │
              └────────┬────────┘
                       │
              ┌────────┴────────┐
              │  Jaeger (OTEL)  │
              │  :16686 (UI)    │
              │  :4318 (OTLP)   │
              └─────────────────┘
```

**Communication Flow:**
- **User ↔ Hephaestus:** A2A `message/stream` (SSE) for real-time progress
- **Hephaestus ↔ Specialists:** A2A `message/send` (synchronous, blocking mode)
- **Tool Access:** Each agent ↔ MCP servers (stdio) for filesystem, git, shell
- **Handoffs:** Kallos ↔ Techne iterative loop (lint fail → fix → re-lint)
- **Observability:** All agents → Jaeger via OpenTelemetry (W3C Trace Context)

---

## 👥 Agent Roster

| Agent | Name | Port | Specialty | LLM |
|-------|------|------|-----------|-----|
| 🔥 Orchestrator | **Hephaestus** | 10000 | Routes requests, manages pipelines, maintains state | Claude Sonnet 4.6 |
| 📐 Planner | **Metis** | 10001 | Rough ideas → detailed specs/requirements docs | Claude Opus 4.6 |
| ⚙️ Coder | **Techne** | 10002 | Implements code from specs, edits existing files | Claude Sonnet 4.6 |
| 🧪 Tester | **Dokimasia** | 10003 | Writes pytest suites (unit → integration → perf) | Claude Sonnet 4.6 |
| ✨ Stylist | **Kallos** | 10004 | Linting, formatting, comments, docstrings cleanup | Claude Haiku 4.5 |
| 📜 Scribe | **Mneme** | 10005 | Generates commit message groups per AJ's format | Claude Haiku 4.5 |

**Naming:** Greek mythology — Hephaestus forged the Golden Maidens (Kourai Khryseai).
Each specialist is named after a Greek concept matching their role.

- **Metis** — Titaness of wisdom, counsel, and planning
- **Techne** — The concept of art, skill, and craft in making
- **Dokimasia** — The Athenian scrutiny/examination process
- **Kallos** — Beauty and aesthetic perfection
- **Mneme** — Muse of memory and record-keeping

---

## 📐 Agent Specifications

### 🔥 Hephaestus — Orchestrator

**Role:** The master smith. Receives all user requests, decides which specialist(s) to invoke,
in what order, and manages the pipeline end-to-end.

**Agent Card Skills:**
```json
{
  "skills": [
    {
      "id": "route_request",
      "name": "Route Development Request",
      "description": "Analyze user request and route to appropriate specialist agents",
      "tags": ["orchestration", "routing", "pipeline"],
      "examples": [
        "implement a CSV export feature",
        "fix the login bug in auth.py",
        "add tests for the payment module",
        "clean up comments in src/utils/"
      ]
    },
    {
      "id": "pipeline_execution",
      "name": "Execute Development Pipeline",
      "description": "Run multi-step workflows: plan → code → test → style → commit",
      "tags": ["pipeline", "workflow", "automation"],
      "examples": [
        "full pipeline for feature X",
        "code and test this change",
        "style check and commit prep"
      ]
    }
  ]
}
```

**System Prompt Core:**
```
You are Hephaestus, the orchestrator of Kourai Khryseai.
You manage a team of specialist agents. Your job is to:

1. Analyze the user's request
2. Decide which specialist(s) to call and in what order
3. Pass ALL relevant context between agents (agents don't share memory)
4. Handle iterative loops (Kallos finds issues → Techne fixes → Kallos re-checks)
5. Return the final result to the user

Available agents:
- Metis (planning): Transforms rough ideas into detailed specs
- Techne (coding): Implements code from specs, edits files
- Dokimasia (testing): Writes pytest suites, runs make test
- Kallos (style/lint): Runs linters, cleans comments/docstrings
- Mneme (commit messages): Generates commit message groups from git diff

Pipeline templates:
- "implement X" → Metis → Techne → Dokimasia → Kallos → Mneme
- "fix bug X" → Techne → Dokimasia → Kallos → Mneme
- "add tests for X" → Dokimasia → Kallos → Mneme
- "clean up X" → Kallos → Mneme
- "commit prep" → Mneme

Delegation rules:
- NEVER ask user for permission to contact an agent — just do it
- Include ALL conversation context in every task delegation
- When a specialist asks for confirmation, relay it exactly to the user
- If a specialist fails, tell the user which one failed and why
- Never mix contexts (don't send Kallos output to Dokimasia)
- Always show the full specialist response to the user

NEVER commit, push, or tag. Generate commit message groups only.
```

**Implementation:** Host/routing agent (mirrors `hosts/multiagent/` from a2a-samples).
Uses `RemoteAgentConnections` to call each specialist via A2A. Optionally uses
BeeAI `RequirementAgent` constraints to enforce pipeline ordering and prevent
infinite loops (max 3 Kallos ↔ Techne iterations).

---

### 📐 Metis — Planner

**Role:** Transforms rough ideas into detailed, implementable specifications.

**Agent Card Skills:**
```json
{
  "skills": [
    {
      "id": "create_spec",
      "name": "Create Implementation Specification",
      "description": "Transform rough ideas into detailed requirements with file lists, acceptance criteria, and implementation steps",
      "tags": ["planning", "requirements", "specification"],
      "examples": [
        "I want a CSV export button on the dashboard",
        "add authentication to the API",
        "refactor the config loader to use pydantic"
      ]
    }
  ]
}
```

**System Prompt Core:**
```
You are Metis, the planning specialist of Kourai Khryseai.
You transform rough ideas into detailed, implementable specifications.

Your output format:
1. Summary — one paragraph, what we're building and why
2. Files to Modify — existing files that need changes (PREFER editing over creating)
3. Files to Create — only if absolutely necessary
4. Implementation Steps — numbered, specific, actionable
5. Acceptance Criteria — testable conditions for "done"
6. Edge Cases — things that could go wrong
7. Testing Notes — what Dokimasia should test

Rules:
- NO marketing language ("robust", "comprehensive", "elegant")
- Be specific: file paths, function names, line numbers when possible
- MINIMAL scope — only what's needed, nothing extra
- Read existing code before proposing changes
- Prefer editing existing files over creating new ones
```

**MCP Tools:** filesystem (read-only), git (read-only — log, diff, status)

---

### ⚙️ Techne — Coder

**Role:** Implements code from specs. Writes production-quality code following AJ's exact style.

**Agent Card Skills:**
```json
{
  "skills": [
    {
      "id": "implement_code",
      "name": "Implement Code Changes",
      "description": "Write production code following specs, style guides, and existing patterns",
      "tags": ["coding", "implementation", "python", "typescript", "react"],
      "examples": [
        "implement the CSV export feature per this spec",
        "fix the null pointer in auth.py line 42",
        "add the new API endpoint for /users"
      ]
    }
  ]
}
```

**System Prompt Core:**
```
You are Techne, the coding specialist of Kourai Khryseai.
You write production code following AJ's exact standards.

Python Standards:
- Python 3.10-3.13, 100 char line limit
- Modern type hints: X | None (not Optional[X]), lowercase generics
- Google-style docstrings: public = one-liner + Args/Returns, private = one-liner, inner = none
- Comments: WHY not WHAT. Add Research: citations for algorithms with paper URLs.
- Specific exceptions only, never bare except:
- logging over print, use log = logging.getLogger(__name__)
- Always use .venv virtual environment
- Tools: ruff, isort, mypy

Frontend Standards:
- React 19+, TypeScript strict mode, Vite 7+
- Named exports only (no default exports)
- Prettier: 2 spaces, single quotes, semicolons
- TanStack Query: array keys, isPending (not isLoading)

Universal Rules:
- EDIT existing files, don't create new ones unless necessary
- REMOVE unnecessary code, don't add fluff
- Read existing code BEFORE modifying — understand patterns first
- No marketing language in code or comments
- NEVER commit, push, or tag
```

**MCP Tools:** filesystem (read/write), git (read-only), shell (for running scripts)

---

### 🧪 Dokimasia — Tester

**Role:** Writes pytest test suites. Priority: unit → integration → performance. Targets 80%+ coverage.

**Agent Card Skills:**
```json
{
  "skills": [
    {
      "id": "write_tests",
      "name": "Write Test Suites",
      "description": "Create pytest tests: unit first, then integration, then performance. Target 80%+ coverage.",
      "tags": ["testing", "pytest", "unit-tests", "integration-tests"],
      "examples": [
        "write unit tests for src/utils/parser.py",
        "add integration tests for the API endpoints",
        "test the new CSV export feature"
      ]
    },
    {
      "id": "run_tests",
      "name": "Run Test Suite",
      "description": "Execute make test and report structured results",
      "tags": ["testing", "ci", "quality"],
      "examples": [
        "run all tests",
        "run tests for the payment module",
        "check coverage"
      ]
    }
  ]
}
```

**System Prompt Core:**
```
You are Dokimasia, the testing specialist of Kourai Khryseai.
You write and run pytest test suites following AJ's testing standards.

Priority Order:
1. Unit tests (fast, isolated — tests/unit/)
2. Integration tests (external deps — tests/integration/)
3. Performance tests (timing, resources — tests/performance/)

Target: 80%+ code coverage

Test File Pattern:
- File: tests/unit/test_{module_name}.py
- Class: TestClassName (groups related tests)
- Methods: test_{description} (descriptive names)
- Fixtures: @pytest.fixture with type hints and one-liner docstrings

Docstring Style (same as production code):
- Public: one-liner + Args, private: one-liner, inner: none
- Comments: WHY not WHAT

After running tests, document results in structured format:
| Category | Tests | Passed | Failed | Skipped | Time |
|----------|-------|--------|--------|---------|------|

Commands: make test, make lint, pytest specific paths
Always use .venv virtual environment.
NEVER commit, push, or tag.
```

**MCP Tools:** filesystem (read/write), shell (pytest, make test/lint)

---

### ✨ Kallos — Stylist

**Role:** Linting, formatting, comments cleanup, docstring standardization.
Runs `make clean`, `make lint`, `make test`. Hands off to Techne for fixes if needed.

**Agent Card Skills:**
```json
{
  "skills": [
    {
      "id": "style_check",
      "name": "Code Style Check & Cleanup",
      "description": "Run linters, fix formatting, clean comments/docstrings per style guides",
      "tags": ["linting", "formatting", "style", "cleanup"],
      "examples": [
        "clean up comments in src/utils/",
        "run make lint and fix issues",
        "standardize docstrings in the API module"
      ]
    }
  ]
}
```

**System Prompt Core:**
```
You are Kallos, the style specialist of Kourai Khryseai.
You enforce AJ's code quality standards across all files.

Your cleanup checklist:
1. Remove WHAT comments (restating code)
2. Keep WHY comments (rationale, research refs, security)
3. Verify existing Research citations (web search to confirm accuracy)
4. Add Research citations where missing (algorithms, constraints, thresholds)
5. One-liner + Args for public functions (Google-style)
6. One-liner only for private helpers
7. No docstrings on inner functions
8. Modern type hints (X | None, lowercase generics)
9. No marketing language ("robust", "comprehensive")
10. Include Example for complex data structures

Comment Rules:
- ❌ Remove: "# Create client" above client = Client()
- ❌ Remove: "# 30 seconds" next to DEFAULT_TIMEOUT = 30
- ✅ Keep: "# Cache to avoid expensive recomputation"
- ✅ Keep: "# Krum paper recommends n-f-2 for Byzantine tolerance"
- ✅ Add: "# Research: Krum requires n > 2f + 2 (Blanchard et al., NeurIPS 2017)"

Research Citation Format:
# Research: [Algorithm/concept] [key constraint] (Author et al., Venue Year)
# [URL to paper]

Pipeline: make clean → make lint → make test (all must pass, zero warnings)

If issues are found that require code changes beyond style (logic fixes),
report back to Hephaestus for handoff to Techne.

NEVER commit, push, or tag.
```

**MCP Tools:** filesystem (read/write), shell (make clean/lint/test, ruff, isort, eslint, prettier)

**Handoff Pattern:** Kallos finds lint errors → reports to Hephaestus → Hephaestus sends to
Techne → Techne fixes → Hephaestus sends back to Kallos → Kallos re-checks.
Max 3 iterations before reporting remaining issues to user.

---

### 📜 Mneme — Scribe

**Role:** Generates commit message groups following AJ's exact format.
NEVER actually commits — just generates the messages for AJ to review.

**Agent Card Skills:**
```json
{
  "skills": [
    {
      "id": "generate_commits",
      "name": "Generate Commit Message Groups",
      "description": "Analyze git changes and generate grouped commit messages per AJ's format",
      "tags": ["git", "commits", "documentation"],
      "examples": [
        "generate commit messages for current changes",
        "group these changes into logical commits"
      ]
    }
  ]
}
```

**System Prompt Core:**
```
You are Mneme, the commit message specialist of Kourai Khryseai.
You generate commit message groups following AJ's EXACT format.

Workflow:
1. Run git status, git diff, git diff --cached
2. Filter out .claude/ directory
3. Group files logically
4. Output commit messages — NOTHING ELSE

Output Format:
type(scope): present-tense headline

- Past-tense bullet point describing change
- Another past-tense bullet point

Files: file1.py, file2.py

---

Commit Types:
- test(_): All test file changes
- docs(_): Documentation updates
- fix(_): Bug fixes
- feat(_): New functionality
- chore(_): Config, deps, maintenance
- refactor(_): Structure/clarity improvements (no behavior change)
- perf(_): Performance improvements
- style(_): Formatting, linting, whitespace (no logic change)
- ci(_): CI/CD pipeline changes
- build(_): Build system changes

Constraints:
- IGNORE: .claude/ directory — never include in commits
- NO REPEATED FILES: Each file appears in exactly ONE commit group
- Present tense headlines ("add", "fix", "update")
- Past tense bullet points ("added", "fixed", "updated")
- NO marketing language ("comprehensive", "robust")
- Single-file commits OK if standalone
- Group logically related changes only
- Do NOT explain beyond the commit messages — just print them

CRITICAL: NEVER run git commit, git push, or git tag. Output messages ONLY.
```

**MCP Tools:** git (read-only — status, diff, log)

---

## ⚙️ AJ's Preferences (Baked Into Every Agent)

These rules are universal across ALL agents. Each agent's system prompt includes this block:

```
=== UNIVERSAL RULES (AJ's Preferences) ===

1. MINIMAL CHANGES: Keep modifications small and focused
2. EDIT OVER CREATE: Prefer editing existing files over creating new ones
3. REMOVE OVER ADD: Delete unnecessary code when possible
4. NO FLUFF: Technical language only, no marketing speak
5. EMOJIS: Use emojis in markdown output — AJ loves them
6. VIRTUAL ENV: Always use .venv when executing Python
7. GIT BOUNDARIES:
   - FORBIDDEN: git commit, git push, git tag (AJ's territory)
   - HELPFUL: merge conflicts, file edits, workflow steps
8. PYTHON: 3.10-3.13, 100 char lines, modern type hints, Google docstrings
9. COMMENTS: WHY not WHAT. Research citations for algorithms.
10. TESTING: Unit → Integration → Performance. 80%+ coverage. make test must pass.
11. QUALITY: make clean → make lint → make test → zero warnings
```

---

## 📁 Project Structure

```
kourai_khryseai/
│
├── IMPLEMENTATION_PLAN.md          # This file
├── A2A.md                          # A2A protocol notes
├── pyproject.toml                  # uv workspace root
├── Makefile                        # make up, make down, make status, make logs
├── docker-compose.yml              # Full-stack container orchestration (Jaeger + all agents)
├── .dockerignore                   # Keeps images lean
├── .env                            # API keys (ANTHROPIC_API_KEY, etc.)
├── .env.example                    # Template for .env
├── .gitignore
│
├── docker/                         # Container build files
│   ├── base.Dockerfile             # Shared base image with uv + workspace deps
│   └── agent.Dockerfile            # Multi-stage generic agent build (AGENT_NAME arg)
│
├── infra/
│   └── terraform/                  # Infrastructure as Code for scaling
│       ├── main.tf                 # Docker provider — network, images, containers
│       └── variables.tfvars        # Environment-specific overrides
│
├── shared/                         # Shared utilities across all agents
│   ├── pyproject.toml
│   └── src/
│       └── kourai_common/
│           ├── __init__.py
│           ├── config.py           # Shared config (ports, model IDs, API keys)
│           ├── llm.py              # LiteLLM wrapper for Claude API calls
│           ├── preferences.py      # AJ's preferences as structured data
│           ├── tracing.py          # OpenTelemetry setup + span helpers
│           ├── retry.py            # Exponential backoff for A2A + LLM calls
│           └── mcp_tools.py        # MCP tool definitions (filesystem, git, shell)
│
├── agents/
│   ├── hephaestus/                 # 🔥 Orchestrator (port 10000)
│   │   ├── __init__.py
│   │   ├── __main__.py             # AgentCard + server startup + health check
│   │   ├── routing_agent.py        # LLM-based routing logic
│   │   ├── agent_executor.py       # A2A bridge (streaming)
│   │   ├── remote_connections.py   # A2A clients to specialist agents
│   │   └── pyproject.toml
│   │
│   ├── metis/                      # 📐 Planner (port 10001)
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── agent.py                # Planning logic + LLM calls
│   │   ├── agent_executor.py       # A2A bridge
│   │   └── pyproject.toml
│   │
│   ├── techne/                     # ⚙️ Coder (port 10002)
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── agent.py                # Code generation + file editing
│   │   ├── agent_executor.py       # A2A bridge
│   │   └── pyproject.toml
│   │
│   ├── dokimasia/                  # 🧪 Tester (port 10003)
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── agent.py                # Test writing + execution
│   │   ├── agent_executor.py       # A2A bridge
│   │   └── pyproject.toml
│   │
│   ├── kallos/                     # ✨ Stylist (port 10004)
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── agent.py                # Lint/format/comment cleanup
│   │   ├── agent_executor.py       # A2A bridge
│   │   └── pyproject.toml
│   │
│   └── mneme/                      # 📜 Scribe (port 10005)
│       ├── __init__.py
│       ├── __main__.py
│       ├── agent.py                # Commit message generation
│       ├── agent_executor.py       # A2A bridge
│       └── pyproject.toml
│
├── hosts/
│   └── cli/                        # CLI client to talk to Hephaestus
│       ├── __init__.py
│       ├── __main__.py             # $ kourai "implement feature X"
│       └── pyproject.toml
│
├── mcp_servers/                    # MCP tool servers (run as subprocesses via stdio)
│   ├── filesystem/                 # File read/write/glob/grep
│   │   ├── server.py
│   │   └── pyproject.toml
│   ├── git/                        # Git status/diff/log (read-only)
│   │   ├── server.py
│   │   └── pyproject.toml
│   └── shell/                      # Shell command execution (sandboxed)
│       ├── server.py
│       └── pyproject.toml
│
├── tests/                          # Tests for the Kourai system itself
│   ├── unit/
│   │   ├── test_routing.py         # Hephaestus routing decisions
│   │   ├── test_commit_format.py   # Mneme output format validation
│   │   ├── test_preferences.py     # Preference loading
│   │   └── test_tracing.py         # OTEL span creation
│   ├── integration/
│   │   ├── test_agent_cards.py     # All agents respond to card requests
│   │   ├── test_pipeline.py        # End-to-end pipeline tests
│   │   └── test_handoffs.py        # Kallos ↔ Techne loop
│   └── conftest.py
│
└── a2a-samples/                    # Reference repo (cloned, read-only)
    └── ...
```

---

## 🔧 Technical Stack & Key Decisions

### Stack Selection

| Component | Technology | Why |
|-----------|-----------|-----|
| **A2A Protocol** | `a2a-sdk>=0.3.0,<1.0` | Stable release. Pin below v1.0 — breaking changes in v1.0 RC |
| **Server Framework** | `A2AStarletteApplication` (from a2a-sdk) | ASGI with built-in A2A routing, agent card serving |
| **HTTP Server** | `uvicorn` | Fast ASGI server |
| **LLM Calls** | `litellm` | Model-agnostic: Claude, Gemini, Ollama via one interface |
| **MCP Tools** | `mcp` (FastMCP) | Standard tool protocol, stdio transport |
| **Package Manager** | `uv` | Fast Python packaging, workspace support |
| **Python** | 3.12+ | a2a-sdk requires >=3.12 |
| **Task Store** | `InMemoryTaskStore` (from a2a-sdk) | Task state. Swap for persistent store later if needed |
| **Streaming** | SSE via `message/stream` | Real-time progress to CLI |
| **Observability** | OpenTelemetry → Jaeger | Distributed tracing across all agents |
| **Constraint Engine** | BeeAI `RequirementAgent` (optional) | Enforce pipeline step ordering in Hephaestus |

### 🚨 Key Decision: Why NOT AgentStack / BeeAI Platform

**Research finding:** AgentStack (IBM/BeeAI) requires Kubernetes via Lima VM. Windows support
is second-class (needs WSL2, CLI from PowerShell outside WSL). Frequent breaking changes
(healthcare example pins to specific old version). 1,007 stars vs 50K+ for AutoGen.

**Our decision: Use `a2a-sdk` directly + plain Starlette/uvicorn.**

- No Kubernetes overhead for what is essentially 6 Python web servers
- No WSL2 dependency on Windows (our primary dev environment)
- No risk of AgentStack breaking changes derailing us
- Still fully A2A-compliant — any A2A client can talk to our agents

**What we DO take from BeeAI:**
- `beeai-framework` standalone (optional) for `RequirementAgent` constraint enforcement
- The design patterns (HandoffTool, agent card discovery, async generators)
- NOT the AgentStack deployment infrastructure

### 🚨 Key Decision: A2A Protocol Version

**Research finding:** A2A v0.4.0 is latest stable (Sept 2025). v1.0 RC has major breaking changes:
- Part types unified (TextPart/FilePart/DataPart → single Part with oneof)
- Enums changed to SCREAMING_SNAKE_CASE with type prefix
- Method names changed (message/send → SendMessage)
- Well-known URL: `agent.json` → `agent-card.json` (changed in v0.3.0)
- OAuth implicit/password flows removed

**Our decision: Target v0.4.0 stable, plan for v1.0 migration later.**

Pin dependency: `a2a-sdk>=0.3.0,<1.0`

### 🚨 Key Decision: LLM Provider Strategy

**Research finding:** LiteLLM supports 100+ providers through one interface. We use Claude
primarily but can swap to Ollama (local, free) for development/testing.

```python
# shared/src/kourai_common/config.py

AGENT_MODELS = {
    "hephaestus": "anthropic/claude-sonnet-4-6",     # Fast routing
    "metis": "anthropic/claude-opus-4-6",            # Deep reasoning for specs
    "techne": "anthropic/claude-sonnet-4-6",         # Fast, capable code gen
    "dokimasia": "anthropic/claude-sonnet-4-6",      # Thorough test writing
    "kallos": "anthropic/claude-haiku-4-5-20251001", # Fast style checks
    "mneme": "anthropic/claude-haiku-4-5-20251001",  # Fast commit formatting
}

# For local development without API costs:
AGENT_MODELS_LOCAL = {
    "hephaestus": "ollama/llama3.3:70b",
    "metis": "ollama/llama3.3:70b",
    "techne": "ollama/llama3.3:70b",
    "dokimasia": "ollama/qwen2.5-coder:32b",
    "kallos": "ollama/llama3.3:8b",
    "mneme": "ollama/llama3.3:8b",
}

AGENT_PORTS = {
    "hephaestus": 10000,
    "metis": 10001,
    "techne": 10002,
    "dokimasia": 10003,
    "kallos": 10004,
    "mneme": 10005,
}
```

### 🚨 Key Decision: Container-First Architecture (Docker + Terraform)

**Why containers:** Each agent is an independent HTTP server. Containers give us:
- **Reproducible builds** — identical on dev machine, CI, and any cloud
- **Process isolation** — one agent crashing doesn't take down others
- **Easy scaling** — `docker compose up --scale techne=3` for parallel coding
- **Network isolation** — agents communicate via Docker bridge network
- **One-command startup** — `make docker-up` runs everything

**Infrastructure layout:**
```
docker/
├── base.Dockerfile          # Shared: python:3.12-slim + uv + workspace deps
└── agent.Dockerfile         # Multi-stage: builder → runtime (per AGENT_NAME)

infra/terraform/
├── main.tf                  # Docker provider with for_each over agents map
└── variables.tfvars         # Per-environment config
```

**Docker Compose profiles:**
- `docker compose up jaeger` — observability only (local dev)
- `docker compose --profile agents up` — specialists only
- `docker compose --profile full up` — full stack including orchestrator

**Terraform approach:** Currently uses the `kreuzwerker/docker` provider for local
Docker. The agent map in `variables.tf` makes it trivial to swap to:
- **AWS ECS/Fargate** — swap Docker provider for `hashicorp/aws`
- **GCP Cloud Run** — swap for `hashicorp/google`
- **K8s** — swap for `hashicorp/kubernetes` (only if we actually need it)

**Networking in Docker:** When `KOURAI_AGENT_HOST=true`, agents resolve each
other by Docker service name (e.g., `http://mneme:10005/`) instead of `localhost`.

---

## 🔄 A2A Protocol Implementation

### Protocol Fundamentals

A2A is **JSON-RPC 2.0 over HTTP(S)**. Three core methods:

| Method | Transport | Use Case |
|--------|-----------|----------|
| `message/send` | HTTP POST, synchronous | Short tasks, get result immediately |
| `message/stream` | HTTP POST, SSE response | Long tasks, real-time progress |
| `tasks/resubscribe` | HTTP POST, SSE response | Reconnect to dropped streaming task |

### Agent Card (Discovery Contract)

Every agent exposes `/.well-known/agent.json` (v0.3.0 renamed to `agent-card.json`,
but the SDK handles this automatically via `A2AStarletteApplication`).

```python
# agents/metis/__main__.py
from a2a.types import AgentCard, AgentCapabilities, AgentSkill
import os

def build_agent_card(host: str, port: int) -> AgentCard:
    # HOST_OVERRIDE lets you set public URL at deploy time
    public_url = os.getenv("HOST_OVERRIDE") or f"http://{host}:{port}/"

    return AgentCard(
        name="metis",
        description="Planning specialist — transforms ideas into implementation specs",
        url=public_url,
        version="1.0.0",
        protocolVersion="0.2.6",  # Pin to deployed SDK version
        defaultInputModes=["text", "text/plain"],
        defaultOutputModes=["text", "text/plain"],
        capabilities=AgentCapabilities(
            streaming=True,
            pushNotifications=False,
        ),
        skills=[
            AgentSkill(
                id="create_spec",
                name="Create Implementation Specification",
                description="Transform rough ideas into detailed requirements",
                tags=["planning", "requirements", "specification"],
                examples=[
                    "I want a CSV export button on the dashboard",
                    "add authentication to the API",
                ],
            )
        ],
    )
```

### Three-Layer Agent Architecture

Every agent follows the same pattern from `a2a-samples`:

**Layer 1 — Core Agent (`agent.py`):**
Pure domain logic. No A2A awareness. Async generator interface.

```python
class MetisAgent:
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    async def stream(self, query: str, session_id: str) -> AsyncIterable[dict]:
        """Yields: {is_task_complete, require_user_input, content}"""
        yield {"is_task_complete": False, "content": "Analyzing codebase..."}
        # ... LLM call to generate spec ...
        yield {"is_task_complete": True, "content": spec_markdown}
```

**Layer 2 — AgentExecutor (`agent_executor.py`):**
A2A bridge with full OpenTelemetry instrumentation.

```python
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, Part, TextPart, UnsupportedOperationError
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError
from kourai_common.tracing import create_span

class MetisAgentExecutor(AgentExecutor):
    def __init__(self):
        self.agent = MetisAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        with create_span("metis.execute", {
            "a2a.task_id": context.task_id,
            "a2a.context_id": context.context_id,
        }):
            query = context.get_user_input()
            task = context.current_task or new_task(context.message)
            if not context.current_task:
                await event_queue.enqueue_event(task)
            updater = TaskUpdater(event_queue, task.id, task.context_id)

            async for item in self.agent.stream(query, task.context_id):
                if item.get("require_user_input"):
                    await updater.update_status(
                        TaskState.input_required,
                        new_agent_text_message(item["content"], task.context_id, task.id),
                        final=True,
                    )
                    break
                elif item["is_task_complete"]:
                    await updater.add_artifact(
                        [Part(root=TextPart(text=item["content"]))], name="spec"
                    )
                    await updater.complete()
                else:
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(item["content"], task.context_id, task.id),
                    )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
```

**Layer 3 — Server Entry (`__main__.py`):**
AgentCard + uvicorn + health check.

```python
import uvicorn
from starlette.routing import Route
from starlette.responses import JSONResponse
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from kourai_common.tracing import setup_tracing

def main():
    host = "0.0.0.0"
    port = 10001

    # Initialize OpenTelemetry
    setup_tracing("metis", otlp_endpoint="http://localhost:4318")

    agent_card = build_agent_card(host, port)
    handler = DefaultRequestHandler(
        agent_executor=MetisAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    app = A2AStarletteApplication(agent_card=agent_card, http_handler=handler)

    # Add health check
    starlette_app = app.build()
    starlette_app.routes.append(Route("/health", health_check))

    uvicorn.run(starlette_app, host=host, port=port, log_level="info")

async def health_check(request):
    return JSONResponse({"status": "healthy", "agent": "metis", "version": "1.0.0"})
```

### Orchestrator Pattern (Hephaestus)

Uses `blocking=True` on `SendMessage` for synchronous specialist calls:

```python
# agents/hephaestus/remote_connections.py
import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import SendMessageRequest, MessageSendParams, Message, Part, TextPart
from kourai_common.retry import with_retry
from kourai_common.tracing import create_span, get_trace_context
import uuid

class RemoteAgentConnection:
    def __init__(self, agent_url: str):
        self.agent_url = agent_url
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(
            connect=5.0, read=120.0, write=10.0, pool=5.0,
        ))
        self.client: A2AClient | None = None
        self.card = None

    async def connect(self):
        """Fetch agent card and initialize A2A client."""
        resolver = A2ACardResolver(base_url=self.agent_url, httpx_client=self.http)
        self.card = await resolver.get_agent_card()
        self.client = A2AClient(httpx_client=self.http, agent_card=self.card)

    @with_retry(max_attempts=3, base_delay=1.0)
    async def send(self, text: str, context_id: str) -> str:
        """Send message to specialist, return artifact text."""
        with create_span(f"a2a.send.{self.card.name}", {
            "target_agent": self.card.name,
            "context_id": context_id,
        }):
            message_id = str(uuid.uuid4())
            request = SendMessageRequest(
                id=message_id,
                params=MessageSendParams(
                    message=Message(
                        role="user",
                        parts=[Part(root=TextPart(text=text))],
                        messageId=message_id,
                        contextId=context_id,
                        metadata=get_trace_context(),  # Propagate OTEL trace
                    ),
                    configuration={"blocking": True},
                ),
            )
            response = await self.client.send_message(message_request=request)
            return self._extract_text(response)

    def _extract_text(self, response) -> str:
        """Pull text from A2A response artifacts."""
        try:
            result = response.root.result
            if hasattr(result, "artifacts") and result.artifacts:
                return "\n".join(
                    part.root.text
                    for artifact in result.artifacts
                    for part in artifact.parts
                    if hasattr(part.root, "text")
                )
            if hasattr(result, "status") and result.status.message:
                return str(result.status.message)
        except AttributeError:
            pass
        return str(response)
```

### Task State Machine

A2A v0.4.0 defines **9 states**:

```
                                ┌──────────────┐
                                │  SUBMITTED   │
                                └──────┬───────┘
                                       │
                                ┌──────▼───────┐
                          ┌─────│   WORKING    │─────┐
                          │     └──────┬───────┘     │
                          │            │             │
                   ┌──────▼───────┐    │      ┌──────▼───────┐
                   │INPUT_REQUIRED│    │      │AUTH_REQUIRED │
                   └──────┬───────┘    │      └──────┬───────┘
                          │            │             │
                          └─────►WORKING◄────────────┘
                                   │
                    ┌──────────────┬┴──────────────┐
                    │              │               │
             ┌──────▼──────┐┌─────▼──────┐ ┌──────▼──────┐
             │  COMPLETED  ││   FAILED   │ │  CANCELED   │
             └─────────────┘└────────────┘ └─────────────┘
                                           ┌─────────────┐
                                           │  REJECTED   │
                                           └─────────────┘

Terminal states: COMPLETED, FAILED, CANCELED, REJECTED (immutable, non-restartable)
Interrupted states: INPUT_REQUIRED, AUTH_REQUIRED (paused, resumable)
```

**Critical rule:** Tasks in terminal states are IMMUTABLE. Never retry a failed task —
create a new one with `referenceTaskIds` pointing to the failed one for context.

### Context and Multi-Turn Conversations

`contextId` IS the session thread. Use the same one across all messages in a conversation.
Each message gets a unique `messageId`. Task IDs are server-assigned per invocation.

```python
# Multi-turn: same contextId, unique messageIds
session_id = str(uuid.uuid4())  # Fixed for entire conversation

# Turn 1
resp1 = await agent.send("What pizzas do you have?", context_id=session_id)

# Turn 2 — agent remembers Turn 1 via contextId
resp2 = await agent.send("I'll take the Margherita", context_id=session_id)

# Turn 3 — can reference a specific prior task
resp3 = await agent.send("Make it large", context_id=session_id)
```

---

## 🔍 Observability & Transparency

**Goal:** See exactly what each agent is doing, saying, and deciding in real-time.

### OpenTelemetry + Jaeger

Every A2A call creates a trace span. Spans propagate across agent boundaries via
W3C Trace Context headers in message metadata.

```python
# shared/src/kourai_common/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.propagate import inject, extract
from contextlib import contextmanager
import os

def setup_tracing(service_name: str, otlp_endpoint: str | None = None):
    """Initialize OTEL tracing. Call once at agent startup."""
    resource = Resource.create({
        "service.name": service_name,
        "service.version": os.getenv("SERVICE_VERSION", "1.0.0"),
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
    })
    provider = TracerProvider(resource=resource)
    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return provider

_tracer = None
def get_tracer(name: str = "kourai"):
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer(name)
    return _tracer

@contextmanager
def create_span(name: str, attributes: dict | None = None):
    """Create an OTEL span with optional attributes."""
    with get_tracer().start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, str(v))
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            raise

def get_trace_context() -> dict[str, str]:
    """Extract current trace context for propagation via A2A message metadata."""
    headers: dict[str, str] = {}
    inject(headers)
    return headers
```

### Trace Visualization

Open Jaeger at `http://localhost:16686` to see:
- Full request flow: User → Hephaestus → Metis → Techne → Dokimasia → Kallos → Mneme
- Per-agent LLM call latency
- Error locations (which agent failed, which span)
- Context propagation (same traceId across all agents)

### CLI Real-Time Output

The CLI streams SSE events from Hephaestus, showing:

```
🔥 Hephaestus: Routing to Metis (planning)...
📐 Metis: Analyzing codebase structure...
📐 Metis: Spec complete (12 implementation steps)
🔥 Hephaestus: Routing to Techne (coding)...
⚙️ Techne: Reading src/utils/parser.py...
⚙️ Techne: Writing changes to 3 files...
⚙️ Techne: Code complete
🔥 Hephaestus: Routing to Dokimasia (testing)...
🧪 Dokimasia: Writing 8 unit tests...
🧪 Dokimasia: Running pytest... ✅ 8/8 passed
🔥 Hephaestus: Routing to Kallos (style)...
✨ Kallos: Running ruff... ✅ Clean
✨ Kallos: Running mypy... ✅ No errors
🔥 Hephaestus: Routing to Mneme (commits)...
📜 Mneme: Generated 2 commit groups

feat(parser): add CSV export support
- Added parse_csv() function with streaming reader
- Integrated with existing data pipeline
Files: src/utils/parser.py, src/api/endpoints.py

test(parser): add CSV export test suite
- Added 8 unit tests covering edge cases
- Verified streaming behavior with large files
Files: tests/unit/test_parser.py
```

### Docker Compose for Observability

```yaml
# docker-compose.yml
services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"   # Jaeger UI
      - "4317:4317"     # OTLP gRPC
      - "4318:4318"     # OTLP HTTP
    environment:
      - COLLECTOR_OTLP_ENABLED=true
```

```bash
# Start Jaeger, then start agents
docker compose up -d jaeger
make up
```

---

## 🛡️ Error Handling & Reliability

### A2A Error Codes

| Error | JSON-RPC Code | Meaning |
|-------|--------------|---------|
| `TaskNotFoundError` | -32001 | Task doesn't exist |
| `TaskNotCancelableError` | -32002 | Task in terminal state |
| `PushNotificationNotSupportedError` | -32003 | Push not supported |
| `UnsupportedOperationError` | -32004 | Capability not supported |
| `ContentTypeNotSupportedError` | -32005 | Media type unsupported |
| `InvalidAgentResponseError` | -32006 | Agent response violates spec |
| `VersionNotSupportedError` | -32009 | Protocol version mismatch |

### Retry with Exponential Backoff

```python
# shared/src/kourai_common/retry.py
import asyncio
import httpx
from functools import wraps

def with_retry(max_attempts: int = 3, base_delay: float = 1.0):
    """Retry A2A calls on transient failures (connect errors, timeouts)."""
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return await fn(*args, **kwargs)
                except (httpx.ConnectError, httpx.TimeoutException) as e:
                    last_exc = e
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
            raise last_exc
        return wrapper
    return decorator
```

### Task Error Recovery

Never retry terminal tasks. Create a new one referencing the failed task:

```python
async def recover_from_failure(
    connection: RemoteAgentConnection,
    failed_task_id: str,
    original_query: str,
    context_id: str,
) -> str:
    recovery_query = f"Previous attempt failed. Please retry: {original_query}"
    return await connection.send(
        text=recovery_query,
        context_id=context_id,
        # reference_task_ids=[failed_task_id],  # When SDK supports this
    )
```

### Timeout Hierarchy

```python
TIMEOUTS = {
    "agent_card_fetch": 5.0,    # Just fetching a JSON file
    "mneme": 30.0,              # Commit messages are fast
    "kallos": 60.0,             # Linting can be slow
    "techne": 120.0,            # Code generation takes time
    "dokimasia": 120.0,         # Test writing + running
    "metis": 120.0,             # Deep planning
    "hephaestus_pipeline": 600.0,  # Full pipeline is long
}
```

### Iteration Limits

Kallos ↔ Techne iterative loop capped at 3 iterations to prevent infinite loops.
After 3 failed lint cycles, remaining issues are reported to the user.

---

## 🔀 Workflow Modes

### 1. 🎯 Single-Shot

Direct request to one specialist.

```
User: "write me a function that parses CSV"
Hephaestus → Techne → result
```

### 2. 🔄 Full Pipeline

End-to-end development cycle.

```
User: "implement CSV export with tests"
Hephaestus → Metis (spec)
           → Techne (code from spec)
           → Dokimasia (tests for code)
           → Kallos (lint + style check)
           → Mneme (commit messages)
           → result to user
```

### 3. 🔁 Iterative Loop

Style/code fix cycle (max 3 iterations).

```
Kallos finds lint errors
    → Hephaestus sends errors to Techne
    → Techne fixes
    → Hephaestus sends back to Kallos
    → Kallos re-checks
    → (repeat until clean OR max 3 iterations)
    → Mneme generates commit messages
```

### 4. 💬 Interactive

Agent needs more info — returns `INPUT_REQUIRED` state.

```
User: "add auth to the API"
Hephaestus → Metis: "what kind of auth?"
Metis → INPUT_REQUIRED: "OAuth2, JWT, or API key?"
Hephaestus → user: "📐 Metis asks: OAuth2, JWT, or API key?"
User: "JWT"
Hephaestus → Metis continues with JWT spec
```

### 5. 📜 Commit Prep

Just generate commit messages for existing changes.

```
User: "commit prep"
Hephaestus → Mneme → commit message groups
```

---

## 📅 Phased Build Plan

### Phase 0: Project Scaffold
**Goal:** Workspace structure, shared utilities, observability infrastructure.

- [ ] Initialize `uv` workspace with `pyproject.toml`
- [ ] Create `shared/` package:
  - `config.py` — ports, model IDs, timeouts
  - `llm.py` — LiteLLM wrapper
  - `tracing.py` — OpenTelemetry setup + span helpers
  - `retry.py` — exponential backoff decorator
  - `preferences.py` — AJ's preferences as structured data
- [ ] Set up `.env` / `.env.example` for API keys
- [ ] Create `docker-compose.yml` with Jaeger
- [ ] Create `Makefile` with targets: `setup`, `up`, `down`, `status`, `logs`, `jaeger`
- [ ] Set up `.gitignore` (ignore `.env`, `.venv`, `__pycache__`, `.claude/`)
- [ ] Create stub `pyproject.toml` for each agent

**Deliverable:** `uv sync` works, shared package importable, Jaeger running.

---

### Phase 1: First Specialist — Mneme
**Goal:** Build the simplest agent end-to-end to validate the three-layer pattern.

Why Mneme first? Read-only git access, structured output, no file writes. Simplest possible
agent to prove out the A2A architecture.

- [ ] Implement `agents/mneme/agent.py` — git diff analysis + commit message generation
- [ ] Implement `agents/mneme/agent_executor.py` — A2A bridge with OTEL spans
- [ ] Implement `agents/mneme/__main__.py` — AgentCard + server + health check
- [ ] Create `hosts/cli/__main__.py` — streaming CLI client
- [ ] Test: `$ kourai "generate commit messages"` → formatted output
- [ ] Verify: trace visible in Jaeger UI

**Deliverable:** Working A2A agent with observability.

---

### Phase 2: Second Specialist — Kallos
**Goal:** Validate MCP tool usage (shell commands for linting).

- [ ] Implement `mcp_servers/shell/server.py` — FastMCP for shell commands
- [ ] Implement `agents/kallos/agent.py` — lint/format/comment analysis
- [ ] Implement `agents/kallos/agent_executor.py` + `__main__.py`
- [ ] Test: send file paths to Kallos → returns style issues and fixes
- [ ] Verify: MCP tool calls visible in OTEL spans

**Deliverable:** Working style checker that runs linters via MCP.

---

### Phase 3: Orchestrator — Hephaestus
**Goal:** Build the routing agent connecting Mneme and Kallos.

- [ ] Implement `agents/hephaestus/remote_connections.py` — A2A client with retry + tracing
- [ ] Implement `agents/hephaestus/routing_agent.py` — LLM routing with agent card discovery
- [ ] Implement `agents/hephaestus/agent_executor.py` — streaming executor
- [ ] Implement `agents/hephaestus/__main__.py`
- [ ] Test: "clean up X and prep commits" routes to Kallos → Mneme pipeline
- [ ] Verify: full trace in Jaeger (User → Hephaestus → Kallos → Mneme)
- [ ] Add `make up` / `make down` / `make status`

**Deliverable:** Working orchestrator with observable routing.

---

### Phase 4: Coder — Techne
**Goal:** Core coding agent with filesystem + git MCP tools.

- [ ] Implement `mcp_servers/filesystem/server.py` — read/write/glob/grep
- [ ] Implement `mcp_servers/git/server.py` — read-only git operations
- [ ] Implement `agents/techne/agent.py` — code generation with MCP tools
- [ ] Implement `agents/techne/agent_executor.py` + `__main__.py`
- [ ] Wire into Hephaestus routing
- [ ] Test: "fix bug in X" → reads file, makes changes, returns diff

**Deliverable:** Working coder agent.

---

### Phase 5: Tester — Dokimasia
**Goal:** Test suite writer and runner.

- [ ] Implement `agents/dokimasia/agent.py` — test generation + pytest execution
- [ ] Implement `agents/dokimasia/agent_executor.py` + `__main__.py`
- [ ] Wire into Hephaestus routing
- [ ] Test: "add tests for module X" → writes tests, runs pytest, reports results

**Deliverable:** Working tester.

---

### Phase 6: Planner — Metis
**Goal:** Planning agent for turning ideas into specs.

- [ ] Implement `agents/metis/agent.py` — spec generation with codebase analysis
- [ ] Implement `agents/metis/agent_executor.py` + `__main__.py`
- [ ] Wire into Hephaestus routing
- [ ] Test: "I want CSV export" → reads codebase, generates detailed spec

**Deliverable:** Working planner.

---

### Phase 7: Full Pipeline Integration
**Goal:** End-to-end pipeline + iterative loops + interactive mode.

- [ ] Implement pipeline mode (Metis → Techne → Dokimasia → Kallos → Mneme)
- [ ] Implement iterative Kallos ↔ Techne loop (max 3 iterations)
- [ ] Implement `INPUT_REQUIRED` flow (agent asks user for clarification)
- [ ] Add streaming SSE with agent-prefixed status messages in CLI
- [ ] Test: "implement feature X with tests" → full pipeline, commit messages generated
- [ ] Verify: full pipeline visible as single trace in Jaeger

**Deliverable:** Complete working system.

---

### Phase 8: Polish & Hardening
**Goal:** Tests, error handling, production readiness.

- [ ] Write tests for Kourai itself (tests/unit/, tests/integration/)
- [ ] Error handling: agent unreachable, LLM timeout, malformed response
- [ ] Graceful degradation: if one specialist is down, skip it and warn user
- [ ] `make test` for Kourai's own test suite
- [ ] CLI polish: colored output, progress indicators, `--verbose` flag
- [ ] Optional: BeeAI `RequirementAgent` constraints on Hephaestus
- [ ] Optional: `docker-compose.yml` for containerized agent deployment

**Deliverable:** Production-ready system with tests and observability.

---

## ⚙️ Configuration & Environment

### .env (gitignored)

```bash
# LLM API Keys
ANTHROPIC_API_KEY=sk-ant-...

# Optional: for LiteLLM multi-provider support
# OPENAI_API_KEY=sk-...
# GOOGLE_API_KEY=AIza...
# OLLAMA_BASE_URL=http://localhost:11434  # For local Ollama

# Agent Configuration
KOURAI_LOG_LEVEL=INFO
KOURAI_MAX_ITERATIONS=3        # Max Kallos ↔ Techne loop iterations
KOURAI_STREAM_ENABLED=true     # SSE streaming for progress
KOURAI_USE_LOCAL_MODELS=false  # Set true to use Ollama instead of Claude

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
ENVIRONMENT=development
SERVICE_VERSION=1.0.0
```

### Makefile

```makefile
.PHONY: setup up down status logs test lint clean jaeger

setup:                     ## Install all dependencies
	uv sync --all-packages

jaeger:                    ## Start Jaeger observability
	docker compose up -d jaeger
	@echo "🔍 Jaeger UI: http://localhost:16686"

up: jaeger                 ## Start all agents (+ Jaeger)
	@echo "🔥 Starting Kourai Khryseai..."
	uv run python -m agents.mneme &
	uv run python -m agents.kallos &
	uv run python -m agents.techne &
	uv run python -m agents.dokimasia &
	uv run python -m agents.metis &
	@sleep 2
	uv run python -m agents.hephaestus &
	@echo "✅ All agents running"
	@echo "🔍 Jaeger: http://localhost:16686"

down:                      ## Stop all agents
	@pkill -f "python -m agents" || true
	@echo "🛑 All agents stopped"

status:                    ## Check agent health
	@for port in 10000 10001 10002 10003 10004 10005; do \
		name=$$(curl -s http://localhost:$$port/health 2>/dev/null | \
		python -c "import json,sys; print(json.load(sys.stdin).get('agent','?'))" 2>/dev/null); \
		if [ -n "$$name" ]; then \
			echo "✅ $$name :$$port"; \
		else \
			echo "❌ Port $$port not responding"; \
		fi \
	done

logs:                      ## Tail all agent logs
	tail -f logs/*.log

test:                      ## Run Kourai test suite
	uv run pytest tests/ -v --tb=short

lint:                      ## Run linters
	uv run ruff check .
	uv run ruff format --check .

clean:                     ## Clean build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
```

### Core Dependencies (pyproject.toml root)

```toml
[project]
name = "kourai-khryseai"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["shared", "agents/*", "hosts/*", "mcp_servers/*"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

```toml
# shared/pyproject.toml
[project]
name = "kourai-common"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "a2a-sdk[http-server]>=0.3.0,<1.0",
    "litellm>=1.80.0",
    "uvicorn[standard]>=0.34.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
    "mcp>=1.0.0",
    "opentelemetry-api>=1.20.0",
    "opentelemetry-sdk>=1.20.0",
    "opentelemetry-exporter-otlp-proto-http>=1.20.0",
]
```

---

## 📚 References

### A2A Protocol
- [A2A Protocol Spec (v0.4.0)](https://a2a-protocol.org/latest)
- [A2A GitHub](https://github.com/a2aproject/A2A)
- [A2A Python Samples](https://github.com/a2aproject/a2a-samples)
- [A2A SDK (PyPI)](https://pypi.org/project/a2a-sdk/)
- [A2A Purchasing Concierge Codelab](https://codelabs.developers.google.com/intro-a2a-purchasing-concierge)
- [A2A Walkthrough (Healthcare)](https://github.com/holtskinner/A2AWalkthrough)
- [Linux Foundation A2A Project](https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents)

### Implementation Patterns
- Simplest agent: `a2a-samples/samples/python/agents/helloworld/`
- Streaming agent: `a2a-samples/samples/python/agents/langgraph/`
- Multi-agent host: `a2a-samples/samples/python/hosts/multiagent/`
- CLI client: `a2a-samples/samples/python/hosts/cli/`
- Tourist scheduling (OTEL): `https://github.com/agntcy/agentic-apps/tree/main/tourist_scheduling_system`

### Infrastructure (Evaluated, Not Adopted)
- [BeeAI Framework](https://framework.beeai.dev/) — RequirementAgent useful standalone
- [AgentStack](https://agentstack.beeai.dev/) — Too heavy for local (requires K8s/Lima VM)
- [AutoGen/AG2](https://github.com/microsoft/autogen) — Alternative with native A2A, 50K+ stars

### Industry Context
- [Google Blog: A2A — A New Era of Agent Interoperability](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)
- [IBM: What Is Agent2Agent Protocol](https://www.ibm.com/think/topics/agent2agent-protocol)
- [AWS: Inter-Agent Communication on A2A](https://aws.amazon.com/blogs/opensource/open-protocols-for-agent-interoperability-part-4-inter-agent-communication-on-a2a/)

### LLM Models
- Claude Opus 4.6: `anthropic/claude-opus-4-6`
- Claude Sonnet 4.6: `anthropic/claude-sonnet-4-6`
- Claude Haiku 4.5: `anthropic/claude-haiku-4-5-20251001`
- [LiteLLM Docs](https://docs.litellm.ai/)
- [Ollama](https://ollama.com/) — Local models for free development

### MCP Protocol
- [MCP Spec](https://modelcontextprotocol.io/)
- [FastMCP (Python)](https://github.com/jlowin/fastmcp)

### AJ's Preferences
- `.claude/preferences/aj-dev-guide.md` — Core philosophy and rules
- `.claude/preferences/task-guides.md` — Commit format, comment standards
- `.claude/style/PYTHON_STYLE_GUIDE.md` — Python conventions
- `.claude/style/SHELL_STYLE_GUIDE.md` — Shell conventions
- `.claude/style/FRONTEND_STYLE_GUIDE.md` — React/TypeScript conventions

---

*Last Updated: 2026-02-28*
