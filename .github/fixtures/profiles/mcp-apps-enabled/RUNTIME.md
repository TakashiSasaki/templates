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
| Lockfile policy | The fixture pins every direct dependency exactly in `package.json`; maintainer CI installs from the public npm registry and does not publish this fixture as a package. |
| Source layout | `src/text_stats.mjs` owns deterministic domain logic; `mcp/server.mjs` owns the Modern MCP adapter and Apps resources; `mcp/apps/result.html` is the View; `mcp/apps/host_bridge.mjs` is source-only Host/bridge protocol evidence; `tests/test_mcp_apps.mjs` owns executable protocol evidence. |
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
| Inspect MCP server and tool inventory | `node --test --test-name-pattern="Modern discovery" tests/test_mcp_apps.mjs` |
| Invoke one MCP tool over stdio | `node --test --test-name-pattern="core tool result" tests/test_mcp_apps.mjs` |
| Invoke sequential MCP tool calls over stdio | `npm test` |
| Start Streamable HTTP MCP server | NOT SUPPORTED |
| Stop Streamable HTTP MCP server | NOT SUPPORTED |
| Invoke one MCP tool over Streamable HTTP | NOT SUPPORTED |
| Invoke sequential MCP tool calls over Streamable HTTP | NOT SUPPORTED |
| Check MCP readiness | NOT SUPPORTED; stdio readiness is established by successful Modern discovery, extension advertisement, resource reads, and tool calls. |

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
| Default revision or negotiation mode | Fixed/pinned `2026-07-28`; the official SDK test clients use `versionNegotiation.mode.pin` and the server uses `legacy: "reject"`; no Legacy fallback occurs. |
| MCP SDK or protocol library | Official TypeScript MCP SDK split packages `@modelcontextprotocol/server` and `@modelcontextprotocol/client`; MCP Apps stable wire semantics are validated directly against the `2026-01-26` extension contract rather than coupling core SDK v2 to the currently older Apps helper package. |
| SDK version | `2.0.0` for core server/client packages |
| Legacy compatibility policy | NOT SUPPORTED; initialization-based revisions are not served. |
| JSON Schema dialects | JSON Schema 2020-12-compatible schemas through Zod 4 and the official SDK schema path. |
| Optional MCP extensions | io.modelcontextprotocol/ui |
| Deprecated feature policy | Deprecated Roots, Sampling, Logging, and HTTP+SSE are not advertised or implemented. |
| Negotiation and compatibility tests | `tests/test_mcp_apps.mjs` proves Modern pinned discovery, server extension advertisement, Apps-capable and core-only Host behavior, UI resource metadata, tool linkage/visibility, bridge lifecycle, and core fallback. |

The exact MCP Apps extension revision is authoritative in `MCP_APPS.md`, not in the core protocol revision field.

## MCP variants

### stdio variant

| Item | Selected value |
|---|---|
| Supported | YES |
| Server entry point | `mcp/server.mjs` |
| Lifecycle owner | MCP host or maintainer test client's `StdioClientTransport` |
| Invocation scope | Multiple sequential Modern requests may share one stdio connection; Apps View lifecycle remains a separate Host↔View bridge. |
| Protocol negotiation/discovery | `server/discover` selects `2026-07-28` and advertises `io.modelcontextprotocol/ui`; clients pin `2026-07-28`; `serveStdio(..., { legacy: "reject" })` rejects Legacy openings. |
| Request metadata behavior | The official core SDK sends and validates Modern protocol-version/client-capability metadata; Apps-capable tests advertise `extensions.io.modelcontextprotocol/ui.mimeTypes`. |
| Startup cost policy | Start one trusted Node.js child process when the Host activates the Skill and reuse it for bounded calls. |
| Cancellation behavior | The official stdio transport owns core cancellation; closing the client closes the child transport. The simulated Apps bridge has no detached work. |
| Child-process shutdown and escalation | `StdioClientTransport.close()` closes the spawned child; tests always close clients. |

### Streamable HTTP variant

| Item | Selected value |
|---|---|
| Supported | NO |
| Server entry point | NOT SUPPORTED |
| Endpoint path | NOT SUPPORTED |
| Default bind address | NOT SUPPORTED |
| Port | NOT SUPPORTED |
| Supported protocol eras | NOT SUPPORTED |
| Revision-specific state model | NOT SUPPORTED; the fixture opens no HTTP MCP endpoint. |
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
| Negotiation and compatibility behavior | NOT SUPPORTED; test clients and Host bridge simulation are maintainer evidence only. |
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
| Modern MRTR policy | NOT SUPPORTED by these bounded tools |
| Initialization-era elicitation policy | NOT SUPPORTED |
| Non-interactive policy | NOT SUPPORTED |
| Timeout and cancellation policy | NOT SUPPORTED |
| Task or extension support | MCP Apps `io.modelcontextprotocol/ui` only; exact Apps behavior is in `MCP_APPS.md`. |
| Roots/workspace policy | NOT SUPPORTED; no workspace capability and no deprecated Roots. |
| Exit-code mapping | NOT SUPPORTED |

## Optional human verification Web interface deployment

| Item | Selected value |
|---|---|
| Supported | NO |
| Web runtime or entry point | NOT SUPPORTED; the Host-embedded MCP App is not a standalone browser interface. |
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
| MCP distribution | Bundled stdio MCP server plus bundled `ui://` App resource. |
| Human Web interface distribution | not supported; MCP Apps is Host-embedded. |
| Service integration | none |
| Version source of truth | `package.json` fixture version and the protocol/extension contracts. |

## Environment and configuration

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| NONE | NO | The Apps fixture requires no environment variables, network origins, or credentials. | NO |

## Decision rationale

This fixture adds exactly one optional extension to the Modern stdio baseline. The official TypeScript core SDK 2.0.0 provides `2026-07-28` discovery, extension capability advertisement, tools, resources, and stdio transport. Apps `2026-01-26` resource/tool metadata and View↔Host lifecycle are validated directly from the stable extension specification so core and extension revisions remain independent. No standalone Web profile is selected, no network listener is opened, and the core `text_stats` result remains useful to Hosts that do not advertise MCP Apps.
