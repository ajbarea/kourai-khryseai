# Memory MCP sidecar — shared knowledge graph for Puck / Cupid / Mneme
#
# Port 5000: HTTP health check
# Port 5001: MCP Streamable HTTP endpoint at /mcp
#            (memory-mcp-server.js wraps supergateway → @modelcontextprotocol/server-memory)
#
# supergateway converts the stdio MCP server to Streamable HTTP so Python
# agents can connect via mcp.client.streamable_http without Node.js in
# their containers.
#
# research(2026-05): Chainguard Node (Wolfi, daily-rebuilt) over
# node:20-slim — same Debian-glibc CVE profile motivated the Python-side
# migration in issue #98; the Node images shared it. :latest-dev keeps
# npm + a shell so supergateway can spawn its stdio child cleanly;
# :latest is distroless and would need a multi-stage carrying the global
# npm prefix, not worth the complexity for a sidecar.
# tradeoff: chainguard/node:latest-dev ships npm 11.13.0 with a bundled
# vulnerable @xmldom/xmldom 0.8.12 (HIGH CVE-2026-41674/41675),
# upstream-blocked until npm pushes a fix. Not exploitable here — this
# sidecar's only XML pathway is npm's internal config, never network
# input from agents.

FROM cgr.dev/chainguard/node:latest-dev

USER root
WORKDIR /app

# Pre-install packages so the container starts instantly.
RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm install --cache /root/.npm -g \
        @modelcontextprotocol/server-memory@2026.1.26 \
        supergateway@3.4.3 && \
    supergateway --version

COPY docker/memory-mcp-server.js /app/memory-mcp-server.js
RUN chown -R node:node /app

USER node

EXPOSE 5000 5001

# Chainguard's node image sets ENTRYPOINT to /usr/bin/node, so CMD is the
# script path passed as node's argv. Override the ENTRYPOINT-CMD shape here
# to keep this Dockerfile's CMD self-describing rather than relying on
# the base's defaults.
ENTRYPOINT ["/usr/bin/node"]
CMD ["/app/memory-mcp-server.js"]
