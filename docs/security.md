# Security posture

A posture statement, not a code-generated artifact. This page names the trust boundaries and transport assumptions Kourai Khryseai's MCP-and-A2A surface relies on, the conventions the implementation is moving toward, and the deliberate non-goals. It is the document the implementation evolves *into*, not a summary of code already in place.

## Frame: Project Glasswing (2026)

Kourai sits in the same conceptual neighborhood as [Anthropic's Project Glasswing](https://www.anthropic.com/glasswing) (April 2026): trustworthy software in the AI era, with frontier models autonomously discovering and patching vulnerabilities at scale. Kourai is a multi-agent *development* system rather than a vulnerability-discovery one, but the posture is shared: code that AI agents emit and modify needs to be auditable, the trust boundaries between agents need to be explicit, and the transport between agents and tools needs to follow current best practice rather than be reinvented.

This page does not claim Glasswing endorsement or partnership. It cites the initiative as the 2026 frame for the design pressure that produced these choices.

## Transport between agents and MCP servers

The canonical 2026 posture for MCP transport (per the [2026 MCP roadmap](https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/), the [MCP authorization spec](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization), and the [Security Boulevard 2026-05 PQC + MCP guide](https://securityboulevard.com/2026/05/the-2026-guide-to-post-quantum-ai-infrastructure-security-protecting-model-context-protocol-mcp/)):

- **TLS 1.3** for server-to-server hops.
- **OAuth 2.1 + OIDC** for any user-facing authorization flow; MCP servers act as OAuth resource servers.
- **RFC 8707 Resource Indicators** on access tokens to prevent token mis-redemption across services.
- **AES-256** for data at rest (where applicable).
- **RBAC** at the per-resource layer so individual MCP capabilities are reachable only by the agents that need them.

What Kourai does today, against that baseline:

- The MCP sidecars (`mcp_servers/shell/`, `mcp_servers/repo/`, etc.) run inside the same Docker network as the orchestrator and specialists. The trust boundary is the Docker network; intra-network calls are unauthenticated. This is acceptable for the current single-host single-developer deploy shape, but it is an implicit trust boundary that should not silently extend to cross-network or multi-tenant deploys.
- A2A hops between agents likewise rely on the Docker network as the trust boundary. The A2A protocol does not yet impose its own auth; Kourai inherits the network-level posture.
- No OAuth resource-server wrapping is in place today. Adding it is gated on a real cross-network deploy use case; until then the work is speculative scaffolding (cf. the `YAGNI-refactored` invariant in `ROADMAP.md`).

If you fork Kourai for a multi-tenant or cross-host deploy, **make this boundary explicit before opening the network**. The mitigations in priority order are: (1) terminate TLS 1.3 at the MCP edge, (2) wrap the MCP servers as OAuth 2.1 resource servers with RFC 8707 token-binding, (3) add per-resource RBAC on MCP tool capabilities, (4) revisit AES-256-at-rest for any persisted artifact that crosses the boundary.

## Per-resource access lists on MCP tools

Each MCP tool capability today is callable by any agent in the network. The design target is a per-resource access list: each MCP capability declares which agents are allowed to call it, and the MCP server enforces the policy at dispatch.

A worked example: a hypothetical credential-reading tool should be reachable from `techne` (the coder, when writing config) and `dokimasia` (the tester, when validating env wiring) but not from `kallos` (the stylist, which only reads and rewrites source). Expressed as policy:

```yaml
# example only — config shape not yet committed
capabilities:
  - name: credentials.read
    allow_callers: [techne, dokimasia]
```

This replaces the "custom E2E encryption layer for sensitive tools" framing that earlier review notes proposed. The MCP layer is the right place to enforce who can call what; a custom encryption protocol on top of MCP is not the call.

Mechanical small slice once the posture above is committed. Until then, the implicit trust model of "every agent can call every tool, but the network is trusted" stands, with the explicit understanding that broadening the network broadens the access too.

## Post-quantum cryptography (watcher)

The [MCP 2026 roadmap](https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/) names PQC hybrid (ML-KEM / Kyber + classical X25519) as a 2026 priority. The Rustls / OpenSSL hybrid Kyber stack is still maturing as of May 2026; the prudent posture is to wait for a stable hybrid Kyber + X25519 configuration in the transport library before adopting.

Do not hand-roll a PQC layer on top of TLS 1.3. The hybrid construction needs ecosystem consensus (CA + library + client) and is exactly the work the IETF / Rustls / OpenSSL teams are doing.

## Out of scope (deliberately)

- **Encrypted prompt logs / encrypted Forge Transcript at rest.** The Forge Transcript is the legibility artifact; encrypting it defeats the on-the-loop-supervision goal. If the operating context demands it, encrypt at the filesystem or volume layer, not inside the transcript format.
- **End-to-end encryption between agents on top of MCP.** TLS 1.3 plus OAuth-bound access lists is the canonical layered approach; an additional E2E layer is unnecessary and conflicts with the auditability story.
- **Single-step multi-agent jailbreak hardening.** Treated as a research direction, not a hardcoded mitigation in this repo. Agent boundaries today are role discipline (system prompt + tool surface) rather than capability sandboxing.

## Reporting issues

Open a GitHub issue with the `security` label, or — for findings sensitive enough that a public issue is the wrong venue — contact the maintainer via the email in [`CITATION.cff`](../CITATION.cff). Glasswing-aligned best practice is to disclose responsibly; the same applies here.
