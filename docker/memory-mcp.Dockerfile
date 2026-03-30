# Memory MCP sidecar — shared knowledge graph for Puck / Cupid / Mneme
#
# Port 5000: HTTP health check
# Port 5001: MCP SSE endpoint (supergateway → @modelcontextprotocol/server-memory)
#
# supergateway converts the stdio MCP server to SSE so Python agents can
# connect via mcp.client.sse without Node.js in their containers.

FROM node:20-slim

WORKDIR /app

# Pre-install packages so container starts instantly (avoids npx cold-download)
RUN npm install -g \
    @modelcontextprotocol/server-memory@2026.1.26 \
    supergateway@3.4.3 && \
    # Verify supergateway is on PATH
    supergateway --version

COPY docker/memory-mcp-server.js /app/memory-mcp-server.js

RUN chown -R node:node /app

USER node

EXPOSE 5000 5001

CMD ["node", "/app/memory-mcp-server.js"]
