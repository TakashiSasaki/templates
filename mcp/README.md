# Optional MCP adapter

Delete this directory when the concrete skill does not expose MCP.

When MCP is supported, this directory may contain:

- an stdio MCP server adapter;
- an ad hoc MCP client used by the skill or contract tests;
- MCP-specific schemas or adapter tests.

The implementation language is selected in `RUNTIME.md`.

## stdio constraints

- The host or ad hoc client launches the server as a child process.
- stdin and stdout carry protocol messages.
- Logs and diagnostics go to stderr.
- The server must not daemonize.
- The server must terminate when the client connection closes.
- Heavy initialization should be delayed until a tool call requires it.

## Architecture

The MCP server must be an adapter over the same application/domain implementation used by the CLI. MCP handlers should validate protocol inputs, call the application layer, and translate results. They should not contain the core behavior.

An ad hoc client is not automatically a native agent tool. From the host's perspective it is normally a program invoked through a shell or process tool.
