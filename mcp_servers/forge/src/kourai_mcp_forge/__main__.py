"""Entry point — runs the forge MCP server over stdio."""

from __future__ import annotations

import os

from kourai_common.tracing import setup_tracing
from kourai_mcp_forge.server import mcp


def main() -> None:
    # Initialize OTel so the per-tool spans (`forge.read_file`,
    # `forge.write_file`, …) reach the configured OTLP endpoint instead
    # of a no-op tracer. The subprocess inherits
    # OTEL_EXPORTER_OTLP_ENDPOINT from the launching agent's environment
    # via the bridge's env safe-list, so spans land in the same Jaeger
    # backend the agent itself reports to. Trace context propagates
    # through MCP `params._meta`, so `forge.*` spans nest under the
    # calling `techne.execute` / `kallos.execute` / `dokimasia.execute`
    # span as one continuous trace.
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    provider = setup_tracing("kourai-forge", endpoint)
    try:
        mcp.run()
    finally:
        # `BatchSpanProcessor` flushes asynchronously; without an
        # explicit shutdown the bridge's teardown SIGTERM can kill us
        # before the batch reaches Jaeger (verified via live smoke —
        # spans missed Jaeger when this finally was absent). Forcing
        # synchronous flush here makes per-tool latency reliably
        # visible in `make observe` even for short-lived subprocesses.
        provider.shutdown()


if __name__ == "__main__":
    main()
