# MCP transport variants and bundled tool clients

This template supports two standard MCP server transports that share one implementation. It may also include a bounded ad hoc MCP tool client and an explicitly selected local lifecycle controller. Neither helper changes the MCP protocol surface or becomes a domain operation.

## Terminology

Use these names consistently:

- **stdio MCP server:** a client launches the server as a child process and communicates through stdin/stdout;
- **Streamable HTTP MCP server:** a managed process exposes an HTTP MCP endpoint;
- **ad hoc MCP tool client:** a bundled command that discovers and invokes MCP tools without pretending to be a complete native MCP host or general-purpose client;
- **managed local lifecycle controller:** an operator command that starts, probes, restarts, and stops a fixed local Streamable HTTP process without exposing service control through MCP.

Do not call Streamable HTTP a raw TCP MCP transport. TCP is the underlying network protocol; Streamable HTTP is the MCP transport exposed to clients.

Do not claim resources, prompts, completion, subscriptions, tasks, sampling, elicitation, roots, or other client capabilities unless the implementation advertises and tests them.

## Protocol revisions and eras

Transport choice, lifecycle choice, and protocol revision are separate decisions. `RUNTIME.md` is the only source of truth for:

- exact supported revisions and the boundary between any named protocol eras;
- SDK and version;
- fixed or automatic negotiation behavior;
- schema dialects;
- compatibility and fallback policy;
- optional core features or extensions;
- interaction and cancellation behavior;
- tests for every claimed path.

This maintainer document uses revision-neutral terms such as selected modern mode and selected initialization-era mode. It must not maintain its own date-based revision snapshot. Recheck the official specification whenever completing `RUNTIME.md`.

## Decision matrix

| Requirement | Preferred variant |
|---|---|
| Skill needs MCP only during one workflow | stdio |
| No listening socket should remain open | stdio |
| Server process lifetime should follow one client or host | stdio |
| Several clients need one endpoint | Streamable HTTP |
| Server maintains shared resources outside a request | Streamable HTTP with an explicit application-state design |
| Native host is configured for a child process | stdio |
| Native host connects by URL | Streamable HTTP |
| One local endpoint needs explicit operator start/stop/restart | Streamable HTTP plus a bounded local lifecycle controller |
| Broader network deployment | Streamable HTTP with a separate security design |

A concrete skill may support both transports. Supporting both does not justify duplicate tool implementations. Selecting direct foreground or managed local lifecycle for Streamable HTTP does not create a third transport.

## Shared server composition

```text
createServer / registerOperations
            |
            +--> serve over stdio
            +--> serve over Streamable HTTP
            +--> drive through test transport
```

The shared server layer owns:

- supported tool, resource, and prompt definitions;
- input and output schemas;
- application calls;
- authorization and workspace decisions independent of transport;
- structured error mapping.

Transport entry points own protocol binding, revision-specific lifecycle, framing, request metadata, cancellation, and transport security.

The bundled tool client and lifecycle controller are separate:

```text
agent, Web backend, or human
            |
            +--> reusable or bundled MCP client adapter
                            |
                            +--> stdio MCP server
                            +--> existing Streamable HTTP endpoint

operator
            |
            +--> fixed lifecycle controller
                            |
                            +--> Streamable HTTP server process
```

The client must exercise the actual MCP path. It must not call the application layer directly while presenting the result as an MCP invocation. The lifecycle controller must not expose start, stop, restart, readiness, liveness, or PID management as MCP tools.

## stdio lifecycle

The stdio client or host:

1. starts a trusted server process;
2. performs the selected revision's discovery, initialization, or negotiation behavior;
3. sends one or more independent MCP requests;
4. handles only the capabilities it implements;
5. applies revision-appropriate cancellation;
6. closes the connection or stdin according to the SDK contract;
7. waits for server exit and uses bounded escalation if necessary.

The server must not daemonize or retain a listener. Stdout contains only MCP protocol messages. Stderr may contain diagnostics and is not automatically an operation failure.

Reusing one child process does not establish portable hidden application state between calls.

## Streamable HTTP lifecycle

The server:

1. starts independently of a particular request;
2. binds according to the deployment selected in `RUNTIME.md`;
3. exposes readiness and, when claimed, a distinct liveness signal;
4. validates or negotiates the selected revision;
5. accepts requests through the revision-specific HTTP model;
6. handles per-request cancellation and explicit service shutdown;
7. releases sockets and temporary resources cleanly.

Do not infer that Streamable HTTP is always stateful or always stateless. Document each supported era in `RUNTIME.md`.

Service integration may be manual, a bundled local lifecycle controller, systemd, launchd, a Windows service, a container, an orchestrator, or another mechanism selected in `RUNTIME.md`. Each integration mode is a separate deployment claim and needs proportionate tests.

## Managed local lifecycle boundary

A bundled local lifecycle controller is appropriate only when a concrete skill needs explicit operator-owned `start`, `stop`, `restart`, readiness, and liveness without claiming a complete OS service installation or remote deployment. It must remain outside the MCP application surface and start only a fixed, documented server entry point.

A robust controller should define and test:

- one canonical process topology and process-group ownership;
- an external secret source that does not place the secret value in argv, public logs, or PID metadata;
- an atomic, owner-only lifecycle record containing enough identity to reject PID reuse;
- bounded startup readiness and separate liveness behavior;
- identity verification before every signal;
- graceful TERM shutdown followed by bounded KILL escalation;
- stale-record handling that never signals an unrelated process;
- safe handling of symlinks, non-regular files, wrong ownership, excessive permissions, oversized records, and incomplete writes;
- restart as a complete bounded stop followed by start, unless a separately tested handoff topology is selected;
- negative tests proving that configuration and secret failures occur before listener creation.

PID alone is not a sufficient identity on systems that reuse process IDs. Use an operating-system-supported process start identity, process handle, pidfd, service-manager unit identity, container identity, or equivalent authority. State the supported operating systems and reject unsupported identity mechanisms rather than silently weakening the check.

A local controller does not by itself provide automatic restart, privilege separation, socket activation, log rotation, zero-downtime upgrade, multi-worker coordination, TLS, reverse-proxy trust, container isolation, orchestration, persistence, backup, or remote incident response. Do not call the resulting fixture production-ready beyond the exact topology and boundaries it executes.

## Request-scoped HTTP security

Host, Origin, authentication, authorization, size-limit, and protocol-header decisions are request-scoped. They are not properties of the TCP, TLS, HTTP/1.1 keep-alive, HTTP/2, or later multiplexed connection.

For every HTTP request, before MCP dispatch:

- validate Host and apply DNS-rebinding protection;
- evaluate the request's `Origin` independently;
- return HTTP 403 when a present Origin is not explicitly allowed;
- apply the documented absent-Origin policy;
- authenticate and authorize the request where required;
- enforce request-size and timeout limits;
- validate revision-specific protocol headers.

Do not cache an allow decision on the connection and reuse it for later requests. Every request must pass the complete request-level gate before parsing or dispatching its MCP operation where practical.

Origin validation is required even when browser clients are not intended. Loopback reduces exposure but does not eliminate browser-origin or DNS-rebinding risks.

## Modern Streamable HTTP behavior

When the selected revision requires the modern Streamable HTTP contract:

- each JSON-RPC request uses its own HTTP POST;
- clients accept both `application/json` and `text/event-stream`;
- servers may return JSON or a request-scoped SSE stream;
- each request carries the required protocol revision and method metadata;
- method-specific name metadata is included where required;
- transport metadata headers and JSON body values agree;
- cancellation of an SSE response closes that request's stream;
- modern mode does not use initialization-era session IDs, independent GET or DELETE endpoints, or resumability unless the selected specification explicitly requires them;
- initialization-era behavior on the same endpoint is a separate compatibility mode and must be implemented and tested explicitly.

### Tool-defined HTTP headers

A selected modern revision may allow tool schemas to designate top-level input properties as HTTP headers.

A conforming Streamable HTTP tool client must:

- validate the declaration according to the selected specification and SDK;
- exclude unusable tool definitions whose header declarations are invalid;
- remove header-designated properties from JSON arguments;
- emit the corresponding encoded transport headers;
- preserve the original tool definition in lossless diagnostic output where safe;
- test missing, malformed, duplicate, and conflicting header values.

This behavior belongs to the HTTP client adapter. It must not alter stdio tool semantics or domain logic.

## Bundled ad hoc MCP tool client

Recommended mapping:

| Local operation | Required protocol behavior |
|---|---|
| `server-info` | Report discovery or negotiated server information according to the selected revision |
| `tools list` | Send `tools/list`; retain the ordered raw-page sequence and optionally derive a flattened inventory |
| `tools show TOOL` | Filter the derived inventory locally; do not send nonexistent `tools/show`, `tools/get`, or `tools/describe` methods |
| `tools call TOOL` | Send one `tools/call` request |
| `tools run` | Orchestrate several independent `tools/call` requests; reject an empty `--call` sequence before creating a transport; do not call this MCP or JSON-RPC batching |

Generate JSON-RPC request IDs internally. Do not expose arbitrary server shell commands or caller-selected request IDs as normal public options.

## Tool inventory, schemas, and caching

A tools-only client must:

- treat tool names as case-sensitive;
- follow `tools/list` pagination and keep cursors opaque;
- retain each raw page result as a separate ordered record;
- scope cached pages and derived inventories to revision, endpoint, identity, authorization, page, and cache scope;
- preserve input/output schemas, annotations, execution metadata, icons, and future fields where practical;
- validate the selected revision's known initialization capability objects and boolean change/subscription flags;
- reject a listed tool whose optional `_meta` is not an object;
- support the schema dialects selected in `RUNTIME.md`;
- treat annotations from untrusted servers as hints;
- use local validation only as an early diagnostic;
- support any JSON value in `structuredContent` when permitted;
- apply tool-defined HTTP-header processing only to Streamable HTTP.

Tool inventories may vary by authorization. Transport-equivalence tests must use the same revision, identity, authorization, configuration, and workspace policy.

## Lossless paginated tool lists

A paginated `tools/list` operation has two distinct representations:

1. **Lossless page sequence:** ordered page records containing the opaque request cursor as client metadata and the complete raw MCP result exactly as received.
2. **Flattened inventory:** a derived convenience view created by concatenating tool arrays and adding explicitly derived metadata.

Every raw page preserves page-specific `tools`, `nextCursor`, `resultType`, cache hints, `_meta`, and unknown fields. Do not overwrite earlier page metadata with later values. Store the request cursor outside the raw result.

Single-page operations use the same representation with one page record. A flattened inventory is not lossless output. It must not choose one page's cache hint or `_meta` as the global value. Any aggregate expiration or cache scope requires a documented conservative rule and a derived label.

Tests should include different cache hints, `_meta`, unknown fields, empty and nonempty cursors, and conflicting metadata to show that every raw page remains recoverable.

## Lossless tool-call results and errors

Lossless tool-call output preserves the complete result exactly as received, including:

- `resultType` when present;
- `content`;
- `structuredContent` of any permitted JSON type;
- `isError`;
- `_meta`;
- request-state, input-request, cache, and extension fields.

A compatibility layer may interpret an absent result type according to the selected revision, but raw output must not fabricate the field.

Distinguish:

1. transport failure;
2. JSON-RPC or MCP protocol error;
3. invalid or unknown result type;
4. selected modern input-required result;
5. complete result with `isError: true`;
6. complete successful domain result.

## Additional-input models

### Selected modern multi-round-trip behavior

When the selected revision permits a normal request to return an input-required result:

- non-interactive mode may preserve and return the result without retrying;
- interactive or response-file mode retries with input responses and echoed request state;
- every retry uses a new JSON-RPC request ID;
- decline or cancel choices are represented in the applicable input response.

### Selected initialization-era server-to-client requests

When an initialization-era mode is selected:

- do not advertise a capability without implementing its handler;
- answer form elicitation with `accept`, `decline`, or `cancel`;
- document automatic decline or cancellation in non-interactive mode;
- wait for the original operation's terminal response;
- do not synthesize a modern input-required result.

Tasks are separate and revision- or extension-dependent. Do not conflate task status, modern core input-required results, and initialization-era elicitation.

## Cancellation and timeouts

Timeouts must invoke the selected revision and transport's cancellation mechanism and then clean up requests, connections, and child processes.

- Applicable stdio modes may use the supported cancellation notification.
- Modern Streamable HTTP cancels an SSE response by closing that request's stream when required by the selected revision.
- Progress must not extend execution beyond a documented maximum timeout indefinitely.
- Child-process and managed-process escalation must be bounded and tested.

## Roots and workspace restrictions

MCP roots and a skill's workspace policy are not interchangeable. A selected revision may instead use tool arguments, resource identifiers, handles, or server configuration.

Do not invent a universal MCP `--workspace` semantic. A skill-specific workspace option must state exactly how it affects configuration, arguments, resource identifiers, authorization, or negotiated capabilities.

## Loopback security baseline

For a local-only network variant:

- bind to `127.0.0.1` or `::1`;
- validate Host and protect against DNS rebinding on every request;
- validate Origin on every request before dispatch;
- return HTTP 403 for each request with a present disallowed Origin;
- define absent-Origin behavior;
- avoid exposing secrets in URLs, process arguments, PID records, or public logs;
- use an explicit endpoint, normally `/mcp`;
- reject requests exceeding documented size or timeout limits;
- preserve the same authorization and workspace restrictions as stdio.

## Non-loopback access

Accepting requests from other nodes is a separate deployment mode. Before enabling it, document:

- intended clients and trust boundary;
- authentication and authorization;
- TLS or trusted reverse-proxy termination;
- firewall assumptions;
- allowed hosts and origins;
- secret provisioning and rotation;
- audit logging and rate limits;
- upgrade and incident-response procedures.

The language-neutral template does not prescribe one authentication implementation.

## Agent fallback policy

When both transports exist, `INTERFACES.md` must define a deterministic order, for example:

```text
1. Use the configured Streamable HTTP endpoint when readiness succeeds.
2. Otherwise launch the bundled stdio server through the ad hoc MCP tool client.
3. Otherwise use the structured CLI.
```

Starting or controlling a network server as an implicit agent fallback is discouraged because it creates port-conflict, stale-process, secret, state-consistency, and ownership risks. Lifecycle selection belongs to the operator and `RUNTIME.md`.

## Required tests

Test every claimed feature, including:

- each revision, era, negotiation path, and fallback;
- equivalent operations under the same identity and authorization context;
- ordered raw-page preservation and flattened inventory derivation;
- page-specific cursors, cache hints, `_meta`, and unknown fields;
- schema dialect handling and lossless call-result preservation;
- result-type and error classification;
- selected modern multi-round-trip retries and initialization-era elicitation actions;
- cancellation, maximum timeout, and child-process cleanup;
- modern request headers, JSON/SSE responses, and absence of initialization-era session features when required by the selected revision;
- valid and invalid tool-defined HTTP-header declarations and emitted headers;
- loopback binding and per-request Host/Origin validation;
- a reused HTTP/1.1 keep-alive or multiplexed connection carrying requests with different Origin values;
- HTTP 403 for each present disallowed Origin and documented handling of absent Origin;
- readiness, liveness, concurrent clients, graceful shutdown, restart, and stale-process behavior;
- managed secret validation before process creation, process-identity verification, atomic lifecycle records, and bounded TERM/KILL escalation when that variant is selected;
- confirmation that local `tools show` and `tools run` do not send nonexistent methods or JSON-RPC batches;
- confirmation that service-control actions are not MCP tools or implicit fallbacks.
