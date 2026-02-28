# Agent2Agent

I would like to build a multi-agent system called Kourai Khryseai based on the Golden Maidens -- woman-shaped, gold automotones crafted by the divine smith Hephaistos (Hephaestus) as attendants for his palace. This system is specifically going to be a tool meant to make my lazy ass code as alarming speeds using modern AI tools and protocols.

Protocols:
- MCP
- A2A

Agents:
- Planning - my shitty ideas or rough ideas into detailed requirements docs (kiro specialty)
- Coding - implementing detailed plans into code
- Testing - prioritize unit tests, then integration test, then performance test (retain 80%+ coverage)
- Style - run make clean, make lint, and/or make test - ensure all pass with no warnings or errors, HandOff to coding back and forth, and maybe planning?
- CommitMessageGenerator - follow my task for auto commiting groups of related changes into related commit messages following my specific prefs

https://github.com/i-am-bee/agentstack

<!-- 

Can you help me decide which architecture would be the best implementation of an agent stack for our Federated Learning framework? I figure one Top level Orchestrater would chat with the User, then underneath and behind the scenes would be a system of subagents that specialize in one area of the framework. One agent can be dedicated to datasets and huggingface dataset integration, one could be an agent specializing in config setup and validation, one can be an expert at examining the output data and plots and pngs and whatnot, one can be an expert in the federated learning algorithms and theories and strategies, etc.

What is the best way to plan and implement this idea? shoulf i update the @docs\FL_AGENT\ documentation or start from scratch with a new A2A multiagent system design. if the app idea grows large enough starting a new repo isnt out of the question.

-->

---

A2A Notes:

```markdown
# Agent Communication Protocols

## MCP (Model Context Protocol) — Anthropic, Nov 2024
Connects agents to tools, APIs, and resources (how an agent uses its capabilities).
E.g., a Weather agent uses MCP to call a Severe Weather Alert tool or a Current Weather API.

## A2A (Agent-to-Agent Protocol) — Google/IBM, 2025
Facilitates communication between agents (how agents collaborate, delegate, and manage shared tasks).
E.g., a Travel agent uses A2A to ask a Flight-booking agent to find tickets or a Car-rental agent to find rentals.

They work together: MCP handles what an agent can do; A2A handles how agents talk to each other.

---

# A2A Core Concepts

## Key Capabilities
- **Discovery** — agents advertise their capabilities so clients know when and how to use them
- **Negotiation** — clients and agents agree on communication methods (text, forms, iframe, audio, video)
- **Task & State Management** — agents communicate task status, changes, and dependencies throughout execution
- **Collaboration** — agents can request clarifications, extra information, or sub-actions from clients, other agents, or users

## Roles
- **Client Agent** — makes requests; the agent users interact with
- **Remote Agent** — receives and fulfills requests

## Agent Card
JSON file hosted at `/.well-known/agent-card.json`. Describes everything a client needs to communicate with a remote agent:
- Agent name, URI, and protocol bindings (JSON-RPC, gRPC, HTTP JSON)
- How to start a conversation and how to authenticate
- A2A protocol version, supported media types, and special capabilities (streaming, push notifications, extensions)

## Core Objects
- **Message** — one turn in a conversation; has a role (user | agent) and parts (text | file | JSON)
- **Task** — the job an agent needs to do; has a task_id and status
  - Active states: submitted, working, input-required
  - Terminal states: completed, failed
- **Artifact** — the actual output of a task; has an artifact_id and parts (text | file | JSON)

## Execution Modes
1. **Synchronous** — client sends a Message, remote responds immediately with a Message
2. **Asynchronous** — client sends a Message, remote returns a Task object; client polls `task_get` for updates until completed, with outputs in the Artifacts field
3. **Streaming (SSE)** — connection stays open; remote pushes Task updates, status events, artifact updates, and chunked data as they happen
4. **Push Notifications** — client provides a callback URL; remote pushes notifications to that URL when task state changes or an artifact is ready

---

# Orchestration & Tooling

## BeeAI Requirements Agent
Enforces rule-based constraints on agents and their tool use — what you can't enforce through prompting alone.
- Define ConditionalRequirements ahead of time to restrict which tools an agent can access
- E.g., if an agent has 10 tools but only 4 are appropriate for a given condition, only those 4 are exposed

A Requirements Agent is configured with:
- Name, description, and LLM config (model, caching, parallel tool calls)
- Tools: ThinkTool + other agents as HandoffTools
- Requirements: ConditionalRequirements that govern tool and agent access

## AgentStack
Open-source infrastructure for turning AI agents into running services, with a prebuilt GUI for interacting with agents.
- Handles security (TLS, HTTPS), authentication (agent card security scheme, token validation)
- Supports credential storage, extensions, and observability (OpenTelemetry)

---

# References
- A2A Protocol: https://a2a-protocol.org/latest
- A2A GitHub: https://github.com/a2aproject/A2A
- A2A Walkthrough: https://github.com/holtskinner/A2AWalkthrough
- ADK Quickstart (Exposing): https://google.github.io/adk-docs/a2a/quickstart-exposing/
- ADK Quickstart (Consuming): https://google.github.io/adk-docs/a2a/quickstart-consuming/
- LangGraph A2A Server: https://github.com/5enxia/langgraph-a2a-server
- MS Learn A2A: https://learn.microsoft.com/en-us/agent-framework/user-guide/agents/agent-types/a2a-agent
- BeeAI A2A: https://framework.beeai.dev/integrations/a2a
- BeeAI Requirements Agent: https://framework.beeai.dev/modules/agents/requirement-agent
- AgentStack Intro: https://agentstack.beeai.dev/stable/introduction/welcome
- AgentStack Quickstart: https://agentstack.beeai.dev/stable/introduction/quickstart
- AgentStack Python SDK: https://agentstack.beeai.dev/stable/agent-integration/overview
- AgentStack GitHub: https://github.com/i-am-bee/agentstack
- AgentStack Starter: https://github.com/i-am-bee/agentstack-starter
- AgentStack Healthcare Example: https://github.com/sandijean90/AgentStack-HealthcareAgent
- Tourist Scheduling Demo (ADK Multi-Agent): https://github.com/agntcy/agentic-apps/tree/main/tourist_scheduling_system
- A2A Summit 2025 - Agent Discovery: https://github.com/muscariello/a2a-summit-2025/blob/main/slides/ai-agent-discovery-slides.pdf
- Blog: Agents are not tools: https://discuss.google.dev/t/agents-are-not-tools/192812
- Google AI Studio API Keys: https://aistudio.google.com/app/api-keys
- Gemini API Keys: https://ai.google.dev/gemini-api/docs/api-key
- Gemini API Vertex AI Quickstart: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/start/quickstart
- Serper API Keys: https://serper.dev/api-keys
- uv: https://docs.astral.sh/uv/
- Flutter SDK: https://docs.flutter.dev/install
- Python Sample Agents https://github.com/a2aproject/a2a-samples/blob/main/samples/python/agents/README.md

```