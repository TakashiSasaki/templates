# Public interface contracts

This file prevents humans and agents from having to infer which equivalent interface to use. Runtime, SDK, protocol revision, and transport support are selected in `RUNTIME.md`; this file defines the public behavior built on those selections.

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
| 1 | Successful execution with a negative validation, policy, or tool result |
| 2 | Invalid command or input |
| 3 | Missing runtime, dependency, endpoint, or configuration |
| 4 | Operation refused by a safety, authorization, or permission rule |
| 5 | Protocol, transport, or unexpected internal failure |
| 6 | Operation is incomplete because additional input is required in non-interactive mode |

A concrete skill may revise these codes, but CLI documentation and tests must remain consistent.

For a modern MCP `input_required` result, a non-interactive tool client may return the preserved result and exit 6. Initialization-era elicitation is different: the client responds to the server request with the documented `accept`, `decline`, or `cancel` action and then classifies the final operation response. Do not use exit 6 as a substitute for a required legacy elicitation response.

## In-place agent launcher

```text
Command: TODO
```

Use a stable launcher only when it adds value over the installed CLI. A launcher may locate the skill root and delegate to the selected runtime, but it must not implement domain behavior.

## MCP protocol reference

```text
Runtime and SDK source of truth: RUNTIME.md
Public negotiation and fallback behavior: TODO
Public compatibility statement: TODO
```

Do not duplicate the selected SDK version or revision list here. `RUNTIME.md` owns those values. This contract must explain what a caller observes when negotiation succeeds, falls back, or fails.

At the time this template was aligned, `2026-07-28` is the current modern revision and `2025-11-25` and earlier revisions use the initialization-era model. A concrete skill must verify the current specification and SDK before publishing its compatibility claim.

## stdio MCP server variant

```text
Supported: UNSELECTED; see RUNTIME.md
Launch command: TODO or NOT SUPPORTED
Lifecycle owner: MCP host / bundled tool client / other: TODO
```

When supported:

- the host or bundled client launches the server as a trusted child process;
- expose purpose-specific tools with typed inputs;
- keep stdout exclusively for protocol traffic;
- send logs and diagnostics to stderr;
- perform the lifecycle, discovery, request-metadata, and capability behavior required by the selected revision;
- terminate according to the selected SDK's connection and child-process lifecycle;
- use bounded shutdown escalation when the process does not exit;
- return standard MCP results without losing protocol fields;
- reuse the same application/domain implementation as the CLI;
- document workspace and write restrictions;
- avoid generic `run_command` or arbitrary-code tools.

This is normally the preferred MCP variant for ad hoc use from a skill because it requires no listening socket and ties the server process lifetime to the invoking host or client.

## Local Streamable HTTP MCP server variant

MCP does not define a raw TCP transport as a standard transport. A standalone local server that listens on a TCP port should normally expose the standard **Streamable HTTP** transport.

```text
Supported: UNSELECTED; see RUNTIME.md
Start command: TODO or NOT SUPPORTED
Stop command or shutdown method: TODO or NOT SUPPORTED
Endpoint URL: TODO, for example http://127.0.0.1:3000/mcp
Bind address: TODO, normally 127.0.0.1 or ::1
Port selection: fixed / configurable / dynamic: TODO
Supported protocol eras: see RUNTIME.md
Revision-specific state model: TODO
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
- define deterministic startup, readiness, cancellation, shutdown, restart, and stale-process behavior;
- define concurrent-client behavior and revision-specific state assumptions;
- avoid placing secrets in command-line arguments or committed configuration;
- keep transport-specific HTTP behavior out of the domain layer.

When `2026-07-28` is supported, the implementation contract must also state that:

- clients use one HTTP POST for each JSON-RPC request;
- clients send `Accept` with both `application/json` and `text/event-stream`;
- clients and servers support both JSON and request-scoped SSE responses;
- every POST carries `MCP-Protocol-Version`, and its value matches the request `_meta`;
- every request carries `Mcp-Method`, with `Mcp-Name` where required;
- header values are encoded and checked against the request body;
- Streamable HTTP tool clients validate `x-mcp-header`, exclude invalid tool definitions, and emit the required `Mcp-Param-*` headers;
- cancellation closes the request's SSE stream when applicable;
- modern mode does not use `Mcp-Session-Id`, standalone GET or DELETE endpoints, or resumable `Last-Event-ID` streams;
- any initialization-era compatibility on the same endpoint is explicitly implemented and tested.

Origin validation is required even when browser clients are not an intended interface. A concrete skill must state whether this variant is intended only for the local machine, for a trusted LAN, or for broader deployment. The last two cases require additional authentication and transport-security decisions beyond this template's loopback default.

## Bundled ad hoc MCP tool client

A command that only discovers and invokes MCP tools should be described as an **ad hoc MCP tool client**, not as a complete MCP host or general MCP client.

```text
Supported: UNSELECTED; see RUNTIME.md
Scope: tools only / broader MCP client: TODO
Command: TODO or NOT SUPPORTED
Transport used: stdio / Streamable HTTP / both: TODO
Negotiation and compatibility behavior: TODO
Invocation scope: one tool call / multiple sequential tool calls: TODO
Interaction modes: non-interactive / interactive / response file: TODO
Task or extension support: TODO or NOT SUPPORTED
```

The command-line syntax is local to the skill. MCP standardizes protocol methods, messages, capabilities, lifecycle, and transports; it does not standardize CLI names or option names.

### Recommended command mapping

| Local client operation | Protocol behavior |
|---|---|
| `server-info` | Modern mode uses `server/discover`; initialization-era mode reports the negotiated `initialize` result and capabilities |
| `tools list` | Send `tools/list`, follow opaque pagination cursors, and return the complete inventory unless a single-page mode is explicitly requested |
| `tools show TOOL` | Filter the complete `tools/list` result locally; there is no standard `tools/show`, `tools/get`, or `tools/describe` method |
| `tools call TOOL` | Send one `tools/call` request using the declared input arguments |
| `tools run` | Send multiple independent `tools/call` requests sequentially or with documented concurrency; do not represent this as an MCP or JSON-RPC batch method |

A minimal tools-only client should normally expose `server-info`, `tools list`, and `tools call`. `tools show` and `tools run` are optional local conveniences.

### Recommended options

```text
--transport stdio|http
--endpoint URL                     # Streamable HTTP only
--protocol-version VALUE|auto      # only when supported by the selected SDK
--timeout SECONDS
--max-timeout SECONDS
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

### Tool inventory, schemas, and caching

The client must:

- treat tool names as case-sensitive;
- follow `tools/list` pagination until no next cursor remains unless the caller explicitly requests a single page;
- treat cursors as opaque values, including an empty-string cursor when the selected revision permits it;
- preserve the complete list result, including `resultType`, `ttlMs`, `cacheScope`, tool definitions, `_meta`, and unknown extension fields where present;
- apply cache hints only within their documented identity, authorization, revision, and cache scope;
- preserve tool fields supplied by the server, including input and output schemas, annotations, execution metadata, icons, and future extension fields where practical;
- support JSON Schema 2020-12 where the selected revision requires it and respect an explicit supported `$schema`;
- treat annotations from an untrusted server as hints rather than verified safety properties;
- validate arguments locally only as an early diagnostic; the server remains responsible for authoritative validation;
- validate `structuredContent` against a declared output schema when supported;
- allow `structuredContent` to contain any JSON value when the selected revision permits it;
- implement the selected transport's `x-mcp-header` rules when using modern Streamable HTTP.

Tool inventories may differ by per-request authorization. Equivalence tests must compare calls made under the same revision, identity, authorization, configuration, and workspace policy.

### Tool results and errors

A lossless output mode must preserve the complete result object rather than replacing it with a domain-only envelope.

Modern complete result example:

```json
{
  "resultType": "complete",
  "content": [],
  "structuredContent": ["any JSON value permitted by the schema"],
  "isError": false,
  "_meta": {}
}
```

Modern additional-input result example:

```json
{
  "resultType": "input_required",
  "inputRequests": {},
  "requestState": "opaque-server-state"
}
```

Earlier revisions omit `resultType`. A client may interpret an absent value as `complete` for normalized behavior when the selected compatibility contract requires it, but lossless output must preserve the result exactly as received.

The client may wrap the original result for stable CLI metadata:

```json
{
  "contractVersion": "1",
  "ok": true,
  "transport": "stdio",
  "tool": "example.tool",
  "effectiveResultType": "complete",
  "mcpResult": {
    "resultType": "complete",
    "content": [],
    "structuredContent": ["example"],
    "isError": false,
    "_meta": {}
  },
  "metadata": {}
}
```

The client must distinguish:

1. transport failures;
2. JSON-RPC or MCP protocol errors;
3. an unrecognized or invalid result type;
4. a modern `input_required` result;
5. a complete `tools/call` result whose `isError` value is true;
6. a complete successful domain result.

Do not infer that stderr output from a stdio server is necessarily a failure.

### Multiple calls and application state

A local `tools run` command means orchestration by the client. Each item remains a separate `tools/call` request. State must not be assumed merely because calls reuse one process, connection, or HTTP client. Required application state should be represented by documented tool arguments, resource identifiers, handles, storage, or server configuration.

### Modern multi-round-trip requests

For `2026-07-28`, a tool may return `resultType: "input_required"`.

- In non-interactive mode, the client may preserve and return that result without retrying, using the documented incomplete-operation exit code.
- In interactive or response-file mode, the client resolves each input request, then retries the original method with `inputResponses` and the echoed `requestState`.
- Every retry uses a new JSON-RPC request ID.
- Decline or cancel actions are represented in the applicable input response; the client must not invent a generic “incomplete” tool result.

### Initialization-era server-to-client requests

For `2025-11-25` and earlier compatible modes, elicitation and other server-to-client requests use the negotiated client capability and request channel.

- A tools-only client must not advertise elicitation, sampling, or roots support unless it implements the corresponding request handler.
- Form elicitation responses use the protocol-defined `accept`, `decline`, or `cancel` action.
- A non-interactive implementation must document whether it automatically declines or cancels unsupported prompts.
- After responding, the client waits for the original operation's terminal response and maps that response to its normal result and exit-code rules.
- It must not synthesize a nonstandard `input_required` or incomplete tool result for an initialization-era elicitation request.

### Cancellation and timeouts

Timeout handling must use the selected revision and transport's cancellation behavior and then clean up the request, connection, and child process as applicable.

- Initialization-era and modern stdio may use the revision-supported cancellation notification.
- Modern Streamable HTTP cancellation closes the request-scoped SSE response stream; it does not send a cancellation notification over HTTP.
- A maximum timeout should remain enforceable even when progress is reported.
- Child-process shutdown escalation must be bounded and documented.

### Tasks and extensions

Tasks and other extensions must be capability- and revision-gated. Do not expose task commands or claim task support unless the selected SDK implements the applicable extension, the server advertises it, and polling, additional input, cancellation, retention, and terminal results are tested.

Do not confuse a Tasks extension status such as `input_required` with the core modern `InputRequiredResult` returned by a normal request, or with initialization-era elicitation.

### stdio and Streamable HTTP ownership

For stdio, the client normally launches and owns the trusted, bundled server process. Do not accept an arbitrary shell command or user-selected JSON-RPC request ID as a normal public option.

For Streamable HTTP, the client normally connects to an existing endpoint and must not silently create another standalone server unless the execution policy explicitly says so.

Generic workspace restrictions are not a universal MCP client option. Distinguish revision-specific roots support from skill-specific workspace configuration. Use documented MCP capabilities, server configuration, resource URIs, or explicit tool arguments rather than inventing a universal MCP `--workspace` semantic.

The presence of a server under `mcp/` does not register it automatically with an agent host and does not start a network listener automatically.

## Semantic-equivalence requirement

For an operation exposed through CLI, stdio MCP, or Streamable HTTP MCP, under the same protocol revision, identity, authorization, configuration, and workspace policy:

- inputs must have equivalent meaning;
- results must have equivalent meaning;
- safety checks must be identical;
- differences in presentation or transport must not change domain behavior;
- transport adapters must use the same operation registry or server factory where practical;
- contract tests must exercise all supported adapters against the same fixtures;
- protocol-client tests must additionally exercise pagination, caching, schema dialects, result preservation, result types, cancellation, interaction policy, request metadata, custom headers, and every claimed protocol revision.
