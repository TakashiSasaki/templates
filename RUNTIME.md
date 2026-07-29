# Runtime decision record

Complete this file before implementing a concrete skill. This is the authoritative index of toolchain, command, protocol, and transport choices.

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

The template does not select a protocol revision. A concrete skill must verify the current MCP specification and the selected SDK before completing this section. Do not treat a draft or release candidate as a universal baseline.

| Item | Selected value |
|---|---|
| Supported protocol revisions | TODO |
| Default revision or negotiation mode | TODO: automatic negotiation / fixed revision / other |
| MCP SDK or protocol library | TODO |
| SDK version | TODO |
| Legacy compatibility policy | TODO |
| Optional MCP extensions | TODO or NONE |

Protocol lifecycle, cancellation, interaction, subscriptions, logging, and task behavior can differ between revisions. Prefer an SDK-supported negotiation path over handwritten version probing. Tests must cover every revision the concrete skill claims to support.

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
| Startup cost policy | TODO |
| Cancellation behavior | TODO |
| Shutdown behavior | TODO |

### Local Streamable HTTP variant

| Item | Selected value |
|---|---|
| Supported | TODO: YES or NO |
| Server entry point | TODO or NOT SUPPORTED |
| Endpoint path | TODO, normally `/mcp` |
| Default bind address | TODO, normally `127.0.0.1` or `::1` |
| Port | TODO: fixed, configurable, or dynamically assigned |
| Protocol state model | TODO: revision-dependent; do not infer from transport alone |
| Concurrent-client policy | TODO |
| Authentication | TODO |
| Host-header validation | TODO |
| Allowed origins | TODO |
| Readiness check | TODO |
| Cancellation behavior | TODO |
| Shutdown/restart policy | TODO |
| Non-loopback support | TODO: NO or documented security design |

The stdio and Streamable HTTP variants must expose the same domain operations unless a documented protocol limitation prevents exact parity.

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
| Pagination policy | TODO: normally retrieve all pages using opaque cursors |
| Output modes | TODO: include a lossless MCP JSON mode |
| Interaction policy | non-interactive / interactive / response file: TODO |
| Timeout and cancellation policy | TODO |
| Task or extension support | TODO or NOT SUPPORTED |
| Roots/workspace policy | TODO: distinguish MCP roots from skill-specific workspace configuration |

The client command-line syntax is local to this skill. MCP standardizes protocol behavior, not names such as `tools show`, `tools run`, `--arguments-file`, or `--output`.

A tools-only client must preserve standard tool result fields such as `content`, `structuredContent`, `isError`, and `_meta` when present. It must distinguish JSON-RPC or transport failures from successful `tools/call` responses whose tool result reports `isError: true`.

Do not expose an arbitrary server command, shell command, or user-selected JSON-RPC request ID merely for convenience. The bundled stdio server launcher should be fixed or selected from trusted configuration. Generic workspace restrictions should be implemented through documented MCP capabilities, server configuration, or explicit tool arguments rather than an invented universal MCP `--workspace` option.

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

Explain why the selected runtime, package manager, CLI interface, MCP variants, supported protocol revisions, and optional client features fit this skill better than the credible alternatives.

Explain separately:

1. why stdio is or is not supported;
2. why a standalone local Streamable HTTP server is or is not supported;
3. whether the local server is loopback-only;
4. whether the bundled client is tools-only or broader in scope;
5. how protocol revisions are negotiated and tested;
6. how cancellation and additional-input requests are handled;
7. how all adapters share implementation and tests.

TODO
