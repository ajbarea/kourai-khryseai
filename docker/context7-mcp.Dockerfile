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
RUN npm install -g \
    @upstash/context7-mcp@latest \
    supergateway@latest && \
    # Verify supergateway is on PATH
    supergateway --version

EXPOSE 3001

# supergateway exposes context7-mcp as SSE at /sse
CMD ["supergateway", "--stdio", "context7-mcp", "--port", "3001", "--host", "0.0.0.0"]
