# MCP transport variants

This template supports two standard MCP deployment variants that share one implementation.

## Terminology

Use these names consistently:

- **stdio MCP server:** a client launches the server as a child process and communicates through stdin/stdout;
- **local Streamable HTTP MCP server:** an independently managed process listens on a loopback TCP socket and exposes an HTTP MCP endpoint.

Do not call the second variant a raw TCP MCP transport. TCP is the underlying network protocol, while Streamable HTTP is the standard MCP transport presented to clients.

## Decision matrix

| Requirement | Preferred variant |
|---|---|
| Skill needs MCP only during one workflow | stdio |
| No listening socket should remain open | stdio |
| Server lifetime should follow one client | stdio |
| Several local clients need one endpoint | Streamable HTTP |
| Server keeps reusable caches or resources | Streamable HTTP, with documented state model |
| Native host is already configured for a child process | stdio |
| Native host connects by URL | Streamable HTTP |
| Broader network deployment | Streamable HTTP with a separate security design |

A concrete skill may support both. Supporting both does not justify duplicate tool implementations.

## Shared composition

The preferred implementation shape is:

```text
createServer / registerOperations
            |
            +--> serve over stdio
            +--> serve over Streamable HTTP
            +--> drive through test transport
```

The shared layer owns:

- tool, resource, and prompt definitions;
- input and output schemas;
- application calls;
- workspace and authorization decisions that are independent of transport;
- structured error mapping.

The transport entry points own only transport and lifecycle concerns.

## stdio lifecycle

The stdio client or host:

1. starts the server process;
2. initializes the MCP session;
3. invokes one or more operations;
4. closes the session or stdin;
5. waits for the server process to exit.

The server must not daemonize or retain a listener after the session ends.

## Local Streamable HTTP lifecycle

The local network server:

1. starts independently of a particular MCP request;
2. binds to a documented loopback address and port;
3. exposes a readiness indication;
4. accepts one or more client sessions according to the documented state model;
5. handles an explicit shutdown signal;
6. releases its socket and temporary resources cleanly.

Service integration may be manual, systemd, launchd, a Windows service, a container, or another mechanism selected in `RUNTIME.md`.

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
2. Otherwise launch the bundled stdio server through the ad hoc client.
3. Otherwise use the structured CLI.
```

Another order is valid, but the agent must not infer it from file names or runtime availability.

Starting a second local network server as an implicit fallback is discouraged because it can cause port conflicts, stale processes, and inconsistent state.

## Required tests

A concrete implementation supporting both variants should test:

- the same operation inventory and schemas;
- equivalent successful results;
- equivalent domain failures;
- identical safety and workspace restrictions;
- stdio exit on client disconnect;
- Streamable HTTP readiness and graceful shutdown;
- loopback-only default binding;
- Host-header rejection;
- HTTP 403 for a present but disallowed `Origin`;
- documented handling of requests without an `Origin` header;
- concurrent-client behavior;
- configured stateful or stateless session behavior.
