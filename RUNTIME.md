# Runtime decision record

Complete this file before implementing a concrete skill. This is the authoritative index of toolchain, command, and transport choices.

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
| Invoke MCP ad hoc over stdio | TODO or NOT SUPPORTED |
| Start local Streamable HTTP MCP server | TODO or NOT SUPPORTED |
| Stop local Streamable HTTP MCP server | TODO or NOT SUPPORTED |
| Invoke MCP over Streamable HTTP | TODO or NOT SUPPORTED |
| Check local MCP readiness | TODO or NOT SUPPORTED |
| Test | TODO |
| Lint/static analysis | TODO |
| Format check | TODO |
| Build/package | TODO or NOT APPLICABLE |

## MCP variants

Use standard MCP transport names. Do not describe a raw socket protocol as “TCP MCP” unless the project intentionally implements a non-standard custom transport. A standalone local MCP server should normally use Streamable HTTP over a loopback TCP socket.

### stdio variant

| Item | Selected value |
|---|---|
| Supported | TODO: YES or NO |
| Server entry point | TODO or NOT SUPPORTED |
| Lifecycle owner | MCP host / bundled client / other: TODO |
| Expected session scope | one operation / multiple operations: TODO |
| Startup cost policy | TODO |
| Shutdown behavior | TODO |

### Local Streamable HTTP variant

| Item | Selected value |
|---|---|
| Supported | TODO: YES or NO |
| Server entry point | TODO or NOT SUPPORTED |
| Endpoint path | TODO, normally `/mcp` |
| Default bind address | TODO, normally `127.0.0.1` or `::1` |
| Port | TODO: fixed, configurable, or dynamically assigned |
| Session mode | TODO: stateless or stateful |
| Concurrent-client policy | TODO |
| Authentication | TODO |
| Host-header validation | TODO |
| Allowed origins | TODO |
| Readiness check | TODO |
| Shutdown/restart policy | TODO |
| Non-loopback support | TODO: NO or documented security design |

The stdio and Streamable HTTP variants must expose the same domain operations unless a documented protocol limitation prevents exact parity.

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

Explain why the selected runtime, package manager, CLI interface, and MCP variants fit this skill better than the credible alternatives.

Explain separately:

1. why stdio is or is not supported;
2. why a standalone local Streamable HTTP server is or is not supported;
3. whether the local server is loopback-only;
4. how both variants share implementation and tests.

TODO