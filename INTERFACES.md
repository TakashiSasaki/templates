# Public interface contracts

This file defines the public behavior of the concrete skill. Runtime, SDK, protocol revision, and transport support are selected in `RUNTIME.md`.

## Execution policy

Select exactly one preferred agent interface and define a deterministic fallback order.

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

Do not write “use whichever is appropriate” unless the routes are intentionally interchangeable and nondeterminism is acceptable.

When both MCP transports are supported, state whether an agent should:

1. connect to an already-running Streamable HTTP endpoint;
2. fall back to launching the bundled stdio server through the ad hoc MCP tool client; or
3. bypass MCP and use the structured CLI.

Do not start a second network server merely because the configured endpoint is unavailable unless that fallback is explicitly documented.

## Human CLI

```text
Command: TODO
Working directory: TODO
```

The CLI should:

- provide `--help`;
- emit readable terminal output by default;
- provide a structured output mode for agents and CI;
- send diagnostics to stderr;
- use documented stable exit codes;
- keep domain logic out of parsing and presentation code.

### Structured output

```text
Format: TODO, normally JSON
Contract version field: TODO
```

Suggested envelope:

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

A concrete skill may revise these codes, but its documentation and tests must remain consistent.

For a modern MCP `input_required` result, a non-interactive tool client may preserve the result and exit 6. Initialization-era elicitation is different: the client must respond with the documented `accept`, `decline`, or `cancel` action and classify the original operation's terminal response. Do not use exit 6 as a substitute for a required legacy elicitation response.

## In-place agent launcher

```text
Command: TODO
```

Use a stable launcher only when it adds value over the installed CLI. It may locate the skill root and delegate to the selected runtime, but it must not implement domain behavior.

## MCP protocol reference

```text
Runtime and SDK source of truth: RUNTIME.md
Public negotiation and fallback behavior: TODO
Public compatibility statement: TODO
```

Do not duplicate the selected SDK version or revision list here. Explain what callers observe when negotiation succeeds, falls back, or fails.

At the time this template was aligned, `2026-07-28` is the current modern revision, while `2025-11-25` and earlier revisions use the initialization-era model. Verify the current specification and SDK before publishing compatibility claims.

## stdio MCP server variant

```text
Supported: UNSELECTED; see RUNTIME.md
Launch command: TODO or NOT SUPPORTED
Lifecycle owner: MCP host / bundled tool client / other: TODO
```

When supported:

- launch the server as a trusted child process;
- expose purpose-specific tools with typed inputs;
- reserve stdout for protocol traffic;
- send logs and diagnostics to stderr;
- perform the lifecycle, discovery, request-metadata, and capability behavior required by the selected revision;
- use revision-appropriate cancellation;
- terminate according to the selected SDK's connection and child-process lifecycle;
- use bounded shutdown escalation when the process does not exit;
- preserve standard MCP results and extension fields;
- reuse the same application/domain implementation as the CLI;
- enforce the documented workspace and write restrictions;
- avoid generic `run_command` or arbitrary-code tools.

This is normally the preferred MCP transport for ad hoc use because it opens no listening socket and ties the server process lifetime to the invoking host or client.

## Local Streamable HTTP MCP server variant

MCP does not define raw TCP as a standard transport. A standalone local server should normally expose Streamable HTTP.

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

- use the same server factory, tool definitions, schemas, safety checks, and application/domain implementation as stdio;
- bind to a loopback address by default;
- do not bind to `0.0.0.0` or `::` by default;
- validate the HTTP Host header and protect against DNS rebinding;
- validate `Origin` on **every HTTP request before dispatch**, not merely when a connection is accepted;
- repeat Origin validation for every request carried by HTTP/1.1 keep-alive and every stream or request carried by HTTP/2 or later multiplexed connections;
- return HTTP 403 for each request whose present `Origin` is not explicitly allowed;
- define whether an absent `Origin` is accepted for documented non-browser clients;
- perform Host, Origin, authentication, authorization, size-limit, and protocol-header checks before parsing or dispatching the MCP operation where practical;
- require an explicit security design before allowing non-loopback clients;
- document authentication when the endpoint is accessible beyond the current user or machine;
- define deterministic startup, readiness, cancellation, shutdown, restart, and stale-process behavior;
- define concurrent-client behavior and revision-specific state assumptions;
- avoid placing secrets in command-line arguments or committed configuration;
- keep HTTP behavior out of the domain layer.

A connection-level approval must never be treated as authorization for later requests on that connection. Request headers, including `Origin`, may change between requests.

When `2026-07-28` is supported, also require:

- one HTTP POST for each JSON-RPC request;
- `Accept` support for both `application/json` and `text/event-stream`;
- JSON and request-scoped SSE responses;
- `MCP-Protocol-Version` on every POST, consistent with request `_meta`;
- `Mcp-Method` on every request and `Mcp-Name` where required;
- encoded transport headers that agree with the JSON body;
- `x-mcp-header` validation, exclusion of invalid tool definitions, and required `Mcp-Param-*` emission;
- cancellation by closing the applicable request-scoped SSE stream;
- no `Mcp-Session-Id`, standalone GET or DELETE endpoint, or resumable `Last-Event-ID` stream in modern mode;
- explicit tests for any initialization-era compatibility on the same endpoint.

Origin validation is required even when browser clients are not intended. State whether the endpoint is local-machine-only, trusted-LAN, or broader deployment. The latter two require additional authentication and transport-security decisions.

## Bundled ad hoc MCP tool client

A command that only discovers and invokes MCP tools is an **ad hoc MCP tool client**, not a complete MCP host or general MCP client.

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

MCP standardizes protocol methods, messages, capabilities, lifecycle, and transports. It does not standardize CLI command or option names.

### Recommended command mapping

| Local operation | Protocol behavior |
|---|---|
| `server-info` | Modern mode uses `server/discover`; initialization-era mode reports the negotiated `initialize` result and capabilities |
| `tools list` | Send `tools/list`; preserve an ordered raw-page sequence and optionally derive a flattened inventory |
| `tools show TOOL` | Filter the derived flattened inventory locally; there is no standard `tools/show`, `tools/get`, or `tools/describe` method |
| `tools call TOOL` | Send one `tools/call` request |
| `tools run` | Send multiple independent `tools/call` requests; do not represent this as an MCP or JSON-RPC batch method |

A minimal tools-only client should normally expose `server-info`, `tools list`, and `tools call`.

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

Tool arguments may be accepted through mutually exclusive forms:

```text
--arguments JSON
--arguments-file PATH
--arguments-stdin
```

These names are recommendations, not MCP-standard names.

### Tool inventory, schemas, and caching

The client must:

- treat tool names as case-sensitive;
- follow `tools/list` pagination until no next cursor remains unless single-page mode is explicitly requested;
- treat cursors as opaque, including an empty-string cursor when permitted by the selected revision;
- retain every raw page result as a separate ordered record;
- apply cache hints only within their documented identity, authorization, revision, page, and cache scope;
- preserve tool fields supplied by the server, including schemas, annotations, execution metadata, icons, and future fields where practical;
- support JSON Schema 2020-12 where required and respect supported explicit `$schema` values;
- treat annotations from an untrusted server as hints;
- use local argument validation only as an early diagnostic;
- validate `structuredContent` against a declared output schema when supported;
- allow `structuredContent` to contain any JSON value when permitted by the selected revision;
- apply modern `x-mcp-header` processing only to Streamable HTTP.

Tool inventories may differ by per-request authorization. Equivalence tests must use the same revision, identity, authorization, configuration, and workspace policy.

### Lossless paginated tool-list output

Lossless and presentation-oriented list outputs are separate contracts.

A lossless `tools/list` mode retains the ordered page sequence. Each page record contains local request metadata and the complete result object exactly as received:

```json
{
  "contractVersion": "1",
  "operation": "tools/list",
  "pages": [
    {
      "requestCursor": null,
      "mcpResult": {
        "tools": [],
        "nextCursor": "opaque-next-cursor",
        "ttlMs": 30000,
        "cacheScope": "example-scope",
        "_meta": {}
      }
    },
    {
      "requestCursor": "opaque-next-cursor",
      "mcpResult": {
        "tools": [],
        "_meta": {}
      }
    }
  ],
  "metadata": {
    "pageCount": 2
  }
}
```

Each page's `mcpResult` must not be normalized, merged, or stripped. Preserve page-specific `tools`, `nextCursor`, `resultType`, `ttlMs`, `cacheScope`, `_meta`, and unknown fields. `requestCursor` is client metadata and must not be inserted into the received result.

A single-page response uses the same representation with one page record. A flattened inventory may concatenate tool arrays and add explicitly derived metadata, but it is not lossless output. It must not select one page's cache fields as global values or silently merge page-level `_meta`. Any aggregate expiration or cache scope must use a documented conservative rule and be marked as derived.

### Tool-call results and errors

A lossless tool-call output mode preserves the complete result object rather than replacing it with a domain-only envelope.

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

Modern additional-input example:

```json
{
  "resultType": "input_required",
  "inputRequests": {},
  "requestState": "opaque-server-state"
}
```

Earlier revisions omit `resultType`. A compatibility layer may treat an absent value as `complete` for behavior, but lossless output must preserve the result exactly as received.

The client must distinguish:

1. transport failures;
2. JSON-RPC or MCP protocol errors;
3. unrecognized or invalid result types;
4. modern `input_required` results;
5. complete `tools/call` results with `isError: true`;
6. complete successful domain results.

Do not infer that stderr output from a stdio server is necessarily a failure.

### Multiple calls and application state

A local `tools run` command is client-side orchestration. Each item remains a separate `tools/call` request. Do not assume hidden application state merely because calls reuse a process, connection, or HTTP client. Represent required state using documented arguments, resource identifiers, handles, storage, or server configuration.

### Modern multi-round-trip requests

For `2026-07-28`, a request may return `resultType: "input_required"`.

- Non-interactive mode may preserve and return that result without retrying.
- Interactive or response-file mode resolves the input requests and retries the original method with `inputResponses` and echoed `requestState`.
- Every retry uses a new JSON-RPC request ID.
- Decline or cancel choices are represented in the applicable input response; do not invent a generic incomplete result.

### Initialization-era server-to-client requests

For `2025-11-25` and earlier compatible modes:

- do not advertise elicitation, sampling, roots, or other client capabilities without implementing their handlers;
- answer form elicitation with `accept`, `decline`, or `cancel`;
- document automatic decline or cancellation in non-interactive mode;
- wait for the original operation's terminal response;
- do not synthesize a modern `input_required` result for legacy elicitation.

### Cancellation, tasks, and extensions

Timeout handling must use the selected revision and transport's cancellation behavior, followed by cleanup of requests, connections, and child processes.

- Applicable stdio modes may use the revision-supported cancellation notification.
- Modern Streamable HTTP cancellation closes the request-scoped SSE stream and does not send a cancellation notification over HTTP.
- A maximum timeout must remain enforceable even when progress is reported.
- Child-process shutdown escalation must be bounded and documented.
- Tasks and extensions must be revision- and capability-gated and fully tested before being advertised.

Do not confuse a Tasks extension status with a modern core input-required result or initialization-era elicitation.

### Ownership and workspace policy

For stdio, the client normally launches and owns a trusted bundled server command. Do not expose an arbitrary shell command or caller-selected JSON-RPC request ID as a normal public option.

For Streamable HTTP, the client normally connects to an existing endpoint and must not silently create another standalone server unless the execution policy explicitly allows it.

MCP roots and skill-specific workspace restrictions are different concepts. Use documented capabilities, server configuration, resource URIs, or explicit tool arguments rather than inventing a universal MCP `--workspace` semantic.

The presence of a server under `mcp/` neither registers it with an agent host nor starts a network listener automatically.

## Semantic-equivalence and test requirements

For an operation exposed through CLI, stdio MCP, or Streamable HTTP MCP under the same revision, identity, authorization, configuration, and workspace policy:

- inputs, results, and safety checks must have equivalent meaning;
- presentation or transport differences must not change domain behavior;
- server adapters should share one operation registry or server factory;
- contract tests must exercise all supported adapters against the same fixtures.

Protocol and transport tests must additionally cover:

- every claimed revision, negotiation path, and fallback;
- ordered raw-page preservation and flattened inventory derivation;
- page-specific cursors, cache hints, `_meta`, and unknown fields;
- schema dialects and tool-call result preservation;
- result types, cancellation, interaction policy, and extension gating;
- modern request metadata, JSON/SSE behavior, and `x-mcp-header`;
- loopback binding and Host validation;
- Origin validation on every HTTP request before dispatch;
- two or more requests on the same keep-alive or multiplexed connection with different Origin values, including rejection of each present disallowed Origin with HTTP 403;
- documented absent-Origin behavior;
- readiness, concurrency, graceful shutdown, restart, and stale-process handling;
- confirmation that local `tools show` and `tools run` do not send nonexistent MCP methods or JSON-RPC batches.
