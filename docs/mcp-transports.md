# MCP transport variants and bundled tool clients

This template supports two standard MCP server transports that share one implementation. It may also include a bounded ad hoc MCP tool client that drives those transports through standard MCP requests.

## Terminology

Use these names consistently:

- **stdio MCP server:** a client launches the server as a child process and communicates through stdin/stdout;
- **local Streamable HTTP MCP server:** an independently managed process listens on a loopback TCP socket and exposes an HTTP MCP endpoint;
- **ad hoc MCP tool client:** a bundled command that discovers and invokes MCP tools without pretending to be a complete native MCP host or general-purpose MCP client.

Do not call Streamable HTTP a raw TCP MCP transport. TCP is the underlying network protocol, while Streamable HTTP is the MCP transport presented to clients.

Do not claim resources, prompts, completion, subscriptions, tasks, sampling, elicitation, roots, or other client capabilities unless the implementation advertises and tests them.

## Protocol revisions and eras

Transport choice and protocol revision are separate decisions.

At the time this template was aligned:

| Era | Representative revision | Core model |
|---|---|---|
| Modern | `2026-07-28` | Stateless, self-contained requests; per-request metadata; `server/discover`; result types and modern multi-round-trip additional input |
| Initialization-era | `2025-11-25` and earlier | `initialize` / `notifications/initialized`; negotiated client and server capabilities; revision-specific server-to-client requests and possible legacy HTTP session behavior |

A concrete skill must record in `RUNTIME.md`:

- exact supported revisions and eras;
- SDK and version;
- fixed or automatic negotiation behavior;
- schema dialects;
- compatibility and fallback policy;
- optional core features or extensions;
- interaction and cancellation behavior;
- tests for every claimed path.

Do not hardcode a draft or release candidate as a universal baseline. Also do not describe a released modern revision as merely prospective. Recheck the official specification whenever completing the template.

## Decision matrix

| Requirement | Preferred variant |
|---|---|
| Skill needs MCP only during one workflow | stdio |
| No listening socket should remain open | stdio |
| Server process lifetime should follow one client or host | stdio |
| Several local clients need one endpoint | Streamable HTTP |
| Server maintains shared resources outside a request | Streamable HTTP, with an explicit application-state design |
| Native host is configured for a child process | stdio |
| Native host connects by URL | Streamable HTTP |
| Broader network deployment | Streamable HTTP with a separate security design |

A concrete skill may support both. Supporting both does not justify duplicate tool implementations.

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

The bundled tool client is separate:

```text
agent or human
      |
      +--> bundled MCP tool client
                    |
                    +--> stdio MCP server
                    +--> existing Streamable HTTP endpoint
```

The client must exercise the actual MCP path. It must not bypass MCP and call the application layer directly while presenting the result as an MCP invocation.

## stdio lifecycle

The stdio client or host:

1. starts the trusted server process;
2. performs the selected revision's discovery, initialization, or negotiation behavior;
3. sends one or more independent MCP requests;
4. handles only the additional-input, notification, task, or server-to-client capabilities it actually implements;
5. applies revision-appropriate cancellation;
6. closes the connection or stdin according to the SDK contract;
7. waits for the server to exit and uses bounded escalation if necessary.

The server must not daemonize or retain a listener. Stdout contains only MCP protocol messages. Stderr may contain diagnostics and must not be interpreted as an automatic operation failure.

Reusing one child process does not establish portable hidden application state between calls.

## Local Streamable HTTP lifecycle

The local server:

1. starts independently of a particular request;
2. binds to a documented loopback address and port;
3. exposes a readiness indication;
4. validates or negotiates the selected revision;
5. accepts requests using the revision-specific HTTP model;
6. handles per-request cancellation and any explicit service shutdown mechanism;
7. releases sockets and temporary resources cleanly.

Do not infer that Streamable HTTP is always stateful or always stateless. Document each supported era separately.

Service integration may be manual, systemd, launchd, a Windows service, a container, or another mechanism selected in `RUNTIME.md`.

## Modern Streamable HTTP requirements

When supporting `2026-07-28`:

- each JSON-RPC request uses its own HTTP POST;
- the client accepts both `application/json` and `text/event-stream`;
- the server may return one JSON response or a request-scoped SSE stream;
- every request sends `MCP-Protocol-Version`, consistent with the request `_meta`;
- every request sends `Mcp-Method` and, where required, `Mcp-Name`;
- transport metadata headers and JSON body values must agree;
- cancellation of an SSE response closes that request's stream;
- modern mode does not use `Mcp-Session-Id`, independent GET or DELETE endpoints, or resumability through `Last-Event-ID`;
- initialization-era behavior on the same endpoint is a separate compatibility mode and must be explicitly implemented and tested.

### Tool-defined HTTP headers

Modern tool schemas may declare `x-mcp-header` on top-level input properties.

A conforming Streamable HTTP tool client must:

- validate the extension according to the selected specification and SDK;
- exclude unusable tool definitions whose header declarations are invalid;
- remove header-designated properties from the JSON arguments sent in the request body;
- emit the corresponding encoded `Mcp-Param-*` HTTP headers;
- preserve the original tool definition in lossless diagnostic output where safe;
- test missing, malformed, duplicate, and conflicting header values.

This behavior belongs to the HTTP client adapter. It must not alter stdio tool semantics or domain logic.

## Bundled ad hoc MCP tool client

The client CLI is local to the skill. Recommended mapping:

| Local operation | Required protocol behavior |
|---|---|
| `server-info` | Modern: `server/discover`; initialization-era: report the negotiated `initialize` result and capabilities |
| `tools list` | Send `tools/list`; retain the ordered raw page sequence for lossless output and optionally derive a flattened inventory |
| `tools show TOOL` | Filter the flattened inventory derived from the complete page sequence; do not send nonexistent `tools/show`, `tools/get`, or `tools/describe` methods |
| `tools call TOOL` | Send one `tools/call` request |
| `tools run` | Orchestrate several independent `tools/call` requests; do not describe this as an MCP or JSON-RPC batch method |

The client should generate JSON-RPC request IDs internally. Do not expose an arbitrary server shell command or request ID as a normal public option.

## Tool inventory, schemas, and caching

A tools-only client must:

- treat tool names as case-sensitive;
- follow `tools/list` pagination and keep cursors opaque;
- retain each raw page result as a separate ordered record;
- scope cached pages and derived inventories to the documented revision, endpoint, identity, authorization, and cache scope;
- preserve tool input and output schemas, annotations, execution metadata, icons, and future fields where practical;
- support JSON Schema 2020-12 where required and respect supported explicit `$schema` declarations;
- treat annotations from untrusted servers as hints;
- use local input validation only as an early diagnostic;
- support any JSON value in `structuredContent` when the selected revision permits it;
- apply modern `x-mcp-header` processing only to Streamable HTTP.

Tool inventories may vary by authorization. Transport-equivalence tests must use the same revision, identity, authorization, configuration, and workspace policy.

## Lossless paginated tool lists

A paginated `tools/list` operation has two distinct output representations:

1. **Lossless page sequence:** an ordered collection of page records. Each record contains the opaque request cursor used for that request as client metadata and the complete raw MCP result object exactly as received.
2. **Flattened inventory:** a derived convenience view formed by concatenating tool arrays and adding explicitly derived metadata.

The raw result for every page preserves page-specific `tools`, `nextCursor`, `resultType`, `ttlMs`, `cacheScope`, `_meta`, and unknown extension fields. The client must not overwrite earlier page metadata with values from later pages. The request cursor is stored outside the raw result object so the received result remains unchanged.

Single-page operations use the same page-sequence representation with one record. A flattened inventory is not lossless protocol output. It must not silently choose one page's cache hint or `_meta` as the value for the whole inventory. Any aggregate expiration or cache scope must follow a documented conservative derivation rule and be marked as derived.

Tests should include pages with different cache hints, `_meta`, unknown fields, empty and nonempty cursors, and repeated or conflicting metadata to demonstrate that raw pages remain independently recoverable.

## Lossless tool-call results and error classification

A lossless tool-call output mode preserves the complete result object exactly as received, including:

- `resultType` when present;
- `content`;
- `structuredContent` of any permitted JSON type;
- `isError`;
- `_meta`;
- request-state, input-request, cache, and extension fields.

Earlier revisions omit `resultType`. A compatibility layer may normalize an absent value to effective type `complete`, but raw output must not fabricate the field.

The client distinguishes:

1. transport failure;
2. JSON-RPC or MCP protocol error;
3. invalid or unknown result type;
4. modern `input_required` result;
5. complete result with `isError: true`;
6. complete successful domain result.

## Additional-input models

### Modern multi-round-trip

For `2026-07-28`, a normal request may return `resultType: "input_required"` with input requests and opaque request state.

- Non-interactive mode may preserve and return that result without retrying.
- Interactive or response-file mode resolves the input requests and retries the original method with input responses and echoed request state.
- Each retry uses a new JSON-RPC request ID.
- Decline or cancel choices are represented by the applicable input response.

### Initialization-era server-to-client requests

For `2025-11-25` and earlier compatible modes, elicitation and other server-to-client requests use negotiated client capabilities and a request channel.

- Do not advertise a capability without implementing its handler.
- Form elicitation uses protocol-defined `accept`, `decline`, or `cancel` responses.
- A non-interactive client documents whether unsupported prompts are declined or cancelled.
- The client waits for the original operation's terminal response after answering.
- Do not synthesize a modern `input_required` result for legacy elicitation.

Tasks are separate and revision- or extension-dependent. Do not conflate task status, modern core input-required results, and initialization-era elicitation.

## Cancellation and timeouts

Timeouts must invoke the selected revision and transport's cancellation mechanism, then clean up requests, connections, and child processes.

- Initialization-era and applicable stdio modes may use the supported cancellation notification.
- Modern Streamable HTTP cancels an SSE response by closing that request's stream rather than sending a cancellation notification over HTTP.
- Progress must not extend execution beyond a documented maximum timeout indefinitely.
- Child-process escalation must be bounded and tested.

## Roots and workspace restrictions

MCP roots and a skill's workspace policy are not interchangeable concepts. Roots are revision- and capability-dependent. Newer designs may use tool arguments, resource identifiers, handles, or server configuration instead.

Do not invent a universal MCP `--workspace` semantic. A skill-specific workspace option must state exactly how it affects server configuration, tool arguments, resource identifiers, authorization, or a negotiated capability.

## Loopback security baseline

The default network variant must:

- bind to `127.0.0.1` or `::1`;
- validate the Host header and protect against DNS rebinding;
- validate `Origin` on every incoming connection;
- return HTTP 403 when a present Origin is not explicitly allowed;
- define whether an absent Origin is accepted for documented non-browser clients;
- avoid exposing secrets in URLs or process arguments;
- use an explicit endpoint path, normally `/mcp`;
- reject requests exceeding documented size or timeout limits;
- preserve the same authorization and workspace restrictions as stdio.

Loopback access reduces exposure but does not eliminate browser-origin or DNS-rebinding risk.

## Non-loopback access

Binding to all interfaces or a LAN address is a separate deployment mode. Before enabling it, document:

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
1. Use the configured local Streamable HTTP endpoint when its readiness check succeeds.
2. Otherwise launch the bundled stdio server through the ad hoc MCP tool client.
3. Otherwise use the structured CLI.
```

Starting a second network server as an implicit fallback is discouraged because it can create port conflicts, stale processes, and inconsistent state.

## Required tests

A concrete implementation should test every claimed feature, including:

- each revision, era, negotiation path, and fallback;
- equivalent operations under the same identity and authorization context;
- ordered raw-page preservation and flattened inventory derivation for `tools/list`;
- page-specific cursors, cache hints, `_meta`, and unknown fields across pagination;
- JSON Schema dialect handling;
- preservation of standard and unknown tool-call result fields;
- result-type and error classification;
- modern multi-round-trip retries and new request IDs;
- legacy elicitation actions and capability gating;
- cancellation, maximum timeout, and child-process cleanup;
- modern Streamable HTTP request headers, JSON/SSE responses, and absence of legacy session features;
- valid and invalid `x-mcp-header` definitions and emitted headers;
- loopback binding, Host rejection, Origin rejection, and absent-Origin policy;
- readiness, concurrent clients, graceful shutdown, and stale-process behavior;
- confirmation that local `tools show` and `tools run` do not send nonexistent methods or JSON-RPC batches.