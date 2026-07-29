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
        +----------------------+------------------------+
        |                      |                        |
        v                      v                        v
      CLI adapter      stdio MCP adapter     Streamable HTTP adapter
        |                      |                        |
        +----------------------+------------------------+
                               v
                       shared server factory
                       and application layer
                               v
                          domain core
                               v
               infrastructure/filesystem/network
```

The specific filenames depend on the selected implementation language. The dependency direction does not.

## Skill instructions

`SKILL.md` defines when the skill applies, required workflow, safety constraints, and the stable execution entry point. It should not become a complete developer manual.

When both MCP transports exist, the skill must state whether it connects to an existing local Streamable HTTP endpoint, launches stdio ad hoc, or uses the CLI as a fallback. It must not leave this choice implicit.

## Public adapters

The CLI serves humans and may also provide the stable process interface used by an agent.

The optional MCP interface may have two lifecycle variants:

- **stdio:** the MCP host or bundled client launches and owns a child process;
- **Streamable HTTP:** an independently managed process listens on a local network endpoint.

Both MCP variants must expose the same server capabilities and operations through a shared server factory, operation registry, or equivalent composition root. Transport selection must not duplicate tool definitions.

A raw TCP socket protocol is not the standard network MCP transport. The network variant should normally use Streamable HTTP over TCP.

## Application and domain

Application code coordinates use cases. Domain code implements the rules being protected by the skill. Neither layer should know whether a request originated from CLI, stdio MCP, or Streamable HTTP MCP.

Transport adapters may handle:

- process or socket lifecycle;
- protocol framing;
- HTTP bind address, port, path, and headers;
- authentication and origin/host validation;
- conversion between protocol objects and application requests/results.

They must not change domain semantics.

## Network-server boundary

The local Streamable HTTP entry point is a separately managed service boundary even when its source is bundled with the skill.

It must define:

- loopback-only default binding;
- endpoint and readiness behavior;
- session and concurrency model;
- authentication and non-loopback policy;
- startup, shutdown, restart, and stale-process handling;
- DNS-rebinding and Host-header defenses.

A language-specific implementation may use one executable with transport flags or separate entry points. In either case, shared tool registration and application logic are mandatory.

## Runtime-loaded references versus maintainer docs

- `references/`: potentially loaded during skill execution;
- `docs/`: used to develop and maintain the skill.

This distinction limits unnecessary context while keeping the repository understandable.

## Distribution

A release may include the whole repository or a reduced skill bundle. If a reduced bundle is produced, it must retain everything needed for in-place execution and must preserve relative paths referenced by `SKILL.md`.

When the network variant is supported, the distribution documentation must also state whether service definitions such as systemd, launchd, Windows service, or container configuration are bundled, generated, or intentionally left to the installer.