# MCP transport selection for the fixture

This concrete fixture supports only the standard stdio MCP transport. An MCP host starts `bundle exec ruby mcp/server.rb`, exchanges newline-delimited JSON-RPC messages through stdin and stdout, and owns the process lifetime.

The authoritative protocol revision, SDK, command, and lifecycle selections are in `RUNTIME.md`; caller-visible behavior is in `MCP_INTERFACE.md`.

## stdio invariants

- stdout is reserved for MCP protocol messages;
- diagnostics use stderr;
- initialization with revision `2025-11-25` precedes discovery and calls;
- the server advertises tools only;
- sequential calls remain independent;
- closing stdin requests graceful exit;
- caller timeout handling uses bounded TERM/KILL escalation and always reaps the child.

Streamable HTTP, resources, prompts, sampling, elicitation, roots, tasks, optional extensions, and a public bundled MCP client are not supported by this fixture.
