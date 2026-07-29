# MCP transport variants and bundled tool clients

This template supports two standard MCP deployment variants that share one server implementation. It may also include a bounded ad hoc MCP tool client that drives those variants through standard MCP methods.

## Terminology

Use these names consistently:

- **stdio MCP server:** a client launches the server as a child process and communicates through stdin/stdout;
- **local Streamable HTTP MCP server:** an independently managed process listens on a loopback TCP socket and exposes an HTTP MCP endpoint;
- **ad hoc MCP tool client:** a bundled command that discovers and invokes MCP tools without pretending to be a complete native MCP host.

Do not call the second variant a raw TCP MCP transport. TCP is the underlying network protocol, while Streamable HTTP is the standard MCP transport presented to clients.

Do not call a tools-only command a complete MCP client when it does not implement resources, prompts, completion, subscriptions, tasks, sampling, elicitation, roots, or other negotiated features.

## Protocol revisions

Transport choice and protocol revision are separate decisions. A concrete skill must declare:

- the exact protocol revisions it supports;
- whether the selected SDK performs automatic negotiation;
- which lifecycle or discovery exchange applies to each revision;
- which optional core features or extensions are implemented;
- how cancellation and additional-input requests are handled;
- how each supported revision is tested.

Do not hardcode a draft or release candidate as a universal baseline. For example, initialize-era revisions such as `2025-11-25` use an initialization handshake and may use protocol-level session behavior, while newer revisions may use different discovery and stateless request semantics. Prefer the official SDK's version-negotiation path instead of reproducing negotiation logic by hand.

## Decision matrix

| Requirement | Preferred variant |
|---|---|
| Skill needs MCP only during one workflow | stdio |
| No listening socket should remain open | stdio |
| Server lifetime should follow one client | stdio |
| Several local clients need one endpoint | Streamable HTTP |
| Server keeps reusable caches or resources | Streamable HTTP, with a documented state model that is valid for the selected revision |
| Native host is already configured for a child process | stdio |
| Native host connects by URL | Streamable HTTP |
| Broader network deployment | Streamable HTTP with a separate security design |

A concrete skill may support both. Supporting both does not justify duplicate tool implementations.

## Shared composition

The preferred server implementation shape is:

```text
createServer / registerOperations
            |
            +--> serve over stdio
            +--> serve over Streamable HTTP
            +--> drive through test transport
```

The shared server layer owns:

- tool, resource, and prompt definitions that the concrete skill actually supports;
- input and output schemas;
- application calls;
- workspace and authorization decisions that are independent of transport;
- structured error mapping.

Transport entry points own only protocol-binding, transport, and lifecycle concerns.

The bundled tool client is separate from this server composition root:

```text
agent or human
      |
      +--> bundled MCP tool client
                    |
                    +--> stdio MCP server
                    +--> existing Streamable HTTP endpoint
```

The client must exercise the actual MCP path. It must not bypass MCP and call the application layer directly while presenting the result as an MCP invocation.

## stdio lifecycle

The stdio client or host:

1. starts the trusted server process;
2. performs the lifecycle, discovery, or negotiation exchange required by the selected protocol revision;
3. invokes one or more independent MCP operations;
4. handles revision-supported additional-input, task, notification, and cancellation behavior;
5. closes stdin or the connection according to the SDK contract;
6. waits for the server process to exit and escalates only according to a documented shutdown timeout.

The server must not daemonize or retain a listener after the client invocation ends. Stdout contains only valid MCP protocol messages. Stderr may contain diagnostics and must not be interpreted as an automatic operation failure.

## Local Streamable HTTP lifecycle

The local network server:

1. starts independently of a particular MCP request;
2. binds to a documented loopback address and port;
3. exposes a readiness indication;
4. negotiates or validates the selected protocol revision according to the SDK and transport specification;
5. accepts client requests according to the documented revision-specific state model;
6. handles explicit cancellation and shutdown signals;
7. releases its socket and temporary resources cleanly.

Do not infer that Streamable HTTP is always stateful or always stateless. Document the behavior of each claimed protocol revision and SDK mode.

Service integration may be manual, systemd, launchd, a Windows service, a container, or another mechanism selected in `RUNTIME.md`.

## Bundled ad hoc MCP tool client

The client command-line interface is not standardized by MCP. The concrete skill must define a stable local command and map it to standard protocol behavior.

Recommended mapping:

| Local operation | Required behavior |
|---|---|
| `server-info` | Perform the revision-appropriate lifecycle or discovery exchange and report negotiated server information and capabilities |
| `tools list` | Send `tools/list`; follow opaque pagination cursors unless the caller explicitly requests one page |
| `tools show TOOL` | Filter the full `tools/list` result locally; do not send a nonexistent `tools/show`, `tools/get`, or `tools/describe` method |
| `tools call TOOL` | Send one `tools/call` request |
| `tools run` | Orchestrate several separate `tools/call` requests; do not describe this as an MCP batch method |

A tools-only client must preserve server-supplied tool definitions and standard call results. In particular:

- preserve `content`, `structuredContent`, `isError`, `_meta`, and applicable extension or future fields;
- treat tool annotations from untrusted servers as hints;
- distinguish transport failure, protocol error, a returned tool error, and a successful domain result;
- validate output against a declared output schema when supported;
- treat tool names as case-sensitive;
- keep pagination cursors opaque;
- expose a lossless MCP JSON output mode.

The client should normally generate JSON-RPC request IDs internally. It should not expose an arbitrary server shell command or arbitrary request ID as a normal public option.

A `tools run` command may reuse one process, connection, or HTTP client, but that does not create portable application state. Required state must be represented through documented arguments, resource identifiers, handles, or server configuration.

## Interaction, cancellation, and tasks

A concrete client must define non-interactive behavior. When the server needs more input, the client must not hang indefinitely or prompt unexpectedly in an agent or CI context.

Recommended modes are:

- **non-interactive:** return the protocol's incomplete or input-required result in structured form;
- **interactive:** prompt a human only when explicitly selected;
- **response file:** provide pre-authorized answers when the selected protocol revision and SDK support this mechanism.

Timeouts must invoke the selected revision and transport's cancellation behavior and then clean up the request, connection, and child process as applicable.

Tasks are revision- and extension-dependent. Do not add task commands or claim task support unless:

1. the selected SDK implements the applicable task model;
2. the server advertises the required capability or extension;
3. polling, notifications, input-required states, cancellation, retention, and terminal results are tested.

## Roots and workspace restrictions

MCP roots and a skill's workspace policy are not interchangeable concepts. Roots support is protocol- and capability-dependent, and newer protocol revisions may prefer explicit tool arguments, resource URIs, or server configuration.

Do not invent a universal MCP `--workspace` option. A concrete skill may expose a skill-specific workspace option, but it must document whether that value configures the server, becomes a tool argument, supplies a resource URI, or participates in a negotiated MCP capability.

## Loopback security baseline

The default network variant must:

- bind to `127.0.0.1` or `::1`;
- validate the Host header;
- validate the `Origin` header on every incoming connection;
- return HTTP 403 when an `Origin` header is present but not explicitly allowed;
- define whether an absent `Origin` is accepted for documented non-browser clients;
- enable DNS-rebinding protection;
- avoid exposing secrets in URLs or command-line arguments;
- use an explicit endpoint path, normally `/mcp`;
- reject requests that exceed documented size or timeout limits;
- preserve the same workspace and write restrictions as stdio.

Origin validation is required even when browser clients are not an intended interface. Loopback-only access reduces exposure but does not make browser-origin or DNS-rebinding attacks impossible.

## Non-loopback access

Binding to all interfaces or a LAN address is a separate deployment mode. Before enabling it, document:

- intended clients and trust boundary;
- authentication and authorization;
- TLS or trusted reverse-proxy termination;
- firewall and network assumptions;
- allowed hosts and origins;
- secret provisioning and rotation;
- audit logging and rate limits;
- upgrade and incident-response procedures.

The language-neutral template does not prescribe one authentication implementation.

## Agent fallback policy

When both variants exist, `INTERFACES.md` must define a deterministic order such as:

```text
1. Use the configured local Streamable HTTP endpoint when its readiness check succeeds.
2. Otherwise launch the bundled stdio server through the ad hoc MCP tool client.
3. Otherwise use the structured CLI.
```

Another order is valid, but the agent must not infer it from file names or runtime availability.

Starting a second local network server as an implicit fallback is discouraged because it can cause port conflicts, stale processes, and inconsistent state.

## Required tests

A concrete implementation supporting both variants and a bundled tool client should test:

- every claimed protocol revision and negotiation path;
- the same operation inventory and schemas across transports;
- complete `tools/list` pagination with opaque cursors;
- equivalent successful results;
- equivalent domain failures;
- separation of transport, protocol, and `isError` tool failures;
- preservation of standard result fields and unknown extension metadata;
- identical safety and workspace restrictions;
- stdio exit on client disconnect;
- timeout cancellation and child-process cleanup;
- documented non-interactive handling of additional-input results;
- any claimed task or extension behavior;
- Streamable HTTP readiness and graceful shutdown;
- loopback-only default binding;
- Host-header rejection;
- HTTP 403 for a present but disallowed `Origin`;
- documented handling of requests without an `Origin` header;
- concurrent-client behavior;
- configured revision-specific state behavior;
- confirmation that local `tools show` and `tools run` conveniences do not send nonexistent MCP methods or JSON-RPC batches.
