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
        +--------------------+----------------------+------------------+
        |                    |                      |                  |
        v                    v                      v                  v
      CLI adapter    bundled MCP tool client   native MCP host   service control
        |                    |                      |                  |
        |                    +-----------+----------+                  |
        |                                |                             |
        |                    +-----------+-----------+                 |
        |                    |                       |                 |
        |                    v                       v                 |
        |             stdio MCP adapter    Streamable HTTP adapter <--+
        |                    |                       |
        +--------------------+-----------+-----------+
                                         v
                              shared MCP registry and
                              application layer
                                         v
                                    domain core
                                         v
                         infrastructure/filesystem/network
```

The specific filenames depend on the selected implementation language. The dependency direction does not.

The bundled MCP tool client is a protocol client. It reaches the application layer only through an MCP server adapter. It must not bypass negotiation, request metadata, framing, transport behavior, or protocol tests while presenting the result as an MCP invocation.

The CLI is the public adapter in this diagram that may call the application layer directly. Service control starts and stops an independently managed Streamable HTTP process; it is not an MCP application operation.

## Skill instructions

`SKILL.md` defines when the skill applies, required workflow, safety constraints, and the stable execution entry point. It should not become a complete developer manual.

When both MCP transports exist, the skill must state whether it connects to an existing local Streamable HTTP endpoint, launches stdio through the bundled tool client, or uses the CLI as a fallback. It must not leave this choice implicit.

## Public adapters

The CLI serves humans and may also provide the stable process interface used by an agent.

The optional MCP server interface may have two transport and lifecycle variants:

- **stdio:** an MCP host or bundled tool client launches and owns a trusted child process;
- **Streamable HTTP:** an independently managed process listens on a local network endpoint.

A bundled tools-only client is separate from the server adapters. It performs the selected revision's discovery or initialization behavior and invokes the adapters through standard MCP requests.

Both MCP server variants must expose equivalent domain operations through a shared server factory, operation registry, or equivalent composition root under the same protocol revision, identity, authorization, configuration, and workspace policy. Transport selection must not duplicate tool definitions.

A raw TCP socket protocol is not the standard network MCP transport. The network variant should normally use Streamable HTTP over TCP.

## Protocol eras and state

Protocol revision and transport are independent decisions.

At the time this template was aligned:

- `2026-07-28` uses stateless, self-contained requests, per-request protocol metadata, and `server/discover`;
- `2025-11-25` and earlier revisions use the `initialize` / `notifications/initialized` lifecycle and may include initialization-era HTTP session behavior.

Do not use the word “session” as a portable guarantee of application state. Reusing a process, connection, HTTP client, or legacy protocol session does not imply that one tool call can depend on hidden state from another. Portable state must be represented by documented arguments, resource identifiers, handles, durable storage, or server configuration.

When a concrete skill supports more than one era, isolate compatibility behavior in the protocol and transport layers. Domain semantics must not vary because negotiation selected a different revision.

## Application and domain

Application code coordinates use cases. Domain code implements the rules being protected by the skill. Neither layer should know whether a request originated from CLI, stdio MCP, or Streamable HTTP MCP.

Transport and protocol adapters may handle:

- process, connection, request, or socket lifecycle;
- protocol framing and revision negotiation;
- per-request metadata and custom transport headers;
- HTTP bind address, port, path, and headers;
- authentication and origin/host validation;
- conversion between protocol objects and application requests/results;
- cancellation and additional-input control flow;
- lossless preservation of protocol results and extension metadata.

They must not change domain semantics.

## Network-server boundary

The local Streamable HTTP entry point is a separately managed service boundary even when its source is bundled with the skill.

It must define:

- loopback-only default binding;
- endpoint and readiness behavior;
- supported protocol eras and revision-specific state behavior;
- concurrency and per-request cancellation;
- authentication and non-loopback policy;
- startup, shutdown, restart, and stale-process handling;
- DNS-rebinding, Host-header, and Origin defenses;
- modern request metadata, JSON/SSE response behavior, and `x-mcp-header` processing when `2026-07-28` is supported;
- initialization-era compatibility behavior when an older revision is supported on the same endpoint.

A language-specific implementation may use one executable with transport flags or separate entry points. In either case, shared tool registration and application logic are mandatory.

## Runtime-loaded references versus maintainer docs

- `references/`: potentially loaded during skill execution;
- `docs/`: used to develop and maintain the skill.

This distinction limits unnecessary context while keeping the repository understandable.

## Distribution

A release may include the whole repository or a reduced skill bundle. If a reduced bundle is produced, it must retain everything needed for in-place execution and must preserve relative paths referenced by `SKILL.md`.

When the network variant is supported, the distribution documentation must also state whether service definitions such as systemd, launchd, Windows service, or container configuration are bundled, generated, or intentionally left to the installer.
