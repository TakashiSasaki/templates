# Runtime decision record

Retain and complete this file when the selected profile needs a maintained runtime, command, package, service, or deployment authority. It is required for `packaged-cli`, `mcp-enabled`, `browser-interface`, and `headless-service`, and optional for `script-assisted` when helper-runtime decisions need a separate record.

Caller-visible CLI behavior belongs in `CLI_INTERFACE.md`; caller-visible MCP behavior belongs in `MCP_INTERFACE.md`; browser-visible behavior belongs in `WEB_INTERFACE.md`. This file remains authoritative for implementation runtime, exact commands, package and distribution choices, protocol and transport selections, and deployment lifecycle.

## Status

```text
Selection status: UNSELECTED
```

Change the status to `SELECTED` only after completing the common fields and every section activated by `Selected profiles:`. Unselected profile sections may retain template guidance. A selected section must contain no unresolved `TODO` or `UNSELECTED` values.

## Profile applicability

| Section | Activated by |
|---|---|
| Primary implementation | every retained runtime record |
| Shared development commands | every retained runtime record |
| Packaged CLI commands and distribution | `packaged-cli` |
| MCP protocol and variants | `mcp-enabled` |
| Web deployment | `browser-interface` |
| Headless service deployment | `headless-service` |
| Environment and rationale | every retained runtime record |

A `script-assisted` skill may retain only the common runtime identity, applicable shared commands, environment, distribution, and rationale. It does not need to resolve packaged CLI, MCP, browser, or service fields.

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

Select one implementation ecosystem actually used by the skill. Use an explicit value such as `NONE` or `NOT APPLICABLE` only when absence is semantically valid; do not add competing manifests or lockfiles for unused runtimes.

## Commands

Every command must state or imply an exact working directory. Rows activated by an unselected profile may remain `NOT APPLICABLE` or `NOT SUPPORTED`; rows activated by a selected profile must be concrete.

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | TODO |
| Run in place | TODO |
| Agent launcher | TODO or NOT APPLICABLE |
| Test | TODO |
| Lint/static analysis | TODO |
| Format check | TODO |
| Build/package | TODO or NOT APPLICABLE |

### Packaged CLI commands

Complete only when `packaged-cli` is selected. The canonical command must agree with `CLI_INTERFACE.md`.

| Purpose | Exact command |
|---|---|
| Human CLI | TODO or NOT APPLICABLE |

### MCP commands

Complete only when `mcp-enabled` is selected. Public behavior and compatibility remain in `MCP_INTERFACE.md`.

| Purpose | Exact command |
|---|---|
| Start stdio MCP server | TODO or NOT SUPPORTED |
| Inspect MCP server and tool inventory | TODO or NOT SUPPORTED |
| Invoke one MCP tool over stdio | TODO or NOT SUPPORTED |
| Invoke sequential MCP tool calls over stdio | TODO or NOT SUPPORTED |
| Start Streamable HTTP MCP server | TODO or NOT SUPPORTED |
| Stop Streamable HTTP MCP server | TODO or NOT SUPPORTED |
| Invoke one MCP tool over Streamable HTTP | TODO or NOT SUPPORTED |
| Invoke sequential MCP tool calls over Streamable HTTP | TODO or NOT SUPPORTED |
| Check MCP readiness | TODO or NOT SUPPORTED |

### Browser-interface commands

| Purpose | Exact command |
|---|---|
| Start human verification Web UI | TODO or NOT SUPPORTED |
| Stop human verification Web UI | TODO or NOT SUPPORTED |
| Check human verification Web UI readiness | TODO or NOT SUPPORTED |

### Headless-service commands

| Purpose | Exact command |
|---|---|
| Start headless service | TODO or NOT SUPPORTED |
| Stop headless service | TODO or NOT SUPPORTED |
| Check headless service readiness | TODO or NOT SUPPORTED |

## MCP protocol support

Complete this section only when `mcp-enabled` is selected. This unpublished template uses **MCP `2026-07-28` as its only core protocol baseline**. Do not select an earlier revision, a dual-era mode, or automatic fallback to initialization-based protocol revisions. Verify the current official MCP specification and the selected SDK before completing the record.

| Item | Selected value |
|---|---|
| Supported protocol revisions | `2026-07-28` |
| Supported protocol eras | `modern` |
| Default revision or negotiation mode | TODO: fixed or pinned `2026-07-28`; no Legacy fallback |
| MCP SDK or protocol library | TODO |
| SDK version | TODO |
| Legacy compatibility policy | `NOT SUPPORTED` |
| JSON Schema dialects | TODO; MUST support JSON Schema 2020-12 where the selected MCP surface requires it |
| Optional MCP extensions | TODO or NONE; extension revisions are recorded separately when an extension contract is retained |
| Deprecated feature policy | TODO; new implementations must not advertise deprecated MCP features by default |
| Negotiation and compatibility tests | TODO; MUST prove Modern-only discovery, revision rejection, and every claimed transport |

The initial template baseline intentionally has no compatibility promise for MCP revisions `2025-11-25` and earlier. A concrete skill must not reintroduce the Legacy `initialize` / `notifications/initialized` lifecycle, protocol-level HTTP sessions, or automatic era fallback without first changing this template contract and its conformance validator.

For Modern requests, the selected implementation must follow the official `2026-07-28` per-request metadata model. Servers implement `server/discover`; clients may use it before ordinary calls, and an unsupported requested revision is answered with `UnsupportedProtocolVersionError`. Capabilities and optional extensions are request-scoped rather than established by an initialization session.

## MCP variants

Use standard MCP transport names. Do not describe a raw socket protocol as “TCP MCP” unless the project intentionally implements a non-standard custom transport.

### stdio variant

| Item | Selected value |
|---|---|
| Supported | TODO: YES or NO |
| Server entry point | TODO or NOT SUPPORTED |
| Lifecycle owner | MCP host / bundled tool client / other: TODO |
| Invocation scope | one operation / multiple sequential operations: TODO |
| Protocol negotiation/discovery | TODO; when supported use `server/discover` and `2026-07-28` Modern semantics without Legacy fallback |
| Request metadata behavior | TODO; describe per-request protocol version, client capabilities, and applicable identity metadata |
| Startup cost policy | TODO |
| Cancellation behavior | TODO |
| Child-process shutdown and escalation | TODO |

When supported, stdout is protocol-only, diagnostics use stderr, the launcher is trusted and bounded, and shutdown escalation is deterministic. A Modern-only stdio implementation must reject Legacy openings rather than silently entering an initialization session.

### Streamable HTTP variant

| Item | Selected value |
|---|---|
| Supported | TODO: YES or NO |
| Server entry point | TODO or NOT SUPPORTED |
| Endpoint path | TODO, normally `/mcp` |
| Default bind address | TODO, normally `127.0.0.1` or `::1` for local-only use |
| Port | TODO: fixed, configurable, dynamically assigned, shared listener, or deployment-selected |
| Supported protocol eras | TODO: `modern` when supported |
| Revision-specific state model | TODO; Modern `2026-07-28` has no protocol-level sessions and request state is request-scoped or application-owned |
| Concurrent-client policy | TODO |
| Authentication | TODO |
| Host-header validation | TODO: every HTTP request before dispatch |
| Origin validation granularity | TODO: EVERY HTTP REQUEST before dispatch; never connection-scoped |
| Allowed origins and absent-Origin policy | TODO |
| Connection-reuse security tests | TODO: keep-alive or multiplexed requests with different Origin values |
| Readiness check | TODO |
| Cancellation behavior | TODO |
| Shutdown/restart policy | TODO |
| Non-loopback support | TODO: NO or documented security design |

Host, Origin, authentication, authorization, size-limit, and protocol-header decisions are request-scoped. A valid first request must not authorize later requests on the same keep-alive or multiplexed connection. Every present disallowed Origin must produce HTTP 403 for that request.

When Streamable HTTP is supported, complete every Modern requirement below:

| Modern Streamable HTTP requirement | Selected behavior |
|---|---|
| POST request model | TODO: one JSON-RPC client message per new POST |
| `Accept: application/json, text/event-stream` | TODO |
| `MCP-Protocol-Version` and request `_meta` consistency | TODO |
| Required `Mcp-Method` and conditional `Mcp-Name` headers | TODO |
| Header value encoding | TODO |
| `x-mcp-header` validation and `Mcp-Param-*` emission | TODO or NOT APPLICABLE when the implementation is server-only and never acts as an HTTP MCP client |
| JSON and request-scoped SSE response handling | TODO |
| SSE-stream cancellation | TODO: closing the response stream cancels that request and no further messages are sent |
| `Mcp-Session-Id`, GET, DELETE, and resumability | TODO: `NOT USED` in the Modern baseline |
| Initialization-era fallback on the same endpoint | `NOT SUPPORTED` when selected |

The Modern MCP endpoint accepts POST; it does not expose the old standalone GET stream or protocol-session DELETE semantics. Resumable SSE via `Last-Event-ID` is not supported. Long-lived change notifications, when selected, use `subscriptions/listen` rather than a general GET stream.

The stdio and Streamable HTTP variants must expose equivalent domain operations under the same revision, identity, authorization, configuration, and workspace policy unless a documented transport limitation prevents parity.

### Bundled ad hoc MCP tool client

Complete this section only when the skill bundles a command that discovers or invokes MCP tools.

| Item | Selected value |
|---|---|
| Supported | TODO: YES or NO |
| Scope | tools only / broader MCP client: TODO |
| Stable public command | TODO or NOT SUPPORTED |
| Bundled helper command | TODO or NOT SUPPORTED |
| Supported transports | stdio / Streamable HTTP / both: TODO |
| Negotiation and compatibility behavior | TODO; pin or otherwise require Modern `2026-07-28` with no Legacy fallback |
| Invocation scope | one tool call / multiple sequential tool calls: TODO |
| Interaction modes | non-interactive / interactive / response file: TODO |
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
| Initialization-era elicitation policy | `NOT SUPPORTED` when selected |
| Non-interactive policy | TODO |
| Timeout and cancellation policy | TODO |
| Task or extension support | TODO or NOT SUPPORTED |
| Roots/workspace policy | TODO: do not adopt deprecated Roots for new implementations; distinguish skill workspace configuration from MCP capabilities |
| Exit-code mapping | TODO; keep consistent with `MCP_INTERFACE.md` and `CLI_INTERFACE.md` when both apply |

The bundled launcher must not expose arbitrary shell commands or caller-selected JSON-RPC request IDs. Preserve every raw `tools/list` page and complete tool-call result in lossless modes; flattened views are derived presentations.

## Optional human verification Web interface deployment

Complete this section when `browser-interface` is selected. This section is the sole source of truth for process, listener, port, container, service, gateway, external-origin, and deployment-selection capabilities. `WEB_INTERFACE.md` defines browser-visible behavior.

| Item | Selected value |
|---|---|
| Supported | TODO: YES or NO |
| Web runtime or entry point | TODO or NOT SUPPORTED |
| Deployment selection time | build / installation / startup / deployment: TODO |
| Supported topologies | same process and listener / same process separate listener / same container separate process / sidecar / separate service / reverse-proxied combination: TODO |
| Default topology | TODO or NONE; may remain deployment-selected |
| Shared-listener support | YES / NO / TODO |
| Separate-listener support | YES / NO / TODO |
| External-origin model | same origin / separate origin / deployment-selected: TODO |
| Browser-visible MCP exposure capability | direct / backend-only / deployment-selected / not supported: TODO |
| Enablement configuration | TODO |

The final deployment topology may remain deployment-selected, but routing, authentication, authorization, health checks, and failure boundaries remain explicit. Disabling a debug UI must avoid loading UI-only assets or state on non-UI startup paths.

## Headless service deployment

Complete this section when `headless-service` is selected. It applies to an independently reachable non-browser service, whether or not that service also exposes MCP.

| Item | Selected value |
|---|---|
| Supported | TODO: YES or NO |
| Service runtime or entry point | TODO |
| Protocol or API surface | TODO |
| Endpoint or listener model | TODO |
| Default bind address | TODO |
| Port policy | TODO |
| Authentication | TODO |
| Authorization | TODO |
| Exposure and non-loopback policy | TODO |
| Request size and rate limits | TODO |
| Concurrent request policy | TODO |
| State or session model | TODO |
| Readiness check | TODO |
| Liveness check | TODO |
| Timeout and cancellation policy | TODO |
| Graceful shutdown and restart policy | TODO |
| Deployment topology | same process / same container / sidecar / separate service / orchestrated deployment / other: TODO |
| Security and deployment smoke tests | TODO |

Define how another node reaches the service, which identities may invoke it, how readiness differs from liveness, how in-flight requests terminate during shutdown, and which tests establish those guarantees.

## Distribution

Resolve the common rows for every retained runtime record and the profile-specific rows activated by `Selected profiles:`.

| Item | Selected value |
|---|---|
| Skill distribution | Git clone / submodule / release archive / other: TODO |
| CLI distribution | TODO or NOT APPLICABLE |
| MCP distribution | bundled / separate package / not supported: TODO |
| Human Web interface distribution | same artifact / optional artifact / separate artifact / not supported: TODO |
| Service integration | none / systemd / launchd / Windows service / container / orchestrator / other: TODO |
| Version source of truth | TODO |

## Environment and configuration

Document required environment variables without placing secrets in this repository. Replace the example row with concrete variables or an explicit `NONE` record.

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| TODO | TODO | TODO | TODO |

Network-server configuration should normally permit explicit bind address, port, endpoint path, authentication material location, log level, and optional Web-interface enablement. Secret values must not be committed or passed through public process listings when a safer mechanism exists.

## Decision rationale

Explain why the selected runtime, package manager, commands, public-interface support, MCP transport variants, distribution, and deployment choices fit this skill better than credible alternatives. For MCP-enabled skills, explain the choice of an SDK that explicitly supports the `2026-07-28` Modern protocol and how tests prove the Modern-only posture. Address only activated profiles, but include how adapters share implementation and tests when several interfaces expose the same operations.

TODO
