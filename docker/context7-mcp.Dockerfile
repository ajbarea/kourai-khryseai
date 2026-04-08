# Context7 MCP sidecar — live documentation for Techne / Metis
#
# Port 3001: MCP SSE endpoint (supergateway → @upstash/context7-mcp)
#
# supergateway converts the stdio MCP server to SSE so Python agents can
# connect via mcp.client.sse without Node.js in their containers.
# Free tier: 1,000 req/month — no API key required.

FROM node:20-slim

WORKDIR /app

# Pre-install packages so container starts instantly (avoids npx cold-download)
RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm install --cache /root/.npm -g \
    @upstash/context7-mcp@2.1.6 \
    supergateway@3.4.3 && \
    # Verify supergateway is on PATH
    supergateway --version

USER node

EXPOSE 3001

# supergateway exposes context7-mcp as HTTP Streamable
CMD ["supergateway", "--stdio", "context7-mcp", "--outputTransport", "streamableHttp", "--port", "3001", "--host", "0.0.0.0"]
