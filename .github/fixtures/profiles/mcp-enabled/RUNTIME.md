# Runtime decision record

## Status

Selection status: SELECTED

## Primary implementation

| Item | Selected value |
|---|---|
| Language | JavaScript (ES modules) |
| Runtime | Node.js |
| Minimum runtime version | 20 |
| Dependency/package manager | npm |
| Project manifest | `package.json` |
| Lockfile policy | The fixture pins every direct dependency exactly in `package.json`; maintainer CI installs from the public npm registry for executable evidence and does not publish this fixture as a package. |
| Source layout | `src/text_stats.mjs` owns deterministic domain logic; `mcp/server.mjs` owns the MCP adapter; `tests/test_mcp.mjs` owns Modern protocol evidence. |
| Supported operating systems | Linux, macOS, and Windows environments supported by Node.js 20+ and the official TypeScript MCP SDK; maintainer CI executes on Ubuntu. |

## Commands

Run every command from the fixture root.

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | `npm install --ignore-scripts` |
| Run in place | `node mcp/server.mjs` |
| Agent launcher | `node mcp/server.mjs` |
| Test | `npm test` |
| Lint/static analysis | `npm run check` |
| Format check | `npm run check` |
| Build/package | NOT APPLICABLE |

### Packaged CLI commands

| Purpose | Exact command |
|---|---|
| Human CLI | NOT APPLICABLE |

### MCP commands

| Purpose | Exact command |
|---|---|
| Start stdio MCP server | `node mcp/server.mjs` |
| Inspect MCP server and tool inventory | `node --test --test-name-pattern="Modern client discovers" tests/test_mcp.mjs` |
| Invoke one MCP tool over stdio | `node --test --test-name-pattern="Modern client discovers" tests/test_mcp.mjs` |
| Invoke sequential MCP tool calls over stdio | `npm test` |
| Start Streamable HTTP MCP server | NOT SUPPORTED |
| Stop Streamable HTTP MCP server | NOT SUPPORTED |
| Invoke one MCP tool over Streamable HTTP | NOT SUPPORTED |
| Invoke sequential MCP tool calls over Streamable HTTP | NOT SUPPORTED |
| Check MCP readiness | NOT SUPPORTED; stdio readiness is established by successful Modern discovery and invocation |

### Browser-interface commands

| Purpose | Exact command |
|---|---|
| Start human verification Web UI | NOT SUPPORTED |
| Stop human verification Web UI | NOT SUPPORTED |
| Check human verification Web UI readiness | NOT SUPPORTED |

### Headless-service commands

| Purpose | Exact command |
|---|---|
| Start headless service | NOT SUPPORTED |
| Stop headless service | NOT SUPPORTED |
| Check headless service readiness | NOT SUPPORTED |

## MCP protocol support

| Item | Selected value |
|---|---|
| Supported protocol revisions | `2026-07-28` |
| Supported protocol eras | modern |
| Default revision or negotiation mode | Fixed/pinned `2026-07-28`; the official SDK client test uses `versionNegotiation.mode.pin` and the server uses `legacy: "reject"`; no fallback occurs. |
| MCP SDK or protocol library | Official TypeScript MCP SDK split packages `@modelcontextprotocol/server` and `@modelcontextprotocol/client` |
| SDK version | `2.0.0` |
| Legacy compatibility policy | NOT SUPPORTED; `2025-11-25` and earlier initialization openings are rejected with `UnsupportedProtocolVersionError`. |
| JSON Schema dialects | JSON Schema 2020-12-compatible schemas through Zod 4 and the official SDK's schema conversion/validation path. |
| Optional MCP extensions | NONE |
| Deprecated feature policy | Deprecated Roots, Sampling, Logging, and HTTP+SSE are not advertised or implemented by this fixture. |
| Negotiation and compatibility tests | `tests/test_mcp.mjs` proves Modern discovery, pinned Modern client operation, rejection of a Legacy initialize opening, and `UnsupportedProtocolVersionError` for an unsupported Modern revision. |

## MCP variants

### stdio variant

| Item | Selected value |
|---|---|
| Supported | YES |
| Server entry point | `mcp/server.mjs` |
| Lifecycle owner | MCP host or the test client's `StdioClientTransport` |
| Invocation scope | Multiple sequential operations may share the Modern stdio connection; each request carries Modern request metadata. |
| Protocol negotiation/discovery | `server/discover` selects `2026-07-28`; the fixture client pins `2026-07-28`; `serveStdio(..., { legacy: "reject" })` rejects Legacy openings. |
| Request metadata behavior | The official SDK sends and validates the `io.modelcontextprotocol/protocolVersion` and client-capabilities request metadata for Modern calls and emits server identity in response metadata. |
| Startup cost policy | Start one trusted Node.js child process when the MCP host activates the fixture and reuse it for bounded calls. |
| Cancellation behavior | The official stdio transport owns protocol cancellation; closing the client closes stdin and terminates the child using the SDK's bounded stdio transport shutdown behavior. |
| Child-process shutdown and escalation | The official `StdioClientTransport.close()` closes the spawned child transport; fixture tests always call `client.close()` and raw negative probes apply TERM then KILL only if needed. |

### Streamable HTTP variant

| Item | Selected value |
|---|---|
| Supported | NO |
| Server entry point | NOT SUPPORTED |
| Endpoint path | NOT SUPPORTED |
| Default bind address | NOT SUPPORTED |
| Port | NOT SUPPORTED |
| Supported protocol eras | NOT SUPPORTED |
| Revision-specific state model | NOT SUPPORTED; this fixture opens no HTTP MCP endpoint. |
| Concurrent-client policy | NOT SUPPORTED |
| Authentication | NOT SUPPORTED |
| Host-header validation | NOT SUPPORTED |
| Origin validation granularity | NOT SUPPORTED |
| Allowed origins and absent-Origin policy | NOT SUPPORTED |
| Connection-reuse security tests | NOT SUPPORTED |
| Readiness check | NOT SUPPORTED |
| Cancellation behavior | NOT SUPPORTED |
| Shutdown/restart policy | NOT SUPPORTED |
| Non-loopback support | NOT SUPPORTED |

| Modern Streamable HTTP requirement | Selected behavior |
|---|---|
| POST request model | NOT SUPPORTED |
| `Accept: application/json, text/event-stream` | NOT SUPPORTED |
| `MCP-Protocol-Version` and request `_meta` consistency | NOT SUPPORTED |
| Required `Mcp-Method` and conditional `Mcp-Name` headers | NOT SUPPORTED |
| Header value encoding | NOT SUPPORTED |
| `x-mcp-header` validation and `Mcp-Param-*` emission | NOT SUPPORTED |
| JSON and request-scoped SSE response handling | NOT SUPPORTED |
| SSE-stream cancellation | NOT SUPPORTED |
| `Mcp-Session-Id`, GET, DELETE, and resumability | NOT USED |
| Initialization-era fallback on the same endpoint | NOT SUPPORTED |

### Bundled ad hoc MCP tool client

| Item | Selected value |
|---|---|
| Supported | NO |
| Scope | NOT SUPPORTED |
| Stable public command | NOT SUPPORTED |
| Bundled helper command | NOT SUPPORTED |
| Supported transports | NOT SUPPORTED |
| Negotiation and compatibility behavior | NOT SUPPORTED; test code is evidence only and is not a bundled public client. |
| Invocation scope | NOT SUPPORTED |
| Interaction modes | NOT SUPPORTED |
| Server-information command | NOT SUPPORTED |
| Tool-list command | NOT SUPPORTED |
| Tool-show command | NOT SUPPORTED |
| Single tool-call command | NOT SUPPORTED |
| Sequential tool-run command | NOT SUPPORTED |
| Pagination request policy | NOT SUPPORTED |
| Lossless tool-list page format | NOT SUPPORTED |
| Flattened inventory presentation | NOT SUPPORTED |
| Page-level cache-hint policy | NOT SUPPORTED |
| Lossless call-result mode | NOT SUPPORTED |
| Other presentation output modes | NOT SUPPORTED |
| Modern MRTR policy | NOT SUPPORTED by the fixture's single bounded tool |
| Initialization-era elicitation policy | NOT SUPPORTED |
| Non-interactive policy | NOT SUPPORTED |
| Timeout and cancellation policy | NOT SUPPORTED |
| Task or extension support | NOT SUPPORTED |
| Roots/workspace policy | NOT SUPPORTED; the fixture has no workspace capability and does not advertise deprecated Roots. |
| Exit-code mapping | NOT SUPPORTED |

## Optional human verification Web interface deployment

| Item | Selected value |
|---|---|
| Supported | NO |
| Web runtime or entry point | NOT SUPPORTED |
| Deployment selection time | NOT SUPPORTED |
| Supported topologies | NOT SUPPORTED |
| Default topology | NOT SUPPORTED |
| Shared-listener support | NO |
| Separate-listener support | NO |
| External-origin model | NOT SUPPORTED |
| Browser-visible MCP exposure capability | not supported |
| Enablement configuration | NOT SUPPORTED |

## Headless service deployment

| Item | Selected value |
|---|---|
| Supported | NO |
| Service runtime or entry point | NOT SUPPORTED |
| Protocol or API surface | NOT SUPPORTED |
| Endpoint or listener model | NOT SUPPORTED |
| Default bind address | NOT SUPPORTED |
| Port policy | NOT SUPPORTED |
| Authentication | NOT SUPPORTED |
| Authorization | NOT SUPPORTED |
| Exposure and non-loopback policy | NOT SUPPORTED |
| Request size and rate limits | NOT SUPPORTED |
| Concurrent request policy | NOT SUPPORTED |
| State or session model | NOT SUPPORTED |
| Readiness check | NOT SUPPORTED |
| Liveness check | NOT SUPPORTED |
| Timeout and cancellation policy | NOT SUPPORTED |
| Graceful shutdown and restart policy | NOT SUPPORTED |
| Deployment topology | NOT SUPPORTED |
| Security and deployment smoke tests | NOT SUPPORTED |

## Distribution

| Item | Selected value |
|---|---|
| Skill distribution | Repository fixture copied only for maintainer validation; not separately published. |
| CLI distribution | NOT APPLICABLE |
| MCP distribution | Bundled stdio server files with the concrete Skill fixture. |
| Human Web interface distribution | not supported |
| Service integration | none |
| Version source of truth | `package.json` fixture version and exact dependency pins. |

## Environment and configuration

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| NONE | NO | The representative Modern stdio fixture requires no environment variables. | NO |

## Decision rationale

The representative evidence is intentionally stdio-only so the MCP core revision can be tested without listener, authentication, CORS, or deployment concerns. The official TypeScript MCP SDK 2.0.0 is selected because its published Modern serving entry points explicitly support `2026-07-28`; `serveStdio(..., { legacy: "reject" })` prevents the SDK's compatibility defaults from reintroducing the unpublished Legacy era. Streamable HTTP remains available to concrete Skills through the template contract but is not claimed by this fixture. Tests exercise actual SDK discovery and tool calls and raw negative openings rather than treating a revision string in documentation as conformance evidence.
