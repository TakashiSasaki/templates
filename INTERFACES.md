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
- bundled ad hoc MCP tool client over stdio or Streamable HTTP;
- stable in-place CLI launcher;
- installed human CLI command.

Do not write “use whichever is appropriate” unless all routes are intentionally interchangeable and nondeterminism is acceptable.

When both MCP variants are supported, state whether an agent should:

1. connect to an already-running local Streamable HTTP endpoint;
2. fall back to launching the bundled stdio server through the ad hoc MCP tool client; or
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
| 3 | Missing runtime, dependency, endpoint, or configuration |
| 4 | Operation refused by a safety or permission rule |
| 5 | Protocol, transport, or unexpected internal failure |

A concrete skill may revise these codes, but CLI documentation and tests must remain consistent.

## In-place agent launcher

```text
Command: TODO
```

Use a stable launcher only when it adds value over the installed CLI. A launcher may locate the skill root and delegate to the selected runtime, but it must not implement domain behavior.

## MCP protocol contract

```text
Supported protocol revisions: TODO
Default revision or negotiation mode: TODO
MCP SDK and version: TODO
Optional MCP extensions: TODO or NONE
```

The template does not select a protocol revision. A concrete skill must verify the current MCP specification and SDK support when completing this contract. Do not treat a draft or release candidate as a universal default.

Protocol lifecycle, capability discovery, cancellation, additional-input handling, subscriptions, logging, and task behavior may vary by revision. Prefer the selected SDK's negotiation mechanism over handwritten probing. Every claimed revision and optional feature must be covered by tests.

## stdio MCP server variant

```text
Supported: UNSELECTED
Launch command: TODO or NOT SUPPORTED
Lifecycle owner: MCP host / bundled tool client / other: TODO
```

When supported:

- the host or bundled client launches the server as a child process;
- expose purpose-specific tools with typed inputs;
- keep stdout exclusively for protocol traffic;
- send logs to stderr;
- perform the lifecycle and capability exchange required by the selected protocol revision;
- terminate when the client closes stdin, closes the connection, or ends the invocation according to the selected SDK;
- return standard MCP results without losing protocol fields;
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
Protocol state model: TODO; revision-dependent
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
- define concurrent-client behavior and any revision-specific state assumptions;
- avoid placing secrets in command-line arguments or committed configuration;
- keep transport-specific HTTP behavior out of the domain layer.

Origin validation is required even when browser clients are not an intended interface. A concrete skill must state whether this variant is intended only for the local machine, for a trusted LAN, or for broader deployment. The last two cases require additional authentication and transport-security decisions beyond this template's loopback default.

## Bundled ad hoc MCP tool client

A command that only discovers and invokes MCP tools should be described as an **ad hoc MCP tool client**, not as a complete MCP host or general MCP client.

```text
Supported: UNSELECTED
Scope: tools only / broader MCP client: TODO
Command: TODO or NOT SUPPORTED
Transport used: stdio / Streamable HTTP / both: TODO
Supported protocol revisions: TODO
Version negotiation: TODO
Invocation scope: one tool call / multiple sequential tool calls: TODO
Interaction mode: non-interactive / interactive / response file: TODO
Task or extension support: TODO or NOT SUPPORTED
```

The command-line syntax is local to the skill. MCP standardizes protocol methods, messages, capabilities, lifecycle, and transports; it does not standardize CLI names or option names.

### Recommended command mapping

| Local client operation | Protocol behavior |
|---|---|
| `server-info` | Local abstraction over the lifecycle or discovery exchange required by the selected protocol revision; there is not one universal method across all revisions |
| `tools list` | Send `tools/list`, follow opaque pagination cursors, and return the complete inventory unless a single-page mode is explicitly requested |
| `tools show TOOL` | Local filtering of the complete `tools/list` result; there is no standard `tools/show`, `tools/get`, or `tools/describe` method |
| `tools call TOOL` | Send one `tools/call` request using the declared input arguments |
| `tools run` | Send multiple independent `tools/call` requests sequentially or with documented concurrency; do not represent this as an MCP batch method |

A minimal tools-only client should normally expose `server-info`, `tools list`, and `tools call`. `tools show` and `tools run` are optional local conveniences.

### Recommended options

```text
--transport stdio|http
--endpoint URL                     # Streamable HTTP only
--protocol-version VALUE|auto      # only when supported by the selected SDK
--timeout SECONDS
--output mcp-json|json|jsonl|pretty
--client-log-level LEVEL
--non-interactive
--input-responses-file PATH
--help
--version
```

Tool arguments may be accepted through mutually exclusive forms such as:

```text
--arguments JSON
--arguments-file PATH
--arguments-stdin
```

These option names are recommendations, not MCP-standard names.

### Tool inventory and schemas

The client must:

- treat tool names as case-sensitive;
- follow `tools/list` pagination until no next cursor remains unless the caller explicitly requests a single page;
- treat cursors as opaque values and never parse or synthesize them;
- preserve tool fields supplied by the server, including input and output schemas, annotations, execution metadata, icons, and future extension fields where practical;
- treat annotations from an untrusted server as hints rather than verified safety properties;
- validate arguments locally only as an early diagnostic; the server remains responsible for authoritative validation;
- validate `structuredContent` against a declared output schema when the selected SDK and result contract support it.

### Tool results and errors

A lossless output mode must preserve the standard MCP result rather than replacing it with a domain-only envelope. Depending on the selected revision and feature set, relevant fields may include:

```json
{
  "content": [],
  "structuredContent": {},
  "isError": false,
  "_meta": {}
}
```

The client may wrap this value for stable CLI metadata, but the original result must remain available, for example:

```json
{
  "contractVersion": "1",
  "ok": true,
  "transport": "stdio",
  "tool": "example.tool",
  "mcpResult": {
    "content": [],
    "structuredContent": {},
    "isError": false,
    "_meta": {}
  },
  "metadata": {}
}
```

The client must distinguish:

1. transport failures;
2. JSON-RPC or MCP protocol errors;
3. a successful `tools/call` response whose tool result has `isError: true`;
4. a successful domain result.

Do not infer that stderr output from a stdio server is necessarily a failure.

### Multiple calls, interaction, cancellation, and tasks

A local `tools run` command means orchestration by the client. Each item remains a separate `tools/call` request. State must not be assumed merely because calls reuse one process, connection, or HTTP client; required application state should be represented by documented tool arguments, resources, handles, or server configuration.

The client must document what happens when a request needs additional input:

- non-interactive mode should return a structured incomplete or input-required result rather than hanging;
- interactive mode may prompt a human only when explicitly selected;
- a response-file mode may supply pre-authorized answers when the selected revision and SDK support it.

Timeout handling must use the selected revision and transport's cancellation mechanism. Do not merely abandon a stdio child process or HTTP request without cleanup.

Tasks and other extensions must be capability- and revision-gated. Do not expose `tasks` commands or claim task support unless the selected SDK implements the applicable core feature or extension and the server advertises it.

### stdio and Streamable HTTP ownership

For stdio, the client normally launches and owns the trusted, bundled server process. Do not accept an arbitrary shell command or user-selected JSON-RPC request ID as a normal public option.

For Streamable HTTP, the client normally connects to an existing endpoint and must not silently create another standalone server unless the execution policy explicitly says so.

Generic workspace restrictions are not a universal MCP client option. Distinguish revision-specific roots support from skill-specific workspace configuration. Use documented MCP capabilities, server configuration, resource URIs, or explicit tool arguments rather than inventing a universal MCP `--workspace` semantic.

The presence of a server under `mcp/` does not register it automatically with an agent host and does not start a network listener automatically.

## Semantic-equivalence requirement

For an operation exposed through CLI, stdio MCP, or Streamable HTTP MCP:

- inputs must have equivalent meaning;
- results must have equivalent meaning;
- safety checks must be identical;
- differences in presentation or transport must not change domain behavior;
- transport adapters must use the same operation registry or server factory where practical;
- contract tests must exercise all supported adapters against the same fixtures;
- protocol-client tests must additionally exercise pagination, error classification, result preservation, cancellation, interaction policy, and every claimed protocol revision.
