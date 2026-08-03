# Text statistics MCP adapters

`server_factory.rb` owns the shared official-Ruby-SDK server definition, selected revision, schemas, and read-only `text_stats` tool backed by `src/text_stats.rb`.

`server.rb` is the trusted stdio entry point:

```sh
bundle exec ruby mcp/server.rb
```

It reads one JSON-RPC object per stdin line, writes protocol responses only to stdout, sends lifecycle diagnostics to stderr, and exits when its owning host closes stdin or completes bounded escalation.

`http_server.rb` is the explicitly started loopback Streamable HTTP entry point. Supply `TEXT_STATS_MCP_HTTP_TOKEN` through the operator's secret environment, then run:

```sh
bundle exec ruby mcp/http_server.rb
```

It exposes `POST /mcp`, `DELETE /mcp`, and `GET /readyz` at `127.0.0.1:4570` by default. The token is read only from the environment and must not be placed in a committed file or public command history. Every MCP request requires Bearer authentication. Every request, including readiness, independently validates canonical loopback Host authority and any present Origin by effective HTTP port; port 80 accepts omitted or explicit `:80`, while nondefault ports remain explicit. The process rejects non-loopback binds, limits request bodies and live sessions, writes no stdout output, and preserves TERM or INT received before server attachment so foreground shutdown is not lost.

`client.rb` is a private bounded ad hoc MCP tool client. It is not a stable packaged CLI. From the fixture root, invoke only the fixed helper command:

```sh
bundle exec ruby mcp/client.rb --transport stdio tools call text_stats --arguments '{"text":"alpha beta"}'
export TEXT_STATS_MCP_HTTP_TOKEN
bundle exec ruby mcp/client.rb --transport http --endpoint http://127.0.0.1:4570/mcp tools list
```

It performs real MCP initialization, requires `application/json` for JSON HTTP responses, validates required initialization, known capability shapes, inventory including each tool's `inputSchema.type` discriminator, optional object-valued `outputSchema`, and optional `_meta`, metadata, and operation-result fields for the selected revision, sends `notifications/initialized`, follows bounded opaque `tools/list` pagination, preserves each raw page and complete `tools/call` result, and distinguishes authentication, request-policy, transport, timeout, JSON-RPC, tool-result, invalid-result, capacity, and pagination failures. Tool arguments are supplied only as bounded inline JSON or bounded stdin; terminal stdin is rejected, and a producer that does not provide EOF is bounded by the configured `--timeout` before transport startup; response-file input is not supported. It never accepts an arbitrary server command or request ID, passes the token as an argument, starts the HTTP server implicitly, or retries across transports. Stdio closes and reaps its fixed child with bounded TERM/KILL escalation; HTTP cleanup failures are diagnosed and returned as non-success outcomes after the connection is closed.

The two server adapters and the client must remain separate from the shared tool definition and domain logic. Do not duplicate tool definitions or domain behavior outside `server_factory.rb` and `src/text_stats.rb`; the client must never call `TextStatsMcp.analyze` directly.
