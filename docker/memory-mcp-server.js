#!/usr/bin/env node
/**
 * Memory MCP server wrapper.
 *
 * - Port 5000: HTTP health check (used by Docker healthcheck + agents)
 * - Port 5001: MCP SSE endpoint via supergateway → @modelcontextprotocol/server-memory
 *
 * Health is determined by probing port 5001 rather than a fixed timer,
 * so the /health endpoint reflects actual readiness.
 */

'use strict';

const http = require('http');
const net = require('net');
const { spawn } = require('child_process');

const HEALTH_PORT = parseInt(process.env.PORT || '5000', 10);
const MCP_PORT = parseInt(process.env.MCP_PORT || '5001', 10);
const MEMORY_FILE = process.env.MEMORY_FILE_PATH || '/data/memory_graph.json';

let mcpReady = false;

// Launch supergateway to expose memory server as SSE on MCP_PORT.
// supergateway bridges the stdio MCP server to SSE so Python agents can
// connect via mcp.client.sse without Node.js in their containers.
// The --stdio flag expects a single command string that will be executed via shell.
const gatewayArgs = [
  '--stdio',
  `node /usr/local/lib/node_modules/@modelcontextprotocol/server-memory/dist/index.js`,
  '--port',
  String(MCP_PORT),
  '--host',
  '0.0.0.0',
];

const gatewayProcess = spawn('supergateway', gatewayArgs, {
  stdio: ['pipe', 'inherit', 'inherit'],
  env: { ...process.env, MEMORY_FILE_PATH: MEMORY_FILE },
});

gatewayProcess.on('error', (err) => {
  console.error('supergateway error:', err);
  process.exit(1);
});

gatewayProcess.on('exit', (code) => {
  console.log(`supergateway exited with code ${code}`);
  process.exit(code || 1);
});

// Poll MCP_PORT until supergateway is accepting TCP connections.
// This is a real readiness check, not a fixed sleep.
function pollMcpPort() {
  const sock = new net.Socket();
  sock.setTimeout(1000);
  sock.connect(MCP_PORT, '127.0.0.1', () => {
    sock.destroy();
    mcpReady = true;
    console.log(`Memory MCP SSE ready on port ${MCP_PORT}`);
  });
  sock.on('error', () => {
    sock.destroy();
    setTimeout(pollMcpPort, 500);
  });
  sock.on('timeout', () => {
    sock.destroy();
    setTimeout(pollMcpPort, 500);
  });
}
pollMcpPort();

// Minimal HTTP health check server for Docker healthcheck + agent startup probing.
const server = http.createServer((req, res) => {
  if (req.url === '/' || req.url === '/health') {
    const status = mcpReady ? 'healthy' : 'initializing';
    res.writeHead(mcpReady ? 200 : 503, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status, mcp_port: MCP_PORT }));
  } else {
    res.writeHead(404);
    res.end();
  }
});

server.listen(HEALTH_PORT, '0.0.0.0', () => {
  console.log(`Memory MCP health server on ${HEALTH_PORT}, MCP SSE on ${MCP_PORT}`);
});

// Graceful shutdown
function shutdown(signal) {
  console.log(`${signal} received — shutting down`);
  gatewayProcess.kill(signal);
  server.close(() => process.exit(0));
}
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
