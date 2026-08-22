# Implementation runtime decision record

This contract is materialized by `capability.runtime`. Here, **implementation runtime** means the implementation ecosystem and operational choices used to build and run the composed artifact, including its language/runtime, dependency workflow, exact commands, environment, distribution, and deployment. Complete this record when the artifact needs maintained implementation, packaging, public commands, network listeners, services, or deployment authority.

Caller-visible behavior belongs in the applicable interface contract (`CLI_INTERFACE.md`, `MCP_INTERFACE.md`, `WEB_INTERFACE.md`, or `SERVICE_INTERFACE.md`). This file owns implementation-runtime choices, exact commands, dependency/package choices, protocol and transport selections, environment, and deployment lifecycle.

## Status

```text
Selection status: UNSELECTED
```

Change the status to `SELECTED` only after the common fields and every section activated by the selected composition capabilities are concrete.

## Capability applicability

| Section | Activated by |
|---|---|
| Primary implementation | `capability.runtime` |
| Shared development commands | `capability.runtime` |
| Packaged CLI commands | `capability.cli` |
| MCP commands and protocol selections | `capability.mcp` |
| Standalone Web deployment | `capability.web-interface` |
| Headless service deployment | `capability.service` |
| Environment and rationale | `capability.runtime` |

A product may select `capability.runtime` directly without selecting a public interface, for example when private helpers need a maintained implementation runtime decision record.

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

Select one implementation ecosystem actually used by the artifact. Use `NONE` or `NOT APPLICABLE` only when absence is semantically valid; do not add competing manifests or lockfiles for unused runtimes.

## Commands

Every command must state or imply an exact working directory. Rows for unselected capabilities may remain `NOT APPLICABLE` or `NOT SUPPORTED`; selected capabilities require concrete commands or an explicit statement that an operation is externally managed.

### Shared development commands

| Purpose | Exact command |
|---|---|
| Install development dependencies | TODO |
| Run in place | TODO |
| Test | TODO |
| Lint/static analysis | TODO |
| Format check | TODO |
| Build/package | TODO or NOT APPLICABLE |

### Packaged CLI

| Purpose | Exact command |
|---|---|
| Human/agent CLI | TODO or NOT APPLICABLE |

The canonical command must agree with `CLI_INTERFACE.md`.

### MCP

| Purpose | Exact command |
|---|---|
| Start stdio MCP server | TODO or NOT SUPPORTED |
| Start Streamable HTTP MCP server | TODO or NOT SUPPORTED |
| Stop Streamable HTTP MCP server | TODO or NOT SUPPORTED |
| Check MCP readiness | TODO or NOT SUPPORTED |

Public protocol behavior belongs in `MCP_INTERFACE.md`.

### Standalone Web interface

| Purpose | Exact command |
|---|---|
| Start Web interface | TODO or NOT SUPPORTED |
| Stop Web interface | TODO or NOT SUPPORTED |
| Check Web readiness | TODO or NOT SUPPORTED |

### Headless service

| Purpose | Exact command |
|---|---|
| Start service | TODO or NOT SUPPORTED |
| Stop service | TODO or NOT SUPPORTED |
| Check readiness | TODO or NOT SUPPORTED |
| Check liveness | TODO or NOT SUPPORTED |

## MCP protocol support

Complete this section only when `capability.mcp` is selected. The composition baseline uses MCP `2026-07-28` as its core protocol baseline. Verify the selected SDK against the applicable official specification before finalizing the concrete record.

| Item | Selected value |
|---|---|
| Supported protocol revisions | `2026-07-28` |
| Default revision/negotiation mode | TODO |
| MCP SDK or protocol library | TODO |
| SDK version | TODO |
| JSON Schema dialects | TODO; support JSON Schema 2020-12 where required |
| Optional MCP extensions | TODO or NONE |
| Negotiation/conformance tests | TODO |

Record extension identifiers separately from the core protocol revision. `capability.mcp-apps` owns the MCP Apps extension contract when selected.

### stdio variant

| Item | Selected value |
|---|---|
| Supported | TODO: YES or NO |
| Server entry point | TODO or NOT SUPPORTED |
| Lifecycle owner | TODO |
| Startup cost policy | TODO |
| Cancellation behavior | TODO |
| Child-process shutdown and escalation | TODO |

When supported, stdout is protocol-only, diagnostics use stderr, the launcher is bounded, and shutdown is deterministic.

### Streamable HTTP variant

| Item | Selected value |
|---|---|
| Supported | TODO: YES or NO |
| Server entry point | TODO or NOT SUPPORTED |
| Endpoint path | TODO, normally `/mcp` |
| Default bind address | TODO |
| Port | TODO |
| Authentication | TODO |
| Host-header validation | TODO |
| Origin validation | TODO: every HTTP request before dispatch |
| Allowed origins and absent-Origin policy | TODO |
| Request size/rate limits | TODO |
| Readiness check | TODO |
| Cancellation behavior | TODO |
| Shutdown/restart policy | TODO |
| Non-loopback support | TODO |

Security decisions are request-scoped. A valid first request must not authorize later requests on the same reused connection.

## Standalone Web deployment

Complete when `capability.web-interface` is selected. `WEB_INTERFACE.md` owns browser-visible behavior.

| Item | Selected value |
|---|---|
| Web runtime or entry point | TODO |
| Deployment selection time | TODO |
| Supported topologies | TODO |
| Default topology | TODO or NONE |
| Shared-listener support | TODO |
| Separate-listener support | TODO |
| External-origin model | TODO |
| Enablement configuration | TODO |

Logical routing, authentication, authorization, health, and failure boundaries remain explicit even when interfaces share a process, listener, container, or external origin.

## Headless service deployment

Complete when `capability.service` is selected. `SERVICE_INTERFACE.md` owns caller-visible service behavior.

| Item | Selected value |
|---|---|
| Service runtime or entry point | TODO |
| Endpoint/listener model | TODO |
| Default bind address | TODO |
| Port policy | TODO |
| Deployment topology | TODO |
| Process ownership | TODO |
| Graceful shutdown/restart policy | TODO |

## Distribution

| Item | Selected value |
|---|---|
| Runtime distribution | TODO |
| CLI distribution | TODO or NOT APPLICABLE |
| MCP distribution | TODO or NOT APPLICABLE |
| Web interface distribution | TODO or NOT APPLICABLE |
| Service integration | TODO or NOT APPLICABLE |
| Version source of truth | TODO |

## Environment and configuration

Document required environment variables without committing secrets.

| Variable | Required | Purpose | Secret |
|---|---:|---|---:|
| TODO | TODO | TODO | TODO |

Network-server configuration should normally permit explicit bind address, port, endpoint path, authentication material location, log level, and optional interface enablement. Avoid secrets in command-line arguments when a safer mechanism exists.

## Decision rationale

Explain why the selected runtime, dependency workflow, commands, interface capabilities, distribution, and deployment choices fit the artifact. When multiple interfaces expose the same operation, explain how adapters share implementation and how tests establish semantic equivalence.

TODO
