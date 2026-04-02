#!/usr/bin/env node
/**
 * Memory MCP server wrapper.
 *
 * Spawns supergateway once at startup, proxies all requests through to it.
 * Supergateway handles sessionId management and concurrent connections natively.
 */

'use strict';

const http = require('http');
const net = require('net');
const { spawn } = require('child_process');

const HEALTH_PORT = parseInt(process.env.PORT || '5000', 10);
const MCP_PORT = parseInt(process.env.MCP_PORT || '5001', 10);
const GATEWAY_PORT = 9000;
const MEMORY_FILE = process.env.MEMORY_FILE_PATH || '/data/memory_graph.json';

let mcpReady = false;

// Spawn supergateway once at startup using --outputTransport streamableHttp
// to properly handle multiple concurrent connections without crashes
const gatewayProc = spawn('supergateway', [
  '--stdio',
  'node /usr/local/lib/node_modules/@modelcontextprotocol/server-memory/dist/index.js',
  '--outputTransport', 'streamableHttp',
  '--port', String(GATEWAY_PORT),
  '--host', '127.0.0.1',
], {
  stdio: ['pipe', 'inherit', 'inherit'],
  env: { ...process.env, MEMORY_FILE_PATH: MEMORY_FILE },
});

gatewayProc.on('error', (err) => {
  console.error('Supergateway error:', err);
  process.exit(1);
});

gatewayProc.on('exit', (code) => {
  console.log(`Supergateway exited with code ${code}`);
  process.exit(code || 1);
});

// Wait for gateway port to be ready
function waitForGateway() {
  const sock = new net.Socket();
  sock.setTimeout(1000);
  sock.connect(GATEWAY_PORT, '127.0.0.1', () => {
    sock.destroy();
    mcpReady = true;
    console.log(`Memory MCP Streamable HTTP ready on port ${MCP_PORT}`);
  });
  sock.on('error', () => {
    sock.destroy();
    setTimeout(waitForGateway, 500);
  });
}
setTimeout(waitForGateway, 500);

// Main MCP server: proxy all requests to supergateway
const mcpServer = http.createServer((req, res) => {
  const proxyReq = http.request({
    hostname: '127.0.0.1',
    port: GATEWAY_PORT,
    path: req.url,
    method: req.method,
    headers: req.headers,
  }, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res);
  });

  proxyReq.on('error', (err) => {
    console.error('Proxy error:', err);
    res.writeHead(503);
    res.end();
  });

  req.pipe(proxyReq);
});

// Health check server
const healthServer = http.createServer((req, res) => {
  const healthStatus = {
    status: mcpReady ? 'healthy' : 'initializing',
    mcp_port: MCP_PORT,
    timestamp: new Date().toISOString(),
  };
  res.writeHead(mcpReady ? 200 : 503, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(healthStatus));
});

healthServer.listen(HEALTH_PORT, '0.0.0.0', () => {
  console.log(`Health: ${HEALTH_PORT}, MCP: ${MCP_PORT}`);
});

mcpServer.listen(MCP_PORT, '0.0.0.0');

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM — shutting down');
  gatewayProc.kill();
  mcpServer.close();
  healthServer.close(() => process.exit(0));
});

process.on('SIGINT', () => {
  console.log('SIGINT — shutting down');
  gatewayProc.kill();
  mcpServer.close();
  healthServer.close(() => process.exit(0));
});
