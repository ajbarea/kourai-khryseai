# Context7 MCP sidecar — live documentation for Techne / Metis
#
# Port 3001: MCP Streamable HTTP endpoint at /mcp
#            (supergateway → @upstash/context7-mcp)
#
# supergateway converts the stdio MCP server to Streamable HTTP so Python
# agents can connect via mcp.client.streamable_http without Node.js in
# their containers.
# Free tier: 1,000 req/month — no API key required.
#
# Base: Chainguard Node (Wolfi, daily-rebuilt, 0 known CVEs). Migrated from
# node:20-slim per issue #98 — see docker/memory-mcp.Dockerfile for the
# rationale on choosing :latest-dev over distroless for a sidecar.

FROM cgr.dev/chainguard/node:latest-dev

USER root
WORKDIR /app

# Pre-install packages so the container starts instantly (avoids npx cold-download).
RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm install --cache /root/.npm -g \
        @upstash/context7-mcp@2.2.5 \
        supergateway@3.4.3 && \
    supergateway --version

USER node

EXPOSE 3001

# Chainguard's node image sets ENTRYPOINT=/usr/bin/node, so we'd otherwise
# end up running `node supergateway ...`. Reset ENTRYPOINT to [] and put
# the supergateway CLI invocation in CMD; the binary lives in npm's global
# prefix and is on PATH thanks to the install above.
ENTRYPOINT []
# supergateway exposes context7-mcp as HTTP Streamable
CMD ["supergateway", "--stdio", "context7-mcp", "--outputTransport", "streamableHttp", "--port", "3001", "--host", "0.0.0.0"]
