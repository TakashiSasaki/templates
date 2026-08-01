# Text statistics MCP adapter

`server.rb` is the executable stdio entry point for the fixture. It uses the official Ruby `mcp` SDK, fixes negotiation to revision `2025-11-25`, advertises only the `tools` capability, and registers one read-only `text_stats` tool backed by `src/text_stats.rb`.

Run it from the skill root:

```sh
bundle exec ruby mcp/server.rb
```

The process reads one JSON-RPC object per stdin line and writes one protocol response per stdout line. Diagnostic lifecycle messages are written to stderr. The owning MCP host closes stdin for graceful shutdown and applies the bounded escalation policy documented in `RUNTIME.md` if the child does not exit.
