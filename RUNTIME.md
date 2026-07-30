# Runtime decision record

Complete this file before implementing a concrete skill. This is the authoritative index of toolchain, command, MCP SDK, protocol revision, compatibility, and transport choices.

## Status

```text
Selection status: UNSELECTED
```

Change the status to `SELECTED` after completing every required field.

## Primary implementation

| Item | Selected value |
|---|---|
| Language | TODO |
| Runtime | TODO |
| Minimum runtime version | TODO |
| Dependency/package manager | TODO |
| Project manifest | TODO |
| Lockfile policy | TODO |
| Source layout | TODO |
| Supported operating systems | TODO |

Examples of valid decisions include Python with pip, Python with uv, Node.js with npm, Node.js with pnpm, or bun as the runtime and package manager. These are examples, not defaults.

## Commands

Commands must work from an explicitly documented working directory.

| Purpose | Exact command |
|---|---|
| Install development dependencies | TODO |
| Run in place | TODO |
| Human CLI | TODO |
| Agent launcher | TODO |
| Start stdio MCP server | TODO or NOT SUPPORTED |
| Inspect MCP server and tool inventory | TODO or NOT SUPPORTED |
| Invoke one MCP tool over stdio | TODO or NOT SUPPORTED |
| Invoke sequential MCP tool calls over stdio | TODO or NOT SUPPORTED |
| Start local Streamable HTTP MCP server | TODO or NOT SUPPORTED |
| Stop local Streamable HTTP MCP server | TODO or NOT SUPPORTED |
| Invoke one MCP tool over Streamable HTTP | TODO or NOT SUPPORTED |
| Invoke sequential MCP tool calls over Streamable HTTP | TODO or NOT SUPPORTED |
| Check local MCP readiness | TODO or NOT SUPPORTED |
| Test | TODO |
| Lint/static analysis | TODO |
| Format check | TODO |
| Build/package | TODO or NOT APPLICABLE |

## MCP protocol support

The template does not force a protocol revision. Verify the current official MCP specification and selected SDK before completing this section.

At the time this template was aligned:

- `2026-07-28` is the current modern revision with stateless, self-contained requests, per-request metadata, and `server/discover`;
- `2025-11-25` and earlier revisions use the `initialize` / `notifications/initialized` lifecycle.

| Item | Selected value |
|---|---|
| Supported protocol revisions | TODO |
| Supported protocol eras | modern / initialization-era / both: TODO |
| Default revision or negotiation mode | TODO: automatic negotiation / fixed revision / other |
| MCP SDK or protocol library | TODO |
| SDK version | TODO |
| Legacy compatibility policy | TODO |
| JSON Schema dialects | TODO; MUST include 2020-12 when required by the selected revision |
| Optional MCP extensions | TODO or NONE |
| Deprecated feature policy | TODO |
| Negotiation and compatibility tests | TODO |

Protocol lifecycle, cancellation, interaction, subscriptions, logging, and task behavior differ between revisions. Prefer an SDK-supported negotiation path over handwritten probing. Tests must cover every revision and fallback path the concrete skill claims.

## MCP variants

Use standard MCP transport names. Do not describe a raw socket protocol as “TCP MCP” unless the project intentionally implements a non-standard custom transport. A standalone local MCP server should normally use Streamable HTTP over a loopback TCP socket.

### stdio variant

| Item | Selected value |
|---|---|
| Supported | TODO: YES or NO |
| Server entry point | TODO or NOT SUPPORTED |
| Lifecycle owner | MCP host / bundled tool client / other: TODO |
| Invocation scope | one operation / multiple sequential operations: TODO |
| Protocol negotiation/discovery | TODO |
| Request metadata behavior | TODO |
| Startup cost policy | TODO |
| Cancellation behavior | TODO |
| Child-process shutdown and escalation | TODO |

### Local Streamable HTTP variant

| Item | Selected value |
|---|---|
| Supported | TODO: YES or NO |
| Server entry point | TODO or NOT SUPPORTED |
| Endpoint path | TODO, normally `/mcp` |
| Default bind address | TODO, normally `127.0.0.1` or `::1` |
| Port | TODO: fixed, configurable, or dynamically assigned |
| Supported protocol eras | modern / initialization-era / both: TODO |
| Revision-specific state model | TODO; do not infer from transport alone |
| Concurrent-client policy | TODO |
| Authentication | TODO |
| Host-header validation | TODO |
| Allowed origins and absent-Origin policy | TODO |
| Readiness check | TODO |
| Cancellation behavior | TODO |
| Shutdown/restart policy | TODO |
| Non-loopback support | TODO: NO or documented security design |

When `2026-07-28` is supported, also complete:

| Modern Streamable HTTP requirement | Selected behavior |
|---|---|
| POST request model | TODO |
| `Accept: application/json, text/event-stream` | TODO |
| `MCP-Protocol-Version` and request `_meta` consistency | TODO |
| Required `Mcp-Method` and conditional `Mcp-Name` headers | TODO |
| Header value encoding | TODO |
| `x-mcp-header` validation and `Mcp-Param-*` emission | TODO |
| JSON and request-scoped SSE response handling | TODO |
| SSE-stream cancellation | TODO |
| `Mcp-Session-Id`, GET, DELETE, and resumability | TODO: NOT USED in modern mode |
| Initialization-era fallback on the same endpoint | TODO or NOT SUPPORTED |

The stdio and Streamable HTTP variants must expose equivalent domain operations under the same revision, identity, authorization, configuration, and workspace policy unless a documented protocol limitation prevents parity.

### Bundled ad hoc MCP tool client

Complete this section only when the skill bundles a command that discovers or invokes MCP tools.

| Item | Selected value |
|---|---|
| Supported | TODO: YES or NO |
| Scope | tools only / broader MCP client: TODO |
| Stable public command | TODO or NOT SUPPORTED |
| Supported transports | stdio / Streamable HTTP / both: TODO |
| Server-information command | TODO or NOT SUPPORTED |
| Tool-list command | TODO or NOT SUPPORTED |
| Tool-show command | TODO or NOT SUPPORTED; local filtering over `tools/list` |
| Single tool-call command | TODO or NOT SUPPORTED; maps to `tools/call` |
| Sequential tool-run command | TODO or NOT SUPPORTED; repeated `tools/call`, not JSON-RPC batch |
| Pagination request policy | TODO |
| Lossless tool-list page format | TODO: ordered page records preserving each raw `tools/list` result |
| Flattened inventory presentation | TODO: derived view, not lossless protocol output |
| Page-level cache-hint policy | TODO: do not invent a global value without a documented rule |
| Lossless call-result mode | TODO |
| Other presentation output modes | TODO |
| Modern MRTR policy | TODO or NOT SUPPORTED |
| Initialization-era elicitation policy | TODO or NOT SUPPORTED |
| Non-interactive policy | TODO |
| Timeout and cancellation policy | TODO |
| Task or extension support | TODO or NOT SUPPORTED |
| Roots/workspace policy | TODO: distinguish MCP roots from skill-specific workspace configuration |
| Exit-code mapping | TODO; keep consistent with `INTERFACES.md` |

The client command-line syntax is local to this skill. MCP standardizes protocol behavior, not names such as `tools show`, `tools run`, `--arguments-file`, or `--output`.

For paginated `tools/list`, lossless output must retain an ordered record for every page. Each record should include the request cursor used for that page as local metadata and the complete raw result object exactly as received, preserving page-specific `tools`, `nextCursor`, `resultType`, `ttlMs`, `cacheScope`, `_meta`, and unknown extensions. A flattened inventory may concatenate tool definitions for convenience, but it is a derived presentation and must not overwrite or claim to preserve page-level metadata. Single-page results use the same representation with one page record.

A tools-only client must preserve the complete result object returned by the selected SDK or wire-level parser, including `resultType`, `content`, `structuredContent`, `isError`, `_meta`, and unknown extension fields when present. In modern mode, an absent `resultType` from an earlier peer may be interpreted as `complete` for behavior, but a lossless raw mode must not fabricate fields in the preserved result.

Do not expose an arbitrary server command, shell command, or user-selected JSON-RPC request ID merely for convenience. The bundled stdio server launcher should be fixed or selected from trusted configuration. Generic workspace restrictions should be implemented through documented MCP capabilities, server configuration, resource URIs, or explicit tool arguments rather than an invented universal MCP `--workspace` option.

## Distribution

| Item | Selected value |
|---|---|
| Skill distribution | Git clone / submodule / release archive / other: TODO |
| CLI distribution | TODO |
| MCP distribution | bundled / separate package / not supported: TODO |
| Local server service integration | none / systemd / launchd / Windows service / container / other: TODO |
| Version source of truth | TODO |

## Environment and configuration

Document required environment variables without placing secrets in this repository.

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| TODO | TODO | TODO | TODO |

Network-server configuration should normally permit explicit values for bind address, port, endpoint path, authentication material location, and log level. Secret values must not be committed or passed through public process listings when a safer mechanism is available.

## Decision rationale

Explain why the selected runtime, package manager, CLI interface, MCP variants, supported revisions, compatibility policy, and optional client features fit this skill better than the credible alternatives.

Explain separately:

1. why stdio is or is not supported;
2. why a standalone local Streamable HTTP server is or is not supported;
3. whether the local server is loopback-only;
4. whether the bundled client is tools-only or broader in scope;
5. how protocol revisions are negotiated and tested;
6. how modern MRTR and initialization-era elicitation are handled;
7. how cancellation, lossless results, and exit codes are handled;
8. how paginated raw page preservation, flattened inventory presentation, and page-level cache hints are handled;
9. how all adapters share implementation and tests.

TODO