# MCP transport selection for the fixture

This concrete fixture supports trusted stdio and an explicitly started loopback Streamable HTTP endpoint. Both adapters use `mcp/server_factory.rb`, expose the same `text_stats` tool, and delegate to `src/text_stats.rb`.

The authoritative protocol revision, SDK, commands, security, and lifecycle selections are in `RUNTIME.md`; caller-visible behavior and fallback are in `MCP_INTERFACE.md` and `INTERFACES.md`.

## stdio invariants

- the MCP host starts `bundle exec ruby mcp/server.rb` and owns the child lifetime;
- stdout is reserved for MCP protocol messages and diagnostics use stderr;
- initialization selects revision `2025-11-25`; a caller that requested another revision decides whether to continue;
- the server advertises tools only and sequential calls remain independent;
- closing stdin requests graceful exit;
- caller timeout handling closes stdin and waits before bounded TERM/KILL escalation, and always reaps the child.

## Streamable HTTP invariants

- an operator explicitly starts `bundle exec ruby mcp/http_server.rb`; fallback selection never creates a listener;
- the process binds only to `127.0.0.1`, defaults to port 4570, and rejects non-loopback configuration;
- `POST /mcp` and `DELETE /mcp` require the exact external Bearer token on every request;
- `GET /readyz` exposes only process readiness and requires no token;
- canonical Host authority and each present Origin are evaluated independently on every request before authentication or dispatch;
- absent Origin is accepted for non-browser clients, while a present Origin must have the loopback host and configured effective port with no extra URI components;
- port 80 accepts the equivalent omitted and explicit `:80` Host and Origin forms; nondefault ports remain explicit;
- stateful SDK sessions expire after 300 idle seconds, are limited to 16, and can be deleted explicitly;
- request bodies are limited to 65,536 bytes;
- JSON response mode is used; bundled-client request responses must declare `application/json`; no public GET event stream, resumability, or hidden task behavior is claimed;
- TERM or INT remains pending if received before the server callback attaches, then closes the listener and SDK transport, writes lifecycle diagnostics only to stderr, and releases the port for restart.

## Bundled ad hoc MCP tool client

`mcp/client.rb` is a private bounded tools-only client, not a stable packaged CLI or general MCP host. It accepts only the fixed stdio server route or an explicitly supplied loopback `/mcp` endpoint. The HTTP route checks `GET /readyz` first and reads the Bearer token only from `TEXT_STATS_MCP_HTTP_TOKEN`; it never starts a listener implicitly. The stdio route launches only `bundle exec ruby mcp/server.rb` and reaps it with bounded TERM/KILL escalation.

The helper performs one conforming initialization, checks the server-selected `2025-11-25` revision, sends `notifications/initialized`, and then sends real `tools/list` or `tools/call` requests. It generates request IDs internally, requires JSON request responses, validates each listed tool's `inputSchema.type` discriminator, follows opaque cursors with a bounded page limit, preserves ordered raw page records and complete result objects, and does not issue local `tools/show` or JSON-RPC batch methods. Tool-result, JSON-RPC, authentication, request-policy, transport, timeout, capacity, invalid-result, and pagination outcomes remain distinct.

## Equivalence boundary

The fixture tests actual initialization, discovery, and tool calls over both transports and through the bundled client, and requires equal `structuredContent` for equal input. Focused boundary tests verify canonical default-port authority forms and shutdown delivery on both sides of server attachment. Transport-specific status codes, headers, authentication, sessions, framing, and lifecycle remain adapter concerns and do not alter domain semantics.

Resources, prompts, sampling, elicitation, roots, tasks, optional extensions, a stable public packaged CLI, a general-purpose MCP host, remote exposure, TLS termination, reverse-proxy trust, service-manager integration, containers, and automatic restart are not supported by this fixture.
