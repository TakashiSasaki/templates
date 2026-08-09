# MCP implementation area

Retain this directory only when the concrete Skill selects `mcp-enabled` and actually needs bundled MCP implementation files. `RUNTIME.md` is authoritative for the selected SDK/library, exact commands, transport variants, and distribution. `MCP_INTERFACE.md` is authoritative for caller-visible protocol behavior.

The unpublished template baseline is MCP core `2026-07-28`, Modern-only.

## Implementation checklist

For every bundled server implementation:

- use an SDK/library path that explicitly supports MCP `2026-07-28`;
- serve `server/discover` and require Modern per-request metadata;
- reject unsupported protocol revisions with `UnsupportedProtocolVersionError`;
- do not accept the Legacy `initialize` / `notifications/initialized` lifecycle;
- do not expose deprecated Roots, Sampling, Logging, or HTTP+SSE by default;
- share one domain operation implementation across stdio, Streamable HTTP, CLI, or browser adapters when several interfaces expose the same behavior;
- keep generic shell execution and arbitrary-code tools out of the public MCP surface.

### stdio

When stdio is selected:

- reserve stdout for protocol traffic and send diagnostics to stderr;
- reject Legacy openings rather than falling back to an initialization session;
- keep child-process shutdown bounded and deterministic;
- test `server/discover`, ordinary calls, unsupported-revision rejection, cancellation, and process cleanup.

### Streamable HTTP

When Streamable HTTP is selected:

- expose one MCP endpoint accepting POST;
- send every client JSON-RPC message in a new POST;
- support JSON and request-scoped SSE responses;
- require the revision, method, and conditional name headers defined by `2026-07-28` and validate them against the JSON body;
- implement safe `x-mcp-header` / `Mcp-Param-*` handling when acting as a Streamable HTTP client;
- validate Host and every present Origin on every request, including connection reuse;
- treat closing a request-scoped SSE response stream as cancellation of that request;
- do not use `Mcp-Session-Id`, a standalone MCP GET stream, DELETE session cleanup, or `Last-Event-ID` resumability;
- use `subscriptions/listen` for selected long-lived change notifications.

## Bundled client

A bundled tool-oriented client is optional. When retained, it must require Modern `2026-07-28` rather than silently falling back to a Legacy server. Preserve raw MCP results and pagination pages before deriving presentation views. Do not expose caller-selected JSON-RPC request IDs or arbitrary server shell commands as normal public options.

## Multi-round-trip input

When additional input is needed, use the Modern `InputRequiredResult` / `input_required` flow and retry the original request with input responses. Do not recreate Legacy server-to-client elicitation, sampling, or roots request channels.

## Extensions

Extensions are independently negotiated capabilities. Do not make the core MCP server depend on an extension unless the concrete Skill intentionally requires it and documents the failure behavior when the peer does not advertise it.

MCP Apps support, when selected, is governed by its own extension contract and resources. It does not imply that `WEB_INTERFACE.md` or a standalone browser UI must be retained.

## Tests

Every claimed variant must have executable positive and negative evidence. At minimum test discovery, revision rejection, request metadata, tool schemas, result preservation, cancellation, transport security where applicable, and semantic equivalence with other maintained interfaces.
