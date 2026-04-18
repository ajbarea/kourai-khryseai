# Overview

## 🏛️ What is Kourai Khryseai?

Kourai Khryseai is an **interactive multi-agent development system** where ten specialized AI agents collaborate *with* you on software development. Instead of running autonomously, they stream their work in real-time, show their reasoning, and ask for guidance when decisions matter.

You describe what you need. Agents break it down, show options, execute your feedback, and iterate on your input. You're not delegating — you're directing.

Choose your experience: a fast terminal **CLI**, a rich desktop **Pygame GUI** with TTS and visual effects, or a **Ren'Py visual novel** with romance, affinity systems, and character progression.

---

## 🤝 Why Collaboration, Not Automation?

Single-agent tools struggle with multi-discipline problems. A real development task requires planning, coding, testing, review, and documentation. Rather than hoping one model handles all five well, Kourai splits them across **ten specialist agents** — six core developers, two companion spirits, and two quality validators.

**Better yet:** You're in the loop. When Metis says "should we use JWT or sessions?", you answer. When Techne hits an ambiguous pattern, they ask. When Kallos finds lint issues, Techne fixes them automatically, then asks if you're satisfied. Nothing surprises you.

---

## 👥 The Agents

### Core Specialists

| Agent | Role | You'll hear from them when... |
|-------|------|------|
| 🔥 **Hephaestus** | Orchestrator | Routing requests, managing pipelines, asking clarifying questions |
| 📐 **Metis** | Planner | Breaking goals into specs, identifying edge cases, asking architecture decisions |
| ⚙️ **Techne** | Coder | Writing code, explaining patterns, asking about ambiguous requirements |
| 🧪 **Dokimasia** | Tester | Creating test suites, reporting coverage, flagging untested branches |
| ✨ **Kallos** | Stylist | Finding style violations, improving docstrings, asking Techne to fix issues |
| 📜 **Mneme** | Scribe | Organizing git diffs into conventional commits, formatting messages |

### Companion Spirits

| Agent | Role | You'll see them when... |
|-------|------|------|
| 🎭 **Puck** | Companion | Tutorial guidance, idle nudges, minigame facilitation (always present) |
| 💘 **Cupid** | Romance | Relationship coaching, confession scenes, emotional moments (appears at 0.6+ affinity) |

### Quality Validators

| Agent | Role | They activate when... |
|-------|------|------|
| 🪞 **Aidos** | Anti-Slop | Detecting vague, corporate, or passive language in agent output |
| 📚 **Aletheia** | Research | Validating citations, checking claims, ensuring accuracy |

Each agent is an independent HTTP server communicating via the open [A2A (Agent-to-Agent) protocol](https://a2a-protocol.org). They can be deployed separately, tested independently, or swapped for custom implementations.

---

## 🔄 How a Request Actually Flows

This isn't a simple sequential pipeline where each agent hands off a single output to the next. Hephaestus acts as a **Forge Master** — a live moderator who maintains a running **Forge Transcript** of everything said by everyone. Before each specialist is called, Hephaestus narrates an in-character handoff line. Each specialist then receives the **full transcript** (not just the previous agent's output), so every agent has group awareness of all prior reasoning, decisions, and work.

??? info "Deep Dive: The Sequence Flow"

    ```mermaid
    sequenceDiagram
        actor You
        participant UI as CLI / GUI / VN
        participant Hep as 🔥 Hephaestus<br/>(Forge Master)
        participant Spec as Specialists

        You->>UI: "add user authentication"
        UI->>Hep: A2A stream (SSE)
        Hep->>Hep: Select pipeline · init transcript<br/>[User] + [Hephaestus] entries

        Note over Hep: 🔥 Narrates handoff in character
        Hep-->>UI: Forge narration (streamed)
        Hep->>Spec: Full transcript → Metis
        Note over Spec: 📐 Reads all context · analyzes
        Spec-->>UI: "JWT or sessions?"
        UI-->>You: Prompt for decision
        You->>UI: "JWT with refresh tokens"
        Hep->>Hep: Append [User] reply to transcript

        loop Each specialist in sequence
            Hep->>Hep: Append [Hephaestus] narration to transcript
            Note over Hep: 🔥 Narrates next handoff
            Hep-->>UI: Forge narration (streamed)
            Hep->>Spec: Full transcript → next agent
            Spec-->>UI: Status + findings (streamed)
            Hep->>Hep: Append [Agent] output to transcript
            UI-->>You: Live updates
        end

        Note over Spec: Kallos finds issues → Techne fixes → Kallos re-checks (max 3×)
        Hep-->>UI: Final summary
        UI-->>You: Done
    ```

    **Real conversation example:**

    ```
    ❯ add authentication to /api/users

    🔥 Hephaestus: Analyzing request...
       → Route: Metis → Techne → Dokimasia → Kallos → Mneme

    🔥 Hephaestus: "Metis! Lay out the path. What does this forge need?"

    📐 Metis: Spec in progress...
       • Found existing session middleware
       • Should we extend it or use JWT?

    ❯ JWT with refresh tokens

    📐 Metis: Got it. Specification:
       - JWT tokens (15min expiry)
       - Refresh token rotation
       - Rate limiting on token refresh
       ✅ Ready

    🔥 Hephaestus: "Well forged, Metis. Techne! Take what she's built and make it real."

    ⚙️ Techne: Implementing...
       • src/auth/tokens.py — JWT utilities
       • src/api/users.py — Auth middleware
       ✅ Complete

    🔥 Hephaestus: "Dokimasia — put it through the fire."

    🧪 Dokimasia: Testing... 8 tests, 92% coverage ✅

    🔥 Hephaestus: "Kallos. Standards."

    ✨ Kallos: Code review... all clear ✅
    🪞 Aidos: Language check... no slop ✅

    🔥 Hephaestus: "Mneme — seal the work."

    📜 Mneme: Commits ready:
       feat(auth): implement JWT authentication
       - Added JWT token generation and validation
       - Added refresh token rotation
       Files: src/auth/tokens.py, src/api/users.py, tests/...
    ```

---

## 🎯 Pipelines

Hephaestus automatically routes to the right pipeline:

| Request Type | Pipeline |
|---|---|
| *"implement feature X"* | 📐 → ⚙️ → 🧪 → ✨ → 📜 (Full stack) |
| *"fix bug in X"* | ⚙️ → 🧪 → ✨ → 📜 (No planning needed) |
| *"add tests for X"* | 🧪 → ✨ → 📜 (Testing-focused) |
| *"clean up X"* | ✨ → 📜 (Style only) |
| *"commit prep"* | 📜 (Just organize commits) |
| *"plan feature X"* | 📐 (Planning only) |
| *"@metis, why use async here?"* | 📐 (1-on-1 question) |

---

## 🔄 Human-on-the-Loop (HOTL) Design

Instead of silent automation, agents proactively engage when decisions matter:

**Ambiguous requirements?**
```
📐 Metis: Should CSV export support streaming for large files?
   [A] Yes—use async generator (slower startup, constant memory)
   [B] No—load and write all at once (faster start, high memory)

❯ A
```

**Conflicting linting issues?**
```
✨ Kallos: Found 3 issues...
⚙️ Techne: Fixing all 3... ✅
✨ Kallos: Re-checking... All clear!
```

**Nothing gets decided without you.** This prevents wasted tokens on speculation and keeps you in control of trade-offs.

---

## 💻 Three Ways to Play

### :octicons-terminal-24: CLI (Terminal)

Fast, scriptable, works anywhere (including SSH). Real-time agent output with emoji progress.

```bash
$ kourai "add pagination to /api/items"

🔥 Hephaestus: Routing...
📐 Metis: Spec drafted...
⚙️ Techne: Writing changes...
🧪 Dokimasia: Testing...
✨ Kallos: Reviewing...
📜 Mneme: Commits ready
```

### :octicons-device-desktop-24: Pygame GUI (Desktop)

Rich visual experience with agent portraits, dialogue bubbles, and personality-matched voices. Each agent has a distinct neural voice and visual appearance.

- 🎨 Full-color agent portraits with glow effects and crossfade transitions
- 💬 Real-time dialogue bubbles with streaming responses
- 🔊 Neural text-to-speech ([Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) local + Edge-TTS fallback) with real-time streaming
- 🌟 Golden particle system and typewriter effects
- ⚙️ Settings for voice customization and accessibility (WCAG 2.2 AA)

### :octicons-book-24: Ren'Py Visual Novel

A visual novel where the Golden Maidens aren't just tools — they're characters with personality, affinity, and romance routes.

- 🎭 Warm forge-fire colors and rich portrait aesthetic
- 💛 Affinity system — agents warm up as you work together (4 tiers: Professional → Intimate)
- 💘 Romance routes — confession scenes, jealousy moments, vulnerability
- 🎭 Companion spirits — Puck guides, Cupid coaches romance
- 📖 Gossip system — idle agents share personality-driven flavor text
- 💾 Full save/load with portrait thumbnails and conversation context

All three hosts connect to the **same Docker-hosted agent backend.** Your choice of experience doesn't change what the agents can do.

---

## 🔧 Built With

<div class="grid cards" markdown>

-   :material-api:{ .lg .middle } **Protocol**

    ---

    [A2A 0.4](https://a2a-protocol.org) — open agent-to-agent communication

-   :material-brain:{ .lg .middle } **LLM**

    ---

    [LiteLLM](https://docs.litellm.ai/) — Claude, Gemini, Ollama, local models

-   :material-language-python:{ .lg .middle } **Language**

    ---

    Python 3.12+ with modern type hints and Google docstrings

-   :material-server:{ .lg .middle } **Server**

    ---

    [Starlette](https://www.starlette.io/) + uvicorn via `a2a-sdk`

-   :material-magnify:{ .lg .middle } **Observability**

    ---

    [OpenTelemetry](https://opentelemetry.io/) → [Jaeger](https://www.jaegertracing.io/) + [Prometheus](https://prometheus.io/)

-   :material-docker:{ .lg .middle } **Containers**

    ---

    Docker + Docker Compose

-   :material-gamepad-variant:{ .lg .middle } **Visual Novel**

    ---

    [Ren'Py 8.5](https://www.renpy.org/) — HTTP bridge via `vn-bridge` Docker service (`:10010`)

-   :material-tools:{ .lg .middle } **Tools**

    ---

    [MCP](https://modelcontextprotocol.io/) servers (filesystem, git, shell)

</div>

---

## 🏛️ The Name

> *In Greek mythology, Hephaestus — god of fire and the forge — crafted the Κοῦραι Χρύσεαι (Golden Maidens): women-shaped automatons of living gold who served as intelligent attendants in his divine workshop. Each could think, speak, and work independently.*

Each agent is named after a Greek concept matching its function:

- **Hephaestus** — The master craftsman, god of the forge
- **Metis** — Goddess of wisdom and craft (mother of Athena)
- **Techne** — Art, craft, and technical skill
- **Dokimasia** — Scrutiny, examination, proof of competence
- **Kallos** — Beauty, elegance, aesthetic form
- **Mneme** — Memory (one of the original three Muses)
- **Puck** — The mischievous daimon, pragmatic guide
- **Cupid** — Eros, the force of love and connection
- **Aidos** — Shame, modesty, the mirror of honesty
- **Aletheia** — Truth, the unveiling of what is real
