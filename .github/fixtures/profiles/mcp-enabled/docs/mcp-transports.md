# MCP transport selection for the fixture

This concrete fixture supports trusted stdio and an explicitly selected loopback Streamable HTTP endpoint. Both adapters use `mcp/server_factory.rb`, expose the same `text_stats` tool, and delegate to `src/text_stats.rb`. The HTTP adapter can run directly in the foreground or under the bundled private local lifecycle controller; those modes do not create distinct MCP transports or domain implementations.

The authoritative protocol revision, SDK, commands, security, deployment, and lifecycle selections are in `RUNTIME.md`; caller-visible behavior and fallback are in `MCP_INTERFACE.md` and `INTERFACES.md`.

## stdio invariants

- the MCP host starts `bundle exec ruby mcp/server.rb` and owns the child lifetime;
- stdout is reserved for MCP protocol messages and diagnostics use stderr;
- initialization selects revision `2025-11-25`; a caller that requested another revision decides whether to continue;
- the server advertises tools only and sequential calls remain independent;
- closing stdin requests graceful exit;
- caller timeout handling closes stdin and waits before bounded TERM/KILL escalation, and always reaps the child.

## Streamable HTTP invariants

- an operator explicitly selects direct foreground or managed local startup; fallback selection never creates, restarts, or stops a listener;
- the process binds only to `127.0.0.1`, defaults to port 4570, and rejects non-loopback configuration;
- `POST /mcp` and `DELETE /mcp` require the exact external Bearer token on every request;
- direct foreground launch may use `TEXT_STATS_MCP_HTTP_TOKEN`; file-backed and managed launch use `TEXT_STATS_MCP_HTTP_TOKEN_FILE`, opened nonblocking without following symlinks and restricted to a regular service-user-owned file with no group or other access;
- `GET /readyz` and `GET /livez` expose minimal separate readiness and liveness states and require no token; managed mode adds a controller-generated per-start nonce so the probes identify the spawned listener rather than only the configured port;
- canonical Host authority and each present Origin are evaluated independently on every request before authentication or dispatch;
- absent Origin is accepted for non-browser clients, while a present Origin must have the loopback host and configured effective port with no extra URI components;
- stateful SDK sessions expire after 300 idle seconds, are limited to 16, and can be deleted explicitly;
- request bodies are limited to 65,536 bytes;
- JSON response mode is used; bundled-client request responses must declare `application/json`; no public GET event stream, resumability, or hidden task behavior is claimed;
- TERM or INT remains pending if received before the server callback attaches, then closes the listener and SDK transport, writes lifecycle diagnostics only to stderr, and releases the port for restart.

## Managed local lifecycle

`mcp/service_manager.rb` is a private operator controller, not an MCP method, agent fallback, stable packaged CLI, or second server. It supports explicit `start`, `stop`, `restart`, `ready`, and `live` actions around the fixed `mcp/http_server.rb` adapter.

Every lifecycle action for one PID path acquires the adjacent owner-only advisory lock. Managed startup validates the external secret before process creation; rejects missing, symlinked, insecure, oversized, path-equal, or inode-aliased secret/log/lock inputs; validates the final runtime directories with `lstat`; rejects a currently live recorded identity; removes only a safely parsed stale record; starts one process group; and publishes an atomic mode-0600 record containing PID, Linux start ticks, and a cryptographic per-start nonce. Readiness succeeds only when the endpoint returns that nonce, so a manually started listener or another process on the same port cannot satisfy managed startup.

Stop and restart verify PID and start ticks before signaling. TERM receives a fixed grace interval before KILL escalation. The record is removed only after exit is proved and only when its parsed content and inode remain unchanged. If bounded cleanup cannot prove exit, the controller reports failure and retains the record. A missing process, zombie, or start-tick mismatch is stale and is not signaled. Existing final runtime directories must be service-user-owned non-symlink directories with no group or other write permission. The token value is absent from argv, PID metadata, controller output, and the managed log.

This variant does not claim OS service installation, privilege changes, multiple workers, automatic restart, socket activation, zero-downtime handoff, log rotation, non-loopback exposure, TLS, reverse proxy, container, orchestrator, persistence, or remote production deployment.

## Bundled ad hoc MCP tool client

`mcp/client.rb` is a private bounded tools-only client, not a stable packaged CLI or general MCP host. It accepts only the fixed stdio server route or an explicitly supplied loopback `/mcp` endpoint. The HTTP route checks readiness first and reads the Bearer token only from `TEXT_STATS_MCP_HTTP_TOKEN`; it never starts or controls a listener. The stdio route launches only `bundle exec ruby mcp/server.rb` and reaps it with bounded TERM/KILL escalation.

The helper performs one conforming initialization, checks the selected `2025-11-25` revision, sends `notifications/initialized`, and then sends real `tools/list` or `tools/call` requests. It generates request IDs internally, validates known protocol and schema fields, follows opaque cursors with a bounded page limit, preserves ordered raw pages and complete results, bounds `tools run` to 32 sequential calls, and does not issue local `tools/show` or JSON-RPC batch methods. Argument and response inputs are bounded; readiness, tool-result, JSON-RPC, authentication, request-policy, transport, timeout, capacity, invalid-result, and pagination outcomes remain distinct.

## Equivalence boundary

The fixture tests actual initialization, discovery, and tool calls over both transports and through the bundled client, and requires equal `structuredContent` for equal input. Managed-mode tests use the same HTTP adapter and add process identity, instance-owned readiness/liveness, lifecycle serialization, secret/file alias, protected-runtime-directory, stale-record, cleanup-retention, and shutdown-escalation assertions. Transport-specific status codes, headers, authentication, sessions, framing, and lifecycle remain adapter concerns and do not alter domain semantics.

Resources, prompts, sampling, elicitation, roots, tasks, optional extensions, a stable public packaged CLI, a general-purpose MCP host, remote exposure, TLS termination, reverse-proxy trust, OS service-manager integration, containers, persistence, and automatic restart are not supported by this fixture.
