# MCP public interface contract

This guidance is materialized by `capability.mcp` and explains caller-visible MCP behavior. The machine-readable authority for the selected protocol revision, transport inventory, and per-transport caller-visible operation exposures is `contracts/mcp-interface.json`. Runtime, SDK, startup commands, bind/port choices, and distribution remain authoritative in `RUNTIME.md`.

The initial composition baseline uses MCP `2026-07-28` Modern protocol semantics. Earlier initialization-based revisions are not a default compatibility target.

## Machine-readable authority and evidence

`contracts/mcp-interface.json` starts in `template` mode with no product claim. A selected product MCP capability switches it to `product` mode, declares the `2026-07-28` revision, declares every maintained transport, and declares every caller-visible operation exposure together with the transport that carries it.

Each declared item becomes an implementation-evidence target:

- transport: `contract-item / mcp_interface / transport / <transport-id>`
- operation exposure: `contract-item / mcp_interface / operation / <operation-id>`

Every target requires exactly one implementation-evidence record, a linked product requirement, and both positive and negative executable proof. At least one `integration-test` or `end-to-end-test` proof kind must be present in each polarity, and the linked requirement must declare compatible positive-proof strength. Static inspection and unit-only proof do not establish caller-visible MCP execution.

Proof may remain explicitly `deferred` while work is incomplete; do not replace an unavailable protocol round trip with weaker evidence. Generic implementation-evidence/release readiness remains responsible for keeping deferred proof out of a release-ready state.

The Markdown below retains qualitative protocol, security, client, and semantic-equivalence decisions that schema v1 intentionally does not encode. It does not replace the machine inventory or its evidence targets.

## Worksheet status

```text
Worksheet status: UNSELECTED
```

This marker is guidance only. Product selection is machine-visible only when `contracts/mcp-interface.json` is in `product` mode and its transport/operation inventory agrees with `RUNTIME.md` and the implementation evidence.

## Core protocol

```text
Runtime and SDK source of truth: RUNTIME.md
Selected core protocol revision: contracts/mcp-interface.json
Public compatibility statement: TODO
Discovery/negotiation behavior: TODO
Unsupported revision behavior: TODO
```

A selected Modern contract must state how callers supply per-request protocol metadata, how `server/discover` is used where applicable, and how unsupported revisions fail. Optional extensions are capability-gated and do not silently change core semantics.

## stdio server variant

```text
Supported: UNSELECTED
Launch command: TODO or NOT SUPPORTED
Lifecycle owner: host / bundled client / other: TODO
```

When supported:

- launch the server as a bounded child process;
- reserve stdout for protocol traffic and stderr for diagnostics;
- expose purpose-specific typed operations rather than arbitrary command execution;
- use the same application/domain implementation and safety checks as other adapters;
- apply documented workspace and write restrictions;
- make cancellation and shutdown deterministic.

Local stdio is normally preferable when opening a listener is unnecessary.

## Streamable HTTP server variant

```text
Supported: UNSELECTED
Start command: TODO or NOT SUPPORTED
Stop/shutdown method: TODO or NOT SUPPORTED
Endpoint URL: TODO
Bind address: TODO
Port selection: see RUNTIME.md
Authentication: TODO
Authorization: TODO
Readiness check: TODO
```

When supported:

- use the same tool/operation definitions and safety checks as stdio where the same operations are exposed;
- validate Host/authority consistently and defend against DNS rebinding;
- validate every present `Origin` on every HTTP request before dispatch;
- define the absent-Origin policy for non-browser clients;
- apply authentication, authorization, size/rate limits, and protocol-header checks per request;
- require an explicit security design before non-loopback exposure;
- define deterministic startup, readiness, cancellation, shutdown, restart, and stale-process behavior;
- keep HTTP transport behavior out of the domain layer.

A valid first request must not authorize later requests on the same keep-alive or multiplexed connection.

### Modern Streamable HTTP baseline

For the `2026-07-28` baseline, record and test:

- one new HTTP POST per JSON-RPC client message;
- `Accept` support for both JSON and request-scoped SSE responses;
- required protocol/method/name headers and their agreement with request metadata;
- safe header value handling, including tool-defined headers when the selected implementation acts as an HTTP client;
- request-scoped SSE cancellation;
- the absence of initialization-era protocol sessions, standalone MCP GET streams, session DELETE, and resumability unless a later reviewed contract changes the baseline;
- `subscriptions/listen` when long-lived change notification delivery is selected.

## Bundled ad hoc MCP tool client

A command that discovers or invokes MCP tools is a bounded MCP client, not an arbitrary protocol shell.

```text
Supported: UNSELECTED
Scope: tools only / broader client: TODO
Command: TODO or NOT SUPPORTED
Transport: stdio / Streamable HTTP / both: TODO
Invocation scope: one call / multiple sequential calls: TODO
Interaction modes: non-interactive / interactive / response file: TODO
```

A minimal tools-only client should normally expose server information/discovery, `tools/list`, and `tools/call`. Tool arguments may use JSON, file, or stdin forms, but the exact CLI names are local interface choices rather than MCP-standard names.

### Inventory and pagination

The client must:

- treat tool names as case-sensitive;
- follow pagination until no next cursor remains unless single-page mode is explicit;
- treat cursors as opaque;
- retain every raw page result as a separate ordered record in a lossless mode;
- preserve server-supplied schemas, annotations, metadata, cache hints, and future fields where practical;
- treat untrusted annotations as hints rather than authorization;
- distinguish lossless protocol output from flattened presentation views.

### Tool-call results and errors

A lossless mode preserves the complete result object and distinguishes:

1. transport failures;
2. JSON-RPC/MCP protocol errors;
3. invalid/unrecognized result types;
4. additional-input/input-required results;
5. complete domain results with an error indication;
6. complete successful domain results.

Stderr output from a stdio server is diagnostics, not by itself proof of failure.

### Multiple calls and state

A local multi-call command is client-side orchestration. Each item remains an independent protocol call. Do not infer hidden application state merely because calls reuse a process, connection, or HTTP client.

## Multi-round-trip input

When the selected revision supports a request/result model for additional client input, document the exact retry/state behavior. Non-interactive mode must not unexpectedly prompt. Every retry uses a fresh request identifier.

## Extensions

Core protocol and extension revisions are separate authorities. Extensions are selected by their own composition capabilities and advertised only when their contracts are active.

`capability.mcp-apps` owns MCP Apps behavior. A standalone browser interface is `capability.web-interface`; neither capability implies the other.

## Semantic equivalence

For an operation exposed through CLI, stdio MCP, Streamable HTTP MCP, Web, or a service under the same identity, authorization, configuration, and workspace policy:

- inputs, results, side effects, and safety checks have equivalent meaning;
- transport/presentation differences do not change domain behavior;
- adapters share one operation registry or domain implementation when justified;
- contract tests exercise all supported adapters against equivalent fixtures.

## Required tests

For every selected MCP transport, test at least:

- successful discovery/ordinary request execution for the selected revision;
- unsupported-revision behavior;
- required request metadata;
- result-type and unknown-field preservation where claimed;
- pagination where applicable;
- cancellation and timeout;
- semantic equivalence with other adapters;
- transport-specific security boundaries.

Streamable HTTP tests additionally cover Host and per-request Origin checks, connection reuse, required headers, JSON/SSE responses, and the explicitly unsupported lifecycle/session behavior.

## Decision rationale

Explain which MCP transports/client roles are supported, why they are appropriate, how callers choose them under the artifact-specific routing policy, and how the implementation preserves security and semantic equivalence.

```text
Rationale: TODO
```
