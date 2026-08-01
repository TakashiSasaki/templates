# MCP public interface contract

## Status

Selection status: SELECTED

## MCP protocol reference

Runtime, SDK, revision, era boundary, and schema source of truth: RUNTIME.md
Public negotiation and fallback behavior: The caller must initialize with revision `2025-11-25`; another revision receives a JSON-RPC invalid-params error and no fallback is attempted.
Public compatibility statement: Within fixture version 1.x, the `text_stats` tool name, required string input `text`, read-only semantics, and existing `bytes`, `lines`, and `words` result fields remain compatible. Additive MCP result fields must be preserved by callers.

## stdio MCP server variant

Supported: YES
Launch command: bundle exec ruby mcp/server.rb
Lifecycle owner: MCP host

The host launches the trusted bundled command from the skill root, completes initialization before discovery, may send multiple sequential requests, closes stdin when finished, and uses the bounded shutdown escalation documented in `RUNTIME.md`. Stdout contains newline-delimited JSON-RPC protocol messages only. Startup, shutdown, and exception diagnostics use stderr.

## Streamable HTTP MCP server variant

Supported: NO
Start command: NOT SUPPORTED
Stop command or shutdown method: NOT SUPPORTED
Endpoint URL: NOT SUPPORTED
Bind address: NOT SUPPORTED
Port selection: NOT SUPPORTED
Supported protocol eras: NOT SUPPORTED
Revision-specific state model: NOT SUPPORTED
Authentication: NOT SUPPORTED
Health/readiness check: NOT SUPPORTED

No HTTP endpoint or listener is included in this fixture.

## Bundled ad hoc MCP tool client

Supported: NO
Scope: NOT SUPPORTED
Command: NOT SUPPORTED
Transport used: NOT SUPPORTED
Negotiation and compatibility behavior: NOT SUPPORTED
Invocation scope: NOT SUPPORTED
Interaction modes: NOT SUPPORTED
Task or extension support: NOT SUPPORTED

The repository test client is private validation code and is not a stable public command.

### Tool inventory, schemas, and caching

`tools/list` returns one page containing the case-sensitive `text_stats` definition with Draft 2020-12 input and output schemas and read-only annotations. No cursor, cache hint, or custom `_meta` value is emitted. Test code retains and inspects the complete raw page result rather than synthesizing another discovery method.

### Lossless paginated tool-list output

The selected inventory is a single raw MCP result page. Validation keeps that result intact, records the request cursor as `null` outside the result when constructing test assertions, and does not flatten, normalize, or invent page-level cache metadata. Future pagination would require a separate contract and tests before being claimed.

### Tool-call results and errors

A successful `tools/call` result preserves `content`, `structuredContent`, `isError`, `_meta`, and unknown additive fields. Missing or invalid `text` arguments return a complete MCP tool result with `isError: true`; they are not transport failures. Unknown JSON-RPC methods return a JSON-RPC method-not-found error. The caller keeps those outcomes distinct from child-process failure and successful domain results.

### Multiple calls and application state

One initialized stdio process may serve multiple independent `tools/call` requests. The operation is stateless: every result depends only on the current request's `text` argument, and no hidden state is inferred from process reuse.

### Selected modern multi-round-trip requests

Modern input-required results and multi-round-trip retry behavior are not supported or advertised by the selected revision contract. The caller never fabricates input responses or retries a call as though that feature were negotiated.

### Selected initialization-era server-to-client requests

The fixture advertises no elicitation, sampling, roots, or other server-to-client request capability. The private test client declares an empty capability object and therefore needs no server-to-client request handlers.

### Cancellation, tasks, and extensions

The sole operation is synchronous and bounded. A caller-side timeout ends the session by closing stdin and applying the documented TERM/KILL escalation, and tests prove abnormal termination is reaped without hanging. Tasks and optional extensions are not advertised.

### Ownership and workspace policy

The MCP host owns the trusted `mcp/server.rb` child process. The tool accepts text data directly, has no filesystem workspace semantic, opens no network connection, and exposes no arbitrary command, request-ID, or server-command option.

## Semantic-equivalence and test requirements

Tests exercise exact-revision initialization, tools-only capabilities, raw tool inventory, deterministic success, missing-input tool error, unknown-method JSON-RPC error, sequential calls after errors, stdout/stderr separation, graceful EOF shutdown, and bounded abnormal termination through the actual stdio transport.

## Decision rationale

Rationale: One stdio tool is sufficient to prove the executable `mcp-enabled` profile contract. Omitting HTTP and a public client keeps transport security, lifecycle, and caller behavior proportional to the fixture while preserving a real initialization and `tools/list`/`tools/call` protocol path.
