# Overview

## 🏛️ What is Kourai Khryseai?

Kourai Khryseai is an **interactive multi-agent development system** where ten specialized AI agents collaborate *with* you on software development. Instead of running autonomously, they stream their work in real-time, show their reasoning, and pause for guidance when decisions matter.

You describe what you need. Agents break it down, show options, execute on your feedback, and iterate. You're not delegating — you're directing.

Three interfaces share the same Docker-hosted backend: a fast terminal **CLI**, a Pygame **GUI** with portraits and TTS, and a Ren'Py **visual novel** with affinity tiers and romance routes. See **[Getting Started](getting-started.md)** for installation and a first request.

---

## 🤝 Why ten agents?

Single-agent tools struggle with multi-discipline problems. A development task usually requires planning, coding, testing, review, and documentation. Rather than hoping one model handles all five well, Kourai splits them across **ten specialist agents** — six core developers, two companion spirits, and two quality validators.

Specialists run as independent HTTP servers communicating via the open [A2A protocol](https://a2a-protocol.org), so any one of them can be deployed separately, tested in isolation, or replaced with a custom implementation.

| Tier | Agents | Purpose |
|---|---|---|
| **Core specialists** | 🔥 Hephaestus, 📐 Metis, ⚙️ Techne, 🧪 Dokimasia, ✨ Kallos, 📜 Mneme | Plan / code / test / style / commit |
| **Companion spirits** | 🎭 Puck, 💘 Cupid | Tutorial, idle nudges, romance coaching |
| **Quality validators** | 🪞 Aidos, 📚 Aletheia | Anti-slop screening + research validation |

Per-agent detail lives in the **[Agents Overview](agents/index.md)** and **[Agents Reference](agents/specialists.md)**.

---

## 🔄 How a request actually flows

Hephaestus is a **Forge Master**, not a switchboard. It maintains a running **Forge Transcript** of the whole exchange and broadcasts the *full transcript* to every specialist it calls.

Each specialist sees the complete prior reasoning (Techne reads Metis's spec, Kallos reads everything Techne wrote, and so on), so no agent works blind from a decontextualized stub.

Between steps, Hephaestus emits an in-character narration line that streams to the host immediately so the forge feels alive while specialists generate.

??? info "Sequence diagram + a real dialogue excerpt"

    <div class="kseq" markdown="0">
      <div class="kseq-step"><span class="kseq-route">You → UI</span><span class="kseq-msg">"add user authentication"</span></div>
      <div class="kseq-step"><span class="kseq-route">UI → Hephaestus</span><span class="kseq-msg">A2A stream (SSE)</span></div>
      <div class="kseq-step kseq-self"><span class="kseq-route">Hephaestus</span><span class="kseq-msg">CONFIRM_ORDER read-back</span></div>
      <div class="kseq-step"><span class="kseq-route">Hephaestus → UI</span><span class="kseq-msg">"Forge will plan + scaffold + test. Light it?"</span></div>
      <div class="kseq-step"><span class="kseq-route">You → UI</span><span class="kseq-msg">yes</span></div>
      <div class="kseq-step kseq-self"><span class="kseq-route">Hephaestus</span><span class="kseq-msg">select pipeline · init transcript</span></div>
      <div class="kseq-loop">
        <div class="kseq-loop-h">loop · each specialist in sequence</div>
        <div class="kseq-step"><span class="kseq-route">Hephaestus → UI</span><span class="kseq-msg">Forge narration (streamed)</span></div>
        <div class="kseq-step"><span class="kseq-route">Hephaestus → Specialist</span><span class="kseq-msg">full transcript → next agent</span></div>
        <div class="kseq-step"><span class="kseq-route">Specialist → UI</span><span class="kseq-msg">status + findings (streamed)</span></div>
        <div class="kseq-step"><span class="kseq-route">UI → You</span><span class="kseq-msg">live updates</span></div>
      </div>
      <div class="kseq-note">Kallos finds issues → Techne fixes → Kallos re-checks (up to MAX_ITERATIONS, default 5)</div>
      <div class="kseq-step"><span class="kseq-route">Hephaestus → UI</span><span class="kseq-msg">final summary</span></div>
      <div class="kseq-step"><span class="kseq-route">UI → You</span><span class="kseq-msg">Done</span></div>
    </div>

    A trimmed real example:

    ```
    ❯ add authentication to /api/users

    🔥 Hephaestus: "Plan + JWT + tests + commit. Light the forge?"
    ❯ yes

    🔥 Hephaestus: "Metis! Lay out the path."
    📐 Metis:  spec ready (JWT 15m, refresh rotation, rate-limit on refresh)

    🔥 Hephaestus: "Techne! Take what she's built and make it real."
    ⚙️ Techne:  src/auth/tokens.py + src/api/users.py written

    🧪 Dokimasia: 8 tests, 92% coverage ✅
    ✨ Kallos:    style review clean ✅
    📜 Mneme:    feat(auth): implement JWT authentication ...
    ```

Execution stays sequential (Hephaestus awaits each specialist's final artifact before calling the next), but generation is fully transparent — specialists stream their inner monologue in real-time via `AsyncGenerator` over A2A with `streaming=True`.

---

## 🎯 Pipelines

Hephaestus's LLM router selects from a small set of templates:

| Request type | Pipeline |
|---|---|
| *"implement feature X"* | 📐 → ⚙️ → 🧪 → ✨ → 📜 (full stack) |
| *"fix bug in X"* | ⚙️ → 🧪 → ✨ → 📜 (no planning needed) |
| *"add tests for X"* | 🧪 → ✨ → 📜 (testing-focused) |
| *"clean up X"* | ✨ → 📜 (style only) |
| *"commit prep"* | 📜 (just organize commits) |
| *"plan feature X"* | 📐 (planning only) |
| *"@metis, why use async here?"* | 📐 (1-on-1 question) |

---

## 🔄 Human-on-the-loop

Two mechanisms keep you in the loop:

1. **`CONFIRM_ORDER`** — every dev pipeline runs a pre-flight read-back. Hephaestus emits a tiered confirmation card (clear / smart / clarify) and pauses; the player confirms or redirects before any tokens get spent. `/yolo` opts out for power users.
2. **`AgentInputRequired`** — any specialist can pause mid-pipeline. Metis pauses on architecture trade-offs; Techne pauses on ambiguous patterns; Kallos pauses if a fix loop saturates. The CLI / GUI / VN all surface the question and resume on the player's reply.

```
📐 Metis: Should CSV export support streaming for large files?
   [A] Yes—use async generator (slower startup, constant memory)
   [B] No—load and write all at once (faster start, high memory)

❯ A
```

Nothing decisive happens silently — that prevents wasted tokens on speculation and keeps trade-offs in your hands.

---

## 🔧 Built with

<div class="grid cards" markdown>

-   :material-api:{ .lg .middle } **Protocol** — [A2A](https://a2a-protocol.org), open agent-to-agent (pinned `>=1.0,<2.0`; M7 cutover shipped 2026-04-30)
-   :material-brain:{ .lg .middle } **LLM** — [LiteLLM](https://docs.litellm.ai/) wrapping Anthropic, Google, and Ollama
-   :material-language-python:{ .lg .middle } **Language** — Python `>=3.12,<3.14`
-   :material-server:{ .lg .middle } **Server** — [Starlette](https://www.starlette.io/) + uvicorn via `a2a-sdk`
-   :material-magnify:{ .lg .middle } **Observability** — OpenTelemetry → Jaeger v2 + Prometheus v3 + Dozzle
-   :material-docker:{ .lg .middle } **Containers** — Docker + Docker Compose (one image per agent, single shared `Dockerfile`)
-   :material-gamepad-variant:{ .lg .middle } **Visual novel** — [Ren'Py 8.5.x](https://www.renpy.org/) via the `vn-bridge` Docker service (`:10010`)
-   :material-tools:{ .lg .middle } **Tools** — [MCP](https://modelcontextprotocol.io/) servers (`forge`, `shell`)

</div>

---

## 🏛️ The name

> *In Greek mythology, Hephaestus — god of fire and the forge — crafted the Κοῦραι Χρύσεαι (Golden Maidens): women-shaped automatons of living gold who served as intelligent attendants in his divine workshop. Each could think, speak, and work independently.*

Each agent is named after a Greek concept matching its function: **Hephaestus** (god of the forge), **Metis** (wisdom and craft), **Techne** (technical skill), **Dokimasia** (scrutiny and proof), **Kallos** (beauty and form), **Mneme** (memory), **Puck** (the mischievous daimon), **Cupid** (eros), **Aidos** (the mirror of honesty), and **Aletheia** (truth, the unveiling of what is real).
