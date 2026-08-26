# MCP transport guidance

This guidance accompanies `capability.mcp`. `contracts/mcp-interface.json` owns the selected protocol revision, transport inventory, and per-transport caller-visible operation exposures. `MCP_INTERFACE.md` owns qualitative caller-visible protocol, client, security, and semantic-equivalence guidance. `RUNTIME.md` owns exact SDK/library, commands, bind/port choices, and deployment lifecycle.

## Core baseline

The initial composition baseline uses MCP core `2026-07-28` Modern semantics. A selected implementation must explicitly verify that the SDK path used actually implements the chosen revision and discovery/metadata model; installing a newer SDK alone is not conformance evidence.

## stdio

Use stdio when a host or bounded client can own the server process and a listener is unnecessary.

Required invariants:

- stdin/stdout carry protocol traffic only;
- diagnostics use stderr;
- process lifetime has an explicit owner;
- unsupported protocol openings fail explicitly rather than silently selecting another era;
- shutdown is bounded and deterministic;
- operation semantics match other maintained adapters under equivalent identity, authorization, configuration, and workspace policy.

## Streamable HTTP

A Modern endpoint accepts POST requests for MCP traffic. Security decisions are per HTTP request, never once per connection.

For each applicable request:

- validate protocol headers and their agreement with request metadata;
- validate Host/authority;
- validate every present Origin before dispatch and return an explicit denial for disallowed origins;
- apply authentication, authorization, size/rate limits, and operation policy before dispatch where practical;
- do not authorize later keep-alive or multiplexed requests from a previously valid request.

Bind local-only servers to loopback by default. Non-loopback exposure requires explicit authentication and transport-security design.

Request-scoped SSE responses are not a general server-to-client request channel. Cancellation, long-lived notification subscriptions, and any removed session/resumability behavior must follow the selected revision's contract rather than an SDK compatibility default.

## Application state

Protocol transport state is not application state. Represent durable or multi-call state through documented resources, handles, storage, explicit arguments, or application configuration.

## Additional input

When an operation requires additional client input, use the selected revision's explicit result/retry mechanism. Non-interactive clients must be able to surface that result without unexpected prompts.

## Deprecated or compatibility surfaces

Do not add deprecated transports, session behavior, or compatibility modes merely because the SDK exposes them. A concrete interoperability requirement must update the normative contract, tests, and rationale together.

## Extensions

Core MCP revision and extension revision are independent. Select and test an extension through its own capability. `capability.mcp-apps` owns the MCP Apps extension. `capability.web-interface` owns an ordinary standalone browser surface.

## Required evidence

Every transport and operation exposure declared by `contracts/mcp-interface.json` requires implementation-evidence coverage with positive and negative executable proof. Use `integration-test` or `end-to-end-test`; static inspection or unit-only proof is insufficient. Deferred executable proof is truthful incomplete state and remains release-blocking through the generic implementation-evidence release gate.

For each selected transport, establish:

- protocol revision/discovery behavior;
- ordinary successful calls;
- unsupported revision behavior;
- result preservation;
- cancellation/timeout;
- semantic equivalence;
- negative security tests.

Streamable HTTP evidence additionally covers per-request Origin/Host/auth behavior under connection reuse and every explicitly supported/unsupported HTTP lifecycle feature.
