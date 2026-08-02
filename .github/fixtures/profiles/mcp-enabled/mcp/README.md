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

The two adapters must remain thin. Do not duplicate tool definitions or domain behavior outside `server_factory.rb` and `src/text_stats.rb`.
