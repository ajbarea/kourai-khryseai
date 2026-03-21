#!/usr/bin/env node
const http = require('http');
const { spawn } = require('child_process');

const PORT = process.env.PORT || 5000;
let mcpHealthy = false;

// Create a simple HTTP server that responds with OK for health checks
const server = http.createServer((req, res) => {
  if (req.url === '/' || req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: mcpHealthy ? 'healthy' : 'initializing' }));
  } else {
    res.writeHead(404);
    res.end();
  }
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Memory MCP health check server listening on 0.0.0.0:${PORT}`);
});

// Start the actual MCP server in the background
console.log('Starting MCP server...');
const mcpProcess = spawn('npx', ['-y', '@modelcontextprotocol/server-memory@2026.1.26'], {
  stdio: ['pipe', 'inherit', 'inherit'],
});

// Mark as healthy after 5 seconds
setTimeout(() => {
  mcpHealthy = true;
  console.log('MCP server marked as healthy');
}, 5000);

mcpProcess.on('error', (err) => {
  console.error('MCP process error:', err);
  process.exit(1);
});

mcpProcess.on('exit', (code) => {
  console.log(`MCP process exited with code ${code}`);
  process.exit(code || 1);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received, shutting down...');
  mcpProcess.kill('SIGTERM');
  server.close(() => {
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  console.log('SIGINT received, shutting down...');
  mcpProcess.kill('SIGINT');
  server.close(() => {
    process.exit(0);
  });
});
