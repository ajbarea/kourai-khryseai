# Architecture

## 🗺️ System Diagram

```mermaid
flowchart TD
    CLI["🖥️ <b>CLI REPL</b><br/><code>make cli</code>"]
    HEP["🔥 <b>HEPHAESTUS</b><br/>Orchestrator · :10000<br/><i>LLM routing · pipeline · context accumulation</i>"]
    MET["📐 <b>METIS</b><br/>Planner · :10001"]
    TEC["⚙️ <b>TECHNE</b><br/>Coder · :10002"]
    DOK["🧪 <b>DOKIMASIA</b><br/>Tester · :10003"]
    KAL["✨ <b>KALLOS</b><br/>Stylist · :10004"]
    MNE["📜 <b>MNEME</b><br/>Scribe · :10005"]
    JAE["🔍 <b>JAEGER</b><br/>:16686 UI · :4318 OTLP"]

    CLI -->|"A2A message/stream (SSE)"| HEP
    HEP -->|"A2A blocking"| MET
    HEP -->|"A2A blocking"| TEC
    HEP -->|"A2A blocking"| DOK
    HEP -->|"A2A blocking"| KAL
    HEP -->|"A2A blocking"| MNE
    HEP -.->|"OTLP traces"| JAE
    MET -.-> JAE
    TEC -.-> JAE
    DOK -.-> JAE
    KAL -.-> JAE
    MNE -.-> JAE
```

---

## 🔗 Communication Patterns

### User ↔ Hephaestus: Streaming (SSE)

The CLI connects to Hephaestus using A2A `message/stream` with Server-Sent Events. This means you see real-time progress as each agent reports status — not a single response after everything finishes.

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

### Hephaestus ↔ Specialists: Synchronous

Hephaestus calls specialists using A2A `message/send` with `blocking=True`. This makes each call synchronous — Hephaestus waits for one specialist to complete before calling the next.

```python
# RemoteAgentConnection.send() — simplified
request = SendMessageRequest(
    id=message_id,
    params=MessageSendParams(
        message=Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=user_text))],
            context_id=context_id,
            metadata=get_trace_context(),  # W3C trace headers
        ),
        configuration=MessageSendConfiguration(blocking=True),
    ),
)
response = await client.send_message(request)
```

### Input Required: Clarification Loop

When a specialist needs user input, it raises `AgentInputRequired`. Hephaestus catches this and yields an `INPUT_REQUIRED:` status. The CLI detects this state and prompts the user for follow-up, then resends to continue the pipeline.
