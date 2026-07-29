# Public interface contracts

This file prevents humans and agents from having to infer which equivalent interface to use.

## Execution policy

A concrete skill must select exactly one preferred agent interface and define a deterministic fallback order.

```text
Preferred agent interface: UNSELECTED
Fallback 1: UNSELECTED
Fallback 2: UNSELECTED
```

Allowed interface categories:

- native MCP tool already registered in the host;
- existing local Streamable HTTP MCP endpoint;
- bundled ad hoc stdio MCP client;
- stable in-place CLI launcher;
- installed human CLI command.

Do not write “use whichever is appropriate” unless all routes are intentionally interchangeable and nondeterminism is acceptable.

When both MCP variants are supported, state whether an agent should:

1. connect to an already-running local Streamable HTTP endpoint;
2. fall back to launching the bundled stdio server ad hoc; or
3. bypass MCP and use the CLI.

The skill must not start a second network server merely because the configured endpoint is unavailable unless that behavior is explicitly documented.

## Human CLI

```text
Command: TODO
Working directory: TODO
```

The CLI should:

- provide `--help`;
- emit readable terminal output by default;
- provide a structured output mode when results are consumed by an agent or CI;
- send diagnostics to stderr;
- use documented, stable exit codes;
- avoid embedding domain logic in argument parsing or formatting code.

### Structured output

```text
Format: TODO, normally JSON
Contract version field: TODO
```

Suggested result envelope:

```json
{
  "contractVersion": "1",
  "ok": true,
  "result": {},
  "errors": [],
  "warnings": [],
  "metadata": {}
}
```

### Exit codes

| Code | Meaning |
|---:|---|
| 0 | Successful execution and successful domain result |
| 1 | Successful execution with a negative validation or policy result |
| 2 | Invalid command or input |
| 3 | Missing runtime, dependency, or configuration |
| 4 | Operation refused by a safety or permission rule |
| 5 | Unexpected internal failure |

A concrete skill may revise these codes, but CLI documentation and tests must remain consistent.

## In-place agent launcher

```text
Command: TODO
```

Use a stable launcher only when it adds value over the installed CLI. A launcher may locate the skill root and delegate to the selected runtime, but it must not implement domain behavior.

## stdio MCP server variant

```text
Supported: UNSELECTED
Launch command: TODO or NOT SUPPORTED
Lifecycle owner: MCP host / bundled ad hoc client / other: TODO
```

When supported:

- the host or bundled client launches the server as a child process;
- expose purpose-specific tools with typed inputs;
- keep stdout exclusively for protocol traffic;
- send logs to stderr;
- terminate when the client closes stdin or ends the session;
- return structured results compatible with the CLI result model;
- reuse the same application/domain implementation as the CLI;
- document workspace and write restrictions;
- avoid generic `run_command` or arbitrary-code tools.

This is the preferred MCP variant for ad hoc use from a skill because it requires no listening socket and ties the server lifetime to the invoking client.

## Local network MCP server variant

MCP does not define a raw TCP transport as a standard transport. A standalone local server that listens on a TCP port should normally expose the standard **Streamable HTTP** transport.

```text
Supported: UNSELECTED
Start command: TODO or NOT SUPPORTED
Stop command or shutdown method: TODO or NOT SUPPORTED
Endpoint URL: TODO, for example http://127.0.0.1:3000/mcp
Bind address: TODO, normally 127.0.0.1 or ::1
Port selection: fixed / configurable / dynamic: TODO
Session mode: stateless / stateful: TODO
Authentication: TODO or NOT REQUIRED FOR LOOPBACK-ONLY
Health/readiness check: TODO
```

When supported:

- use the same server factory, tool definitions, schemas, safety checks, and application/domain implementation as the stdio variant;
- bind to a loopback address by default;
- do not bind to `0.0.0.0` or `::` by default;
- validate the HTTP Host header and provide DNS-rebinding protection;
- validate the `Origin` header on every incoming connection;
- return HTTP 403 when an `Origin` header is present but not explicitly allowed;
- define whether an absent `Origin` is accepted for documented non-browser clients;
- require an explicit security design before allowing non-loopback clients;
- document authentication when the endpoint is accessible beyond the current user or machine;
- define deterministic startup, readiness, shutdown, restart, and stale-process behavior;
- define whether concurrent clients and multiple sessions are supported;
- avoid placing secrets in command-line arguments or committed configuration;
- keep transport-specific HTTP behavior out of the domain layer.

Origin validation is required even when browser clients are not an intended interface. A concrete skill must state whether this variant is intended only for the local machine, for a trusted LAN, or for broader deployment. The last two cases require additional authentication and transport-security decisions beyond this template's loopback default.

## Ad hoc MCP client

```text
Supported: UNSELECTED
Command: TODO or NOT SUPPORTED
Transport used: stdio / Streamable HTTP: TODO
Session scope: one call / multiple calls: TODO
```

An ad hoc client is justified when the MCP protocol path itself matters, several MCP tools benefit from one session, or the same server is also consumed by native MCP hosts. For a single stateless operation, a direct structured CLI may be simpler.

For stdio, the client normally launches and owns the server process. For Streamable HTTP, the client normally connects to an existing endpoint and must not silently create another standalone server unless the execution policy explicitly says so.

The presence of a server under `mcp/` does not register it automatically with an agent host and does not start a network listener automatically.

## Semantic-equivalence requirement

For an operation exposed through CLI, stdio MCP, or Streamable HTTP MCP:

- inputs must have equivalent meaning;
- results must have equivalent meaning;
- safety checks must be identical;
- differences in presentation or transport must not change domain behavior;
- transport adapters must use the same operation registry or server factory where practical;
- contract tests must exercise all supported adapters against the same fixtures.
