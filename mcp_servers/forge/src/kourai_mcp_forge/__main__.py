"""Entry point — runs the forge MCP server over stdio."""

from __future__ import annotations

import os

from kourai_common.tracing import setup_tracing
from kourai_mcp_forge.server import mcp


def main() -> None:
    # Initialize OTel so the per-tool spans (`forge.read_file`,
    # `forge.write_file`, …) added in M2 Change 2/3 reach the
    # configured OTLP endpoint instead of a no-op tracer. The
    # subprocess inherits OTEL_EXPORTER_OTLP_ENDPOINT from the
    # launching agent's environment, so a Techne tool call writes
    # `forge.*` spans into the same Jaeger backend the agent itself
    # reports to.
    #
    # Trace-context propagation across the MCP subprocess boundary is
    # a separate follow-up — without it, forge spans land as their
    # own roots rather than children of techne.execute, but they're
    # still visible at `kourai-forge` in Jaeger's service list.
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
