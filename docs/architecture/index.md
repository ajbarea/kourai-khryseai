# Architecture

## 🎯 Design Principles

Kourai Khryseai is built around **transparency** and **interactivity**:

- **Specialization**: Each agent handles one discipline — planning, coding, testing, style, commits, companionship, romance, quality screening, or research validation. Specialists are focused and use appropriate model tiers.
- **Real-time feedback**: Agents stream their work as it happens. You don't wait for "final output"—you see reasoning in progress.
- **Human-on-the-loop**: When decisions matter (architecture choices, scope boundaries, validation rules), agents ask. You're never out of control.
- **Composable**: Agents are independent HTTP services. They can be deployed separately, tested independently, or replaced with custom implementations.
- **Observable**: Every request creates a distributed trace. See exactly what each agent did and how long it took.

---

## 🗺️ System Diagram

```mermaid
flowchart TD
    CLI["🖥️ <b>CLI REPL</b><br/><code>make cli</code>"]
    GUI["🎮 <b>Pygame GUI</b><br/><code>make gui</code>"]
    VN["📖 <b>Ren'Py VN</b><br/>Hades-inspired"]
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
    VN -->|"JSON IPC (subprocess)"| HEP
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

All three hosts (CLI, Pygame GUI, Ren'Py VN) connect to Hephaestus using A2A `message/stream` with Server-Sent Events. This means you see real-time progress as each agent reports status — not a single response after everything finishes. The VN uses a subprocess JSON IPC bridge that translates between Ren'Py and the A2A protocol.

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

### Hephaestus ↔ Specialists: Asynchronous Streaming (HOTL)

Kourai Khryseai utilizes a **Human-on-the-Loop (HOTL)** architecture. Hephaestus calls specialists using an asynchronous `AsyncGenerator` wrapper over the A2A client with `streaming=True`. 

This enables specialists to actively stream their "inner monologues" (e.g., `⚙️ Coding: def parse_ast(node)...`) to Hephaestus, which immediately pipes them back to the GUI. The execution of the pipeline remains sequential (Hephaestus waits for Techne's final artifact before calling Dokimasia), but the _generation_ phase is entirely transparent.

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

To facilitate true conversational interaction, the GUI supports `@agent` mentions. A request starting with `@techne` will bypass Hephaestus's normal pipeline routing logic entirely, instantly initiating a 1-on-1 pipeline with that agent.

### Input Required: Clarification Loop

When a specialist needs user input, it raises `AgentInputRequired`. Hephaestus catches this and yields an `INPUT_REQUIRED:` status. The CLI detects this state and prompts the user for follow-up, then resends to continue the pipeline.
