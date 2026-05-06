# Architecture

## 🎯 Design Principles

Kourai Khryseai is built around **transparency** and **interactivity**:

- **Specialization**: Each agent handles one discipline — planning, coding, testing, style, commits, companionship, romance, quality screening, or research validation. Specialists are focused and use appropriate model tiers.
- **Real-time feedback**: Agents stream their work as it happens. You don't wait for "final output"—you see reasoning in progress.
- **Human-on-the-loop**: When decisions matter (architecture choices, scope boundaries, validation rules), agents ask. You're never out of control.
- **Composable**: Agents are independent HTTP services. They can be deployed separately, tested independently, or replaced with custom implementations.
- **Observable**: Every request creates a distributed trace. See exactly what each agent did and how long it took.

---

## 🏛️ The Three Pillars: Monitor / Communicate / Control

Kourai Khryseai treats multi-agent software development as an
interpretability problem. Every coordination decision routes through
one of three pillars; each pillar maps to a concrete mechanism in code,
not a UX-only affordance.

### 🔭 Monitor — every step is observable

- **OpenTelemetry GenAI spans** wrap every LLM call across all 10
  agents (`shared/src/kourai_common/llm.py`).
- **Streamed Forge Transcript** broadcasts the full prior reasoning to
  every specialist before it speaks (see
  [Hephaestus ↔ Specialists](#hephaestus-specialists-the-forge-transcript)
  below).
- **Trace-ID injection** — `_OtelTraceFilter` in
  `shared/src/kourai_common/log.py:89` threads the active trace ID into
  every log record so a Jaeger span is grep-findable in Dozzle without
  any code change between observation and search.

### 💬 Communicate — agents pause when ambiguous

- **HOTL pause tokens** — Metis emits `PAUSE: <preference_kind>` when
  it would otherwise inline a one-time-per-project assumption (test
  coverage target, Python version, style rules). Resolved via slash
  command and persisted as a fact (M17 Phase 1).
- **CONFIRM_ORDER read-back** — Hephaestus emits a tiered read-back
  (`clear` / `smart` / `clarify`) before lighting the forge on any
  development task (M13).
- **A2A `INPUT_REQUIRED`** — see
  [Input Required: Clarification Loop](#input-required-clarification-loop)
  below for the mid-pipeline question / resume flow.

### 🛠️ Control — recovery is deliberate, not an edge case

- **Bounded Kallos⇅Techne repair loop** — when Kallos finds lint or
  style issues Techne can fix, Hephaestus iterates Techne→Kallos up to
  `KOURAI_MAX_ITERATIONS` rounds (default 5; see
  `shared/src/kourai_common/config.py:136` and
  `agents/hephaestus/agent.py:593`). Beyond the bound, the remainder
  is reported, not silently retried.
- **Graceful TTS auto-mute** — `is_audio_output_available()` in
  `shared/src/kourai_common/audio_env.py` probes PortAudio after cheap
  early-exits (env, headless Linux, WSL2-without-WSLg) so a missing
  audio device degrades to silent dialogue rather than crashing the
  agent (M6 / [#146](https://github.com/ajbarea/kourai-khryseai/pull/146)).
- **Retry with jitter** — `with_retry` in
  `shared/src/kourai_common/retry.py` wraps A2A and LLM calls in
  exponential backoff with ±20% jitter so concurrent agents hitting
  a 429 don't retry in lockstep ([#181](https://github.com/ajbarea/kourai-khryseai/pull/181)).

The poster abstract names these the **MCC pillars** and frames
transparency as a systems property. The unit suite under `tests/unit/`
exercises each — `test_pause_tag.py`, `test_pipeline.py`,
`test_metis_parallel.py`, `test_hooks_interaction.py`,
`test_executors.py` cover the load-bearing communicate / control
mechanisms; observability is exercised end-to-end via
`tests/integration/test_reasoning_quality.py` and the live trace path
through Jaeger.

---

## 🗺️ System Diagram

```mermaid
flowchart TD
    CLI["🖥️ <b>CLI REPL</b><br/><code>make cli</code>"]
    GUI["🎮 <b>Pygame GUI</b><br/><code>make gui</code>"]
    VN["📖 <b>Ren'Py VN</b><br/>Visual Novel"]
    HEP["🔥 <b>HEPHAESTUS</b><br/>Orchestrator · :10000<br/><i>LLM routing · pipeline · context</i>"]

    subgraph core ["Core Specialists"]
        MET["📐 <b>METIS</b><br/>Planner · :10001"]
        TEC["⚙️ <b>TECHNE</b><br/>Coder · :10002"]
        DOK["🧪 <b>DOKIMASIA</b><br/>Tester · :10003"]
        KAL["✨ <b>KALLOS</b><br/>Stylist · :10004"]
        MNE["📜 <b>MNEME</b><br/>Scribe · :10005"]
    end

    subgraph spirits ["Companion Spirits"]
        PUC["🎭 <b>PUCK</b><br/>Guide · :10006"]
        CUP["💘 <b>CUPID</b><br/>Romance · :10007"]
    end

    subgraph validators ["Quality Validators"]
        AID["🪞 <b>AIDOS</b><br/>Anti-Slop · :10008"]
        ALE["📚 <b>ALETHEIA</b><br/>Research · :10009"]
    end

    JAE["🔍 <b>JAEGER</b><br/>:16686 UI · :4318 OTLP"]
    PRO["📊 <b>PROMETHEUS</b><br/>:9090 UI · Metrics"]

    CLI -->|"A2A message/stream (SSE)"| HEP
    GUI -->|"A2A message/stream (SSE)"| HEP
    VNB["🌉 <b>VN-BRIDGE</b><br/>HTTP · :10010<br/><i>NDJSON streaming</i>"]
    VN -->|"HTTP (urllib)"| VNB
    VNB -->|"A2A message/stream"| HEP
    HEP -->|"A2A blocking"| MET
    HEP -->|"A2A blocking"| TEC
    HEP -->|"A2A blocking"| DOK
    HEP -->|"A2A blocking"| KAL
    HEP -->|"A2A blocking"| MNE
    HEP -->|"A2A on-demand"| PUC
    HEP -->|"A2A on-demand"| CUP
    HEP -->|"A2A on-demand"| AID
    HEP -->|"A2A on-demand"| ALE
    HEP -.->|"OTLP traces"| JAE
    JAE <-->|"RED metrics (SPM)"| PRO
```

---

## 🔗 Communication Patterns

### User ↔ Hephaestus: Streaming (SSE)

All three hosts (CLI, Pygame GUI, Ren'Py VN) connect to Hephaestus using A2A `message/stream` with Server-Sent Events. This means you see real-time progress as each agent reports status — not a single response after everything finishes. The VN connects through a dedicated **vn-bridge** Docker service (`:10010`) that translates between HTTP/NDJSON and the A2A protocol. Ren'Py sends requests via `urllib` to the bridge, which streams A2A events from Hephaestus and returns them as newline-delimited JSON.

```python
# CLI sends a streaming request
request = SendStreamingMessageRequest(
    id=str(uuid4()),
    params=MessageSendParams(
        message=Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=user_text))],
            context_id=context_id,
        ),
        configuration=MessageSendConfiguration(
            accepted_output_modes=["text"],
        ),
    ),
)

async for result in client.send_message_streaming(request):
    # TaskStatusUpdateEvent → progress messages
    # TaskArtifactUpdateEvent → final output
    ...
```

### Hephaestus ↔ Specialists: The Forge Transcript

Kourai Khryseai uses a **Human-on-the-Loop (HOTL)** architecture built around a shared **Forge Transcript**. Rather than passing each specialist only the previous agent's output, Hephaestus maintains a running dialogue log and broadcasts the **full transcript** to every specialist it calls.

The transcript grows with each step:

```
[User]: add user authentication
[Hephaestus]: Metis! Lay out the path. What does this forge need?
[Metis]: JWT with refresh token rotation, rate limiting on refresh...
[Hephaestus]: Well forged, Metis. Techne! Take what she's built and make it real.
[Techne]: Implementing src/auth/tokens.py and src/api/users.py...
```

This gives every agent full **group awareness** — Techne sees Metis's reasoning, Dokimasia sees what Techne actually wrote, Kallos sees the whole chain. No specialist works blind from a decontextualized stub.

Between every pipeline step, Hephaestus injects an **in-character narration line** (e.g., *"Dokimasia — put it through the fire."*) before calling the next specialist. These lines are streamed to the UI immediately so the forge feels alive during execution.

Execution remains sequential (Hephaestus awaits each specialist's final artifact before calling the next), but the _generation_ phase is entirely transparent — specialists stream their inner monologue in real-time via `AsyncGenerator` over A2A with `streaming=True`.

```python
# RemoteAgentConnection.send() — simplified
async for event in client.send_message(message):
    if isinstance(event, Message):
        yield ("result", extract_text(event))
    else:
        task, update = event
        if isinstance(update, TaskStatusUpdateEvent):
            yield ("status", extract_status(update))
```

### Direct Specialist Handoffs

Both the CLI and GUI support `@agent` mentions. A request starting with `@techne` bypasses Hephaestus's pipeline routing entirely, initiating a 1-on-1 conversation with that specialist directly.

### Input Required: Clarification Loop

When a specialist needs user input, it raises `AgentInputRequired`. Hephaestus catches this and yields an `INPUT_REQUIRED:` status. The CLI detects this state and prompts the user for follow-up, then resends to continue the pipeline.
