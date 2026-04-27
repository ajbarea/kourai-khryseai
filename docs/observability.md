# Observability

Three browser tabs cover the full diagnostic surface for the agent stack. One command opens all three.

```bash
make observe
```

Opens **Jaeger** (`:16686`), **Prometheus** (`:9090`), and **Dozzle** (`:8888`) in your default browser. Cross-platform (Linux, macOS, Windows, WSL2 — see `scripts/observe.py` for the platform handling).

---

## Mental model

| Pane | Category | The question it answers |
|---|---|---|
| **Jaeger** | traces | *Where did this request go?* — A2A hops, MCP tool calls, full pipeline timing |
| **Prometheus** | metrics | *How often / how slow?* — rates, durations, percentile latencies |
| **Dozzle** | logs | *What is THIS agent saying right now?* — per-container live tail |

Trace → flow. Metric → aggregate. Log → narrative. If you read only one column, you should still know which tab to click.

---

## Cross-tool linking

Every log line emitted inside an OpenTelemetry span context carries the active trace ID:

```
2026-04-27 11:36:17 [techne] INFO [trace=750edeb816c2fa5eab9b2261945b1c10]: write_file ok
```

So the cross-pane jump is direct:

1. Spot a slow span in Jaeger → copy its trace ID from the URL or the trace header.
2. Paste it into Dozzle's filter as `trace=<id>`.
3. The exact log lines emitted *during* that trace return — across every container that touched it.

Lines emitted outside any span (startup chatter, pre-request setup) render with the bare format and skip the trace block entirely, so non-traced lines don't pad the output with 32 zeros.

The wiring lives in `shared/src/kourai_common/log.py::_OtelTraceFilter` — a small `logging.Filter` that reads `opentelemetry.trace.get_current_span()` per record and stamps `otelTraceID` / `otelSpanID` onto it. Pairs with the format swapper `_TraceAwareFormatter` that picks between the two format strings based on whether the trace is real or zero.

---

## Triage runbook

When something looks wrong, the answer is almost always one of these patterns:

**Agent looks stuck mid-pipeline**
1. `make observe` → click Dozzle.
2. Find the agent's container group in the sidebar (`agents` group).
3. Live-tail; the most recent line is what it's working on right now. If the same line has been there for >30s, the agent is wedged — check for `tool_use` lines that didn't get a `tool_result` reply.
4. Grab the trace ID from the most recent line, paste into Jaeger's search to see the full A2A → MCP flow that led here.

**A request finished but felt slow**
1. Open Jaeger.
2. Search the service that owns the request entry point (Hephaestus for player-facing requests).
3. Click the most recent trace; the waterfall shows which child span dominated wall time.
4. If the dominant span is an LLM call, that's the LiteLLM request — check Prometheus for whether this latency is normal for that agent + model combo.

**Errors visible somewhere but unclear which agent**
1. Jaeger first — failed spans are flagged red. Drill into the trace, find the span with `status: error`, the service name on it tells you which container to tail.
2. Use that trace ID to grep Dozzle for the same trace context across other containers (the error often originates upstream of where it surfaced).

**OOM / container kept restarting**
1. Dozzle directly — the log scrolling in real time shows the bootstrap chatter on each restart.
2. Jaeger may show *no* recent traces from that service — corroborates that the agent is too unhealthy to even emit telemetry.

---

## Container groups in Dozzle

The compose file labels every service with a `dev.dozzle.group` so the Dozzle sidebar separates them into four collapsible sections:

| Group | Members | Purpose |
|---|---|---|
| `agents` | mneme, kallos, techne, dokimasia, metis, puck, cupid, aidos, aletheia, hephaestus | The 10 A2A specialists |
| `mcp` | memory-mcp, context7-mcp | MCP sidecars the agents call into |
| `observability` | jaeger, prometheus, dozzle | The triad itself |
| `infra` | vn-bridge | Bridges + future infrastructure |

When triaging, "is this an agent issue or an infra issue?" is one click in the sidebar, not a hunt through 16 containers.

---

## What's currently populated, and what's not

Be candid about gaps so you don't go looking for data that isn't there:

- **Jaeger** — fully populated. Every A2A call creates a span; W3C trace context propagates via A2A `metadata` headers; MCP tool calls add child spans.
- **Dozzle** — fully populated. Every container's stdout/stderr; live tail; trace IDs on every span-bound log line.
- **Prometheus** — *almost empty today.* The single scrape job in `docker/prometheus.yml` targets Jaeger's own internal metrics endpoint (`:14269`); the 10 agents are **not** currently scraped despite emitting OTLP traces fine. The Service Performance Monitoring "Monitor" tab in Jaeger's UI is therefore unpopulated. Fixing this is tracked under [M16 — Observability DX uplift](../ROADMAP.md#m16--observability-dx-uplift) (Workstream 4: Jaeger v2 `spanmetrics` connector + Prometheus v3).

Until M16 lands, treat Prometheus as a placeholder pane — its real value arrives with the next observability uplift.

---

## Span naming convention

Every span follows a `<source>.<operation>` shape so Jaeger search by service is meaningful:

| Span | Source |
|---|---|
| `hephaestus.route` | Pipeline determination |
| `hephaestus.pipeline.step.{agent}` | Each specialist call |
| `hephaestus.pipeline.fix_loop` | Kallos-Techne iterations |
| `a2a.connect.{agent}` | Agent card fetch |
| `a2a.send.{agent}` | Message send |
| `{agent}.execute` | Agent-specific execution |
| `{agent}.generate` | LLM call |
| `mcp.context7.query` | Context7 tool call |
| `mcp.memory.{op}` | Memory MCP operation |

---

## References

- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/) — the SDK every agent uses
- [Jaeger v2 deployment guide](https://www.jaegertracing.io/docs/2.16/getting-started/) — target version for the M16 migration
- [Prometheus 3.0 migration](https://prometheus.io/docs/prometheus/latest/migration/) — breaking changes for the v2 → v3 jump
- [Dozzle docs](https://dozzle.dev/) — keyboard shortcuts, filters, swarm mode
- [W3C Trace Context](https://www.w3.org/TR/trace-context/) — the propagation format A2A `metadata` carries
