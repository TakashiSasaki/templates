# Architecture

## Package boundary

The repository root is both the development repository and the deployable skill directory. A clone, submodule checkout, or release archive should not require another wrapping directory.

## Layers

```text
SKILL.md and references
        |
        v
public execution policy
        |
        +----------------+----------------------+-------------------+------------------+
        |                |                      |                   |                  |
        v                v                      v                   v                  v
      CLI adapter   optional Web UI/BFF   bundled MCP tool client   native MCP host   service control
        |                |                      |                   |                  |
        |                +----------+-----------+                   |                  |
        |                           |                               |                  |
        |               +-----------+-----------+                   |                  |
        |               |                       |                   |                  |
        |               v                       v                   |                  |
        |        Web MCP client adapter   non-MCP Web API adapter   |                  |
        |               |                       |                   |                  |
        |               +-----------+           |                   |                  |
        |                           |            |                   |                  |
        |               +-----------+------------+-------------------+                  |
        |               |                           |                                  |
        |               v                           v                                  |
human browser --> Streamable HTTP adapter     stdio MCP adapter <---------------------+
   (direct MCP,          |                           |
    only when selected)  +-------------+-------------+
                                       |
        +------------------------------+-------------------+
        |                                                  |
        +---------------------> shared MCP registry and <---+
                               application layer
                                       |
                                       v
                                  domain core
                                       |
                                       v
                       infrastructure/filesystem/network
```

The diagram shows permitted dependency directions, not a required deployment topology. `RUNTIME.md` selects whether components share a process, listener, container, Pod or task, service, gateway, or reverse proxy.

The bundled MCP tool client and the Web MCP client adapter are protocol clients. They reach the application layer only through an MCP server adapter. They must not bypass negotiation, request metadata, framing, transport behavior, or protocol tests while presenting a result as an MCP invocation.

The CLI and a deliberately non-MCP Web API adapter may call the application layer directly. Such a Web API must not describe its result as MCP verification. Direct browser-to-MCP access is optional and permitted only when selected in `RUNTIME.md` and governed by the browser security contract in `WEB_INTERFACE.md`.

Service control starts and stops an independently managed Streamable HTTP process or a selected combined service. It is not an MCP application operation.

## Skill instructions

`SKILL.md` defines when the skill applies, required workflow, safety constraints, and the stable execution entry point. It should not become a complete developer manual.

When both MCP transports exist, the skill must state whether it connects to an existing Streamable HTTP endpoint, launches stdio through the bundled tool client, or uses the CLI as a fallback. It must not leave this choice implicit.

The optional human Web interface is not an implicit agent fallback unless `INTERFACES.md` explicitly selects it as one.

## Public adapters

The CLI serves humans and may also provide the stable process interface used by an agent.

The optional MCP server interface may have two transport and lifecycle variants:

- **stdio:** an MCP host or bundled tool client launches and owns a trusted child process;
- **Streamable HTTP:** an independently managed or combined process exposes a network endpoint.

A bundled tools-only client is separate from the server adapters. It performs the selected revision's discovery, initialization, or negotiation behavior and invokes the adapters through standard MCP requests.

The optional Web interface may use one or more explicitly selected models:

- a backend-for-frontend using an MCP client adapter;
- direct browser access to the Streamable HTTP MCP adapter;
- a non-MCP Web API adapter calling the application layer;
- a documented mixed model.

`WEB_INTERFACE.md` defines the observable browser contract. `RUNTIME.md` alone selects the supported deployment topology and exposure capabilities.

Both MCP server variants must expose equivalent domain operations through a shared server factory, operation registry, or equivalent composition root under the same protocol revision, identity, authorization, configuration, and workspace policy. Transport selection must not duplicate tool definitions.

A raw TCP socket protocol is not the standard network MCP transport. The network variant should normally use Streamable HTTP over TCP.

## Protocol revisions and state

Protocol revision and transport are independent decisions. Exact supported revisions, the current era boundary used by the concrete skill, SDK support, and compatibility policy are recorded only in `RUNTIME.md`.

Maintainer documents may describe revision-dependent behavior using terms such as modern mode or initialization-era mode, but they must not define their own revision-date boundary.

Do not use the word “session” as a portable guarantee of application state. Reusing a process, connection, HTTP client, or legacy protocol session does not imply that one tool call can depend on hidden state from another. Portable state must be represented by documented arguments, resource identifiers, handles, durable storage, or server configuration.

When a concrete skill supports more than one era, isolate compatibility behavior in the protocol and transport layers. Domain semantics must not vary because negotiation selected a different revision.

## Application and domain

Application code coordinates use cases. Domain code implements the rules being protected by the skill. Neither layer should know whether a request originated from CLI, Web API, stdio MCP, or Streamable HTTP MCP.

Transport, protocol, and Web adapters may handle:

- process, connection, request, or socket lifecycle;
- protocol framing and revision negotiation;
- per-request metadata and custom transport headers;
- HTTP bind address, port, path, and headers;
- browser routing, presentation, CORS, CSRF, and redaction;
- authentication and Origin/Host validation;
- conversion between protocol or Web objects and application requests/results;
- cancellation and additional-input control flow;
- lossless preservation of protocol results and extension metadata.

They must not change domain semantics or create a second tool registry.

## Network-server boundary

The Streamable HTTP entry point is a managed service boundary even when its source, process, listener, or container is shared with an optional Web interface.

It must define:

- default binding and non-loopback policy;
- endpoint and readiness behavior;
- supported protocol revisions and revision-specific state behavior from `RUNTIME.md`;
- concurrency and per-request cancellation;
- authentication and authorization;
- startup, shutdown, restart, and stale-process handling;
- DNS-rebinding, Host-header, and Origin defenses;
- request metadata, JSON/SSE response behavior, and tool-defined HTTP-header processing when required by the selected revision;
- compatibility behavior when an initialization-era revision is supported on the same endpoint;
- logical isolation from Web UI, Web API, and health routes when a listener or process is shared.

A language-specific implementation may use one executable with transport flags or separate entry points. In either case, shared tool registration and application logic are mandatory.

## Runtime-loaded references versus maintainer docs

- `references/`: potentially loaded during skill execution;
- `docs/`: used to develop and maintain the skill.

This distinction limits unnecessary context while keeping the repository understandable.

## Distribution

A release may include the whole repository or a reduced skill bundle. If a reduced bundle is produced, it must retain everything needed for in-place execution and must preserve relative paths referenced by `SKILL.md`.

When a network variant or optional Web interface is supported, distribution documentation must state whether service definitions such as systemd, launchd, Windows service, container, Pod, task, gateway, or reverse-proxy configuration are bundled, generated, or intentionally left to the installer.
