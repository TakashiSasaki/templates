# MCP public interface contract

Retain and complete this file only when `mcp-enabled` is selected. It defines caller-visible MCP behavior. Runtime, SDK, exact protocol revisions, protocol-era boundaries, transport startup commands, and distribution selections remain authoritative in `RUNTIME.md`.

## Status

```text
Selection status: UNSELECTED
```

Change the status to `SELECTED` only after all supported variants are concrete, every unsupported variant is explicitly marked `NO`, and the public behavior agrees with `RUNTIME.md`.

## MCP protocol reference

```text
Runtime, SDK, revision, era boundary, and schema source of truth: RUNTIME.md
Public negotiation and fallback behavior: TODO
Public compatibility statement: TODO
```

Do not duplicate the selected SDK version or revision list here. Explain what callers observe when negotiation succeeds, falls back, or fails, and which behavior remains stable across supported revisions.

## stdio MCP server variant

```text
Supported: UNSELECTED
Launch command: TODO or NOT SUPPORTED
Lifecycle owner: MCP host / bundled tool client / other: TODO
```

When supported:

- launch the server as a trusted child process;
- expose purpose-specific tools with typed inputs;
- reserve stdout for protocol traffic and send logs to stderr;
- perform the lifecycle, discovery, request-metadata, and capability behavior required by the selected revision;
- use revision-appropriate cancellation and bounded child-process shutdown escalation;
- preserve standard MCP results and extension fields;
- reuse the same application or domain implementation as other maintained adapters;
- enforce documented workspace and write restrictions;
- avoid generic `run_command` or arbitrary-code tools.

This is normally the preferred transport for ad hoc local use because it opens no listening socket and ties server lifetime to the invoking host or client.

## Streamable HTTP MCP server variant

MCP does not define raw TCP as a standard transport. A standalone network server should normally expose Streamable HTTP.

```text
Supported: UNSELECTED
Start command: TODO or NOT SUPPORTED
Stop command or shutdown method: TODO or NOT SUPPORTED
Endpoint URL: TODO, for example http://127.0.0.1:3000/mcp
Bind address: TODO, normally 127.0.0.1 or ::1 for local-only use
Port selection: see RUNTIME.md
Supported protocol eras: see RUNTIME.md
Revision-specific state model: see RUNTIME.md
Authentication: TODO
Health/readiness check: TODO
```

When supported:

- use the same server factory, tool definitions, schemas, safety checks, and operation implementation as stdio;
- bind according to the deployment and exposure policy in `RUNTIME.md`;
- validate the HTTP Host header and protect against DNS rebinding;
- validate `Origin` on every HTTP request before dispatch, including requests sharing HTTP/1.1 keep-alive or multiplexed connections;
- return HTTP 403 for each request whose present `Origin` is not explicitly allowed;
- define whether an absent `Origin` is accepted for documented non-browser clients;
- perform Host, Origin, authentication, authorization, size-limit, and protocol-header checks before operation dispatch where practical;
- require an explicit security design before allowing non-loopback clients;
- define deterministic startup, readiness, cancellation, shutdown, restart, and stale-process behavior;
- avoid placing secrets in command-line arguments or committed configuration;
- keep HTTP behavior out of the domain layer.

A connection-level approval must never authorize later requests on that connection. Request headers may change between requests.

When the selected revision requires the modern Streamable HTTP contract, also require:

- one HTTP POST for each JSON-RPC request;
- `Accept` support for both `application/json` and `text/event-stream`;
- JSON and request-scoped SSE responses;
- required revision, method, and method-specific name metadata on each request;
- encoded transport headers that agree with the JSON body;
- validation and emission of tool-defined HTTP headers where supported;
- cancellation by closing the applicable request-scoped SSE stream;
- no initialization-era session behavior in modern mode unless explicitly required by the selected specification;
- explicit tests for any initialization-era compatibility on the same endpoint.

Origin validation is required even when browser clients are not intended. State whether the endpoint is local-machine-only, trusted-LAN, or broader deployment. The latter two require additional authentication and transport-security decisions.

## Bundled ad hoc MCP tool client

A command that only discovers and invokes MCP tools is an **ad hoc MCP tool client**, not a complete MCP host or general MCP client.

```text
Supported: UNSELECTED
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
| `server-info` | Report discovery or negotiated server information according to the selected revision |
| `tools list` | Send `tools/list`; preserve an ordered raw-page sequence and optionally derive a flattened inventory |
| `tools show TOOL` | Filter the derived flattened inventory locally; there is no standard `tools/show`, `tools/get`, or `tools/describe` method |
| `tools call TOOL` | Send one `tools/call` request |
| `tools run` | Send multiple independent `tools/call` requests; do not represent this as an MCP or JSON-RPC batch method |

A minimal tools-only client should normally expose `server-info`, `tools list`, and `tools call`.

### Recommended options

```text
--transport stdio|http
--endpoint URL
--protocol-version VALUE|auto
--timeout SECONDS
--max-timeout SECONDS
--output mcp-json|json|jsonl|pretty
--client-log-level LEVEL
--non-interactive
--input-responses-file PATH
--help
--version
```

Tool arguments may be accepted through mutually exclusive `--arguments JSON`, `--arguments-file PATH`, or `--arguments-stdin` forms. These names are recommendations, not MCP-standard names.

### Tool inventory, schemas, and caching

The client must:

- treat tool names as case-sensitive;
- follow `tools/list` pagination until no next cursor remains unless single-page mode is explicitly requested;
- treat cursors as opaque, including an empty-string cursor when permitted by the selected revision;
- retain every raw page result as a separate ordered record;
- apply cache hints only within their documented identity, authorization, revision, page, and cache scope;
- preserve tool fields supplied by the server, including schemas, annotations, execution metadata, icons, and future fields where practical;
- support the schema dialects selected in `RUNTIME.md`;
- treat annotations from an untrusted server as hints;
- use local argument validation only as an early diagnostic;
- validate `structuredContent` against a declared output schema when supported;
- allow `structuredContent` to contain any JSON value when permitted by the selected revision;
- apply tool-defined HTTP-header processing only to Streamable HTTP.

Tool inventories may differ by per-request authorization. Equivalence tests must use the same revision, identity, authorization, configuration, and workspace policy.

### Lossless paginated tool-list output

Lossless and presentation-oriented list outputs are separate contracts. A lossless mode retains an ordered page sequence:

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
    }
  ],
  "metadata": {
    "pageCount": 1
  }
}
```

Each page's `mcpResult` must not be normalized, merged, or stripped. Preserve page-specific `tools`, `nextCursor`, `resultType`, cache hints, `_meta`, and unknown fields. `requestCursor` is client metadata and must not be inserted into the received result.

A flattened inventory may concatenate tool arrays and add explicitly derived metadata, but it is not lossless output. It must not select one page's cache fields as global values or silently merge page-level `_meta`.

### Tool-call results and errors

A lossless tool-call mode preserves the complete result object, including `resultType`, `content`, `structuredContent`, `isError`, `_meta`, and unknown extensions. A compatibility layer may interpret an absent legacy result type, but lossless output must not fabricate the field.

The client must distinguish:

1. transport failures;
2. JSON-RPC or MCP protocol errors;
3. unrecognized or invalid result types;
4. selected modern input-required results;
5. complete `tools/call` results with `isError: true`;
6. complete successful domain results.

Do not infer that stderr output from a stdio server is necessarily a failure.

### Multiple calls and application state

A local `tools run` command is client-side orchestration. Each item remains a separate `tools/call` request. Do not assume hidden application state merely because calls reuse a process, connection, or HTTP client. Represent required state using documented arguments, resource identifiers, handles, storage, or server configuration.

### Selected modern multi-round-trip requests

When the selected revision permits an input-required result:

- non-interactive mode may preserve and return that result without retrying;
- interactive or response-file mode resolves the input requests and retries the original method with input responses and echoed request state;
- every retry uses a new JSON-RPC request ID;
- decline or cancel choices are represented in the applicable input response.

### Selected initialization-era server-to-client requests

When an initialization-era mode is selected:

- do not advertise elicitation, sampling, roots, or other client capabilities without implementing their handlers;
- answer form elicitation with `accept`, `decline`, or `cancel`;
- document automatic decline or cancellation in non-interactive mode;
- wait for the original operation's terminal response;
- do not synthesize a modern input-required result for initialization-era elicitation.

### Cancellation, tasks, and extensions

Timeout handling must use the selected revision and transport's cancellation behavior, followed by cleanup of requests, connections, and child processes. Maximum timeout remains enforceable during progress. Tasks and extensions must be revision- and capability-gated and fully tested before being advertised.

Do not confuse a Tasks extension status with a modern core input-required result or initialization-era elicitation.

### Ownership and workspace policy

For stdio, the client normally launches and owns a trusted bundled server command. Do not expose an arbitrary shell command or caller-selected JSON-RPC request ID as a normal public option.

For Streamable HTTP, the client normally connects to an existing endpoint and must not silently create another standalone server unless `INTERFACES.md` explicitly allows that fallback.

MCP roots and skill-specific workspace restrictions are different concepts. Use documented capabilities, server configuration, resource URIs, or explicit tool arguments rather than inventing a universal MCP `--workspace` semantic.

The presence of a server under `mcp/` neither registers it with an agent host nor starts a network listener automatically.

## Semantic-equivalence and test requirements

For an operation exposed through CLI, stdio MCP, or Streamable HTTP MCP under the same revision, identity, authorization, configuration, and workspace policy:

- inputs, results, side effects, and safety checks must have equivalent meaning;
- presentation or transport differences must not change domain behavior;
- server adapters should share one operation registry or server factory;
- contract tests must exercise all supported adapters against the same fixtures.

Protocol and transport tests must additionally cover every claimed revision and fallback, ordered raw-page preservation, schemas and result types, cancellation and interaction policy, loopback and Host handling, per-request Origin validation including connection reuse, absent-Origin behavior, readiness, concurrency, graceful shutdown, and confirmation that local `tools show` and `tools run` do not send nonexistent MCP methods or JSON-RPC batches.

## Decision rationale

Explain why each MCP variant is supported or omitted, how agents choose among native MCP, an existing endpoint, bundled stdio launch, and CLI fallback, and how the selected design preserves compatibility and security.

```text
Rationale: TODO
```
