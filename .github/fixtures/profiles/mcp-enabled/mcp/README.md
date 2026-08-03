# Text statistics MCP adapters

`server_factory.rb` owns the shared official-Ruby-SDK server definition, selected revision, schemas, and read-only `text_stats` tool backed by `src/text_stats.rb`.

`server.rb` is the trusted stdio entry point:

```sh
bundle exec ruby mcp/server.rb
```

It reads one JSON-RPC object per stdin line, writes protocol responses only to stdout, sends lifecycle diagnostics to stderr, and exits when its owning host closes stdin or completes bounded escalation.

`http_server.rb` is the explicitly selected loopback Streamable HTTP entry point. Direct foreground launch may supply `TEXT_STATS_MCP_HTTP_TOKEN`, while file-backed foreground or managed launch uses `TEXT_STATS_MCP_HTTP_TOKEN_FILE`. Exactly one secret source is accepted. After provisioning the selected secret source in the operator environment, run:

```sh
bundle exec ruby mcp/http_server.rb
```

The file source is opened nonblocking without following symlinks and must be a regular service-user-owned file inaccessible to group and other users. The server exposes `POST /mcp`, `DELETE /mcp`, `GET /readyz`, and `GET /livez` at `127.0.0.1:4570` by default. Every MCP request requires Bearer authentication. Every request, including health checks, independently validates canonical loopback Host authority and any present Origin. The process rejects non-loopback binds, limits request bodies and live sessions, writes no stdout output, and preserves TERM or INT received before server attachment.

`service_manager.rb` is an optional private local lifecycle controller around that same HTTP adapter:

```sh
TEXT_STATS_MCP_HTTP_TOKEN_FILE=/path/to/mode-0600-token \
  bundle exec ruby mcp/service_manager.rb start
bundle exec ruby mcp/service_manager.rb ready
bundle exec ruby mcp/service_manager.rb live
bundle exec ruby mcp/service_manager.rb restart
bundle exec ruby mcp/service_manager.rb stop
```

Managed startup validates the external secret before process creation, starts only the fixed adapter in its own process group, writes diagnostics to an owner-only log, atomically publishes an owner-only PID plus Linux start-tick record, and waits for readiness. Stop and restart verify process identity before signaling, remove only unchanged stale records, and bound graceful TERM shutdown before KILL escalation. The controller never places the token value in argv, records, or logs. It does not install an OS service, change users, restart automatically, open a non-loopback listener, terminate TLS, configure a reverse proxy, create a container, or provide upgrade orchestration.

`client.rb` is a private bounded ad hoc MCP tool client. It is not a stable packaged CLI. From the fixture root, invoke only the fixed helper command:

```sh
bundle exec ruby mcp/client.rb --transport stdio tools call text_stats --arguments '{"text":"alpha beta"}'
export TEXT_STATS_MCP_HTTP_TOKEN
bundle exec ruby mcp/client.rb --transport http --endpoint http://127.0.0.1:4570/mcp tools list
```

It performs real MCP initialization, requires `application/json` for JSON HTTP responses, validates required initialization, capability, inventory, schema, metadata, and operation-result fields for the selected revision, sends `notifications/initialized`, follows bounded opaque `tools/list` pagination, preserves each raw page and complete `tools/call` result, bounds `tools run` to 32 sequential calls, preserves completed results when a later call fails, and distinguishes readiness, tool-result, authentication, request-policy, transport, timeout, JSON-RPC, invalid-result, capacity, and pagination failures. Tool arguments are bounded inline JSON or bounded nonterminal stdin. It never accepts an arbitrary server command, request ID, secret argument, lifecycle command, implicit HTTP startup, or unbounded retry.

The server adapters, client, and lifecycle controller remain separate from the shared tool definition and domain logic. Do not duplicate tool definitions or domain behavior outside `server_factory.rb` and `src/text_stats.rb`; neither private helper may call `TextStatsMcp.analyze` directly.
