# NE Agents Day 2026 — Kourai Khryseai

**Title:** Kourai Khryseai: Transparent Human-on-the-Loop Multi-Agent Software Development

**Author:** AJ Barea, Rochester Institute of Technology (`ajb6289@rit.edu`)

**Advisor:** Dr. Leon Reznik

**Venue:** North-East AI Agents Day 2026

**Date:** Friday, May 8, 2026

**Location:** Jane Street, New York, NY

**Downloads:**

- [kourai-khryseai-poster.pdf](kourai-khryseai-poster.pdf) — conference poster (48 × 36 in, print quality)
- [kourai-khryseai-extended-abstract.pdf](kourai-khryseai-extended-abstract.pdf) — accepted extended abstract

<img src="kourai-khryseai-poster.jpg" class="research-poster" alt="Kourai Khryseai conference poster — Transparent Human-on-the-Loop Multi-Agent Software Development, organized around Monitor / Communicate / Control pillars with a Hephaestus orchestrator, specialist agents, an OpenTelemetry trace showing HOTL pauses and a bounded repair loop, claim-driven evaluation, and one-backend-three-hosts screenshots">

## Abstract

Multi-agent coding systems are increasingly capable, but their coordination decisions are often opaque to the supervisor. Kourai Khryseai treats multi-agent software development as an interpretability problem and organizes the system around three pillars — **Monitor**, **Communicate**, and **Control**. A Hephaestus orchestrator routes requests to specialist agents for planning, coding, testing, style review, and commit synthesis. Every step is observable through OpenTelemetry GenAI spans and a streamed Forge transcript (Monitor); agents pause to request clarification when requirements are ambiguous (Communicate); and a bounded Kallos⇅Techne repair loop plus graceful degradation make recovery deliberate rather than an edge case (Control). The backend combines independent A2A-connected services, MCP-based tool use, shared local SQLite state, and end-to-end tracing through OpenTelemetry, Jaeger, and Prometheus. The same orchestration layer powers a CLI, desktop GUI, and visual-novel-style interface, enabling studies of interface and embodiment without changing backend logic. Claim-driven tests anchor each MCC property to a mechanism in code: transparency is treated as a systems property, not just a UX choice.

**Keywords:** AI agents, multi-agent systems, software engineering, human-on-the-loop, interpretability, observability
