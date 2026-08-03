# Architecture guidance

This repository is a language-neutral template for Agent Skills. The architecture must remain proportional to the selected profile and must not impose runtime, interface, service, or deployment layers on skills that do not need them.

## Repository boundary

The repository root is the installable skill directory:

```text
<project>/.agents/skills/<skill-name>/
```

`SKILL.md` is the only universally required skill file. References, assets, scripts, application code, interfaces, runtime records, and deployment material are optional and become required only when selected behavior needs them.

## Progressive architecture

A concrete skill should stop at the first sufficient shape:

```text
instruction-only
    |
    +--> knowledge-augmented / asset-driven / script-assisted
              |
              +--> packaged CLI / MCP-enabled
                           |
                           +--> browser-interface / headless-service
                                         |
                                         +--> explicit deployment variants
```

This is not a maturity ladder. An instruction-only skill may be complete. A headless service is not inherently better than a bounded helper. Each added layer creates a contract, trust boundary, validation obligation, and removal cost.

## Contract ownership

| Concern | Source of truth |
|---|---|
| Agent trigger, workflow, resource use, outputs, and safety | `SKILL.md` |
| Runtime, dependency, command, protocol selection, process lifecycle, and deployment topology | `RUNTIME.md` |
| Agent-facing interface order and fallback | `INTERFACES.md` |
| Stable packaged command behavior | `CLI_INTERFACE.md` |
| MCP caller behavior | `MCP_INTERFACE.md` |
| Browser-visible behavior | `WEB_INTERFACE.md` |
| Maintainer architecture and transport guidance | `docs/` |

Avoid duplicating exact command, revision, port, secret, or topology selections across several authorities. Cross-reference the owning contract.

## Shared implementation and thin adapters

When several interfaces expose the same operation, prefer one domain implementation behind thin adapters:

```text
caller
  |
  +--> CLI adapter --------+
  +--> MCP adapter --------+--> shared operation/domain layer
  +--> Web/API adapter ----+
```

Thin does not mean trivial. An adapter still owns its caller-visible parsing, framing, authentication handoff, cancellation, error mapping, and compatibility. Shared domain logic must not depend on transport-specific request objects or lifecycle managers.

Do not force this split onto a small self-contained helper when it adds no real reliability or reuse.

## Process and lifecycle ownership

Every process must have one explicit owner:

- an MCP host owns its stdio child;
- a human or operator owns a foreground listener;
- a bundled local lifecycle controller may own one fixed background process group;
- an OS service manager owns a service unit;
- a container runtime owns a container process;
- an orchestrator owns replicas and rollout state.

These are distinct deployment topologies. Do not combine them into one ambiguous “production” claim.

A bundled local lifecycle controller must remain outside the domain and protocol layers:

```text
operator
  |
  +--> lifecycle controller
           |
           +--> fixed server adapter --> shared domain layer
```

The controller may own start, stop, restart, readiness, liveness, external-secret loading, process identity, stale-record handling, and bounded shutdown escalation. It must not expose those controls as MCP tools, mutate application semantics, accept arbitrary server commands, or become an implicit agent fallback.

## Trust-boundary decomposition

Treat each of the following as a separate boundary unless a concrete deployment proves otherwise:

- child-process execution;
- loopback listener;
- non-loopback listener;
- reverse proxy and forwarded headers;
- TLS termination;
- authentication and authorization;
- external secret provision;
- service-manager or lifecycle ownership;
- container isolation;
- persistence and migration authority;
- backup and restore;
- operational diagnostics, metrics, audit, and overload controls.

One PR should normally add one clear boundary or topology. A loopback lifecycle controller does not establish trusted-proxy, TLS, container, persistence, or remote-service safety.

## Secure lifecycle records

When a controller records process identity, PID alone is usually insufficient because operating systems reuse process IDs. Use PID plus a process-start identity, an OS process handle, pidfd, service-unit identity, container identity, or equivalent authority. Verify identity before signaling and treat mismatch as stale.

Lifecycle metadata and external secret files should be bounded, regular, non-symlink files with explicit ownership and permissions. Publish records atomically and remove only the exact record the controller created or revalidated. Configuration failure must occur before opening a listener or starting an unrelated process.

Graceful shutdown requires a documented drain or stop signal, a bounded grace period, deterministic escalation, and tests for resistant or stale processes. Restart should mean complete stop followed by start unless a separate handoff topology is explicitly selected and tested.

## State authority

Stateless transport or process reuse does not imply stateless application behavior. When persistence exists, identify:

- authoritative state and schema owner;
- version and migration owner;
- transaction and concurrency model;
- rollback limits;
- backup and restore procedure;
- corruption detection and restart recovery;
- compatibility across replicas or versions.

Do not add persistence merely to make a fixture appear production-like.

## Security placement

Apply security at the earliest layer that has the required context:

- process launchers validate fixed commands and secret sources;
- network gates validate Host, Origin, authentication, size, and protocol headers per request;
- adapters enforce caller-visible schemas and authorization mapping;
- domain operations enforce business authorization and invariants;
- deployment layers enforce listener exposure, TLS, resource limits, and restart semantics.

A valid connection or earlier request must not authorize a later request. A valid PID record must not authorize signaling after process identity changes.

## Failure boundaries

Keep these outcomes distinct:

- configuration failure before startup;
- process startup failure;
- readiness failure;
- liveness failure;
- stale or unsafe lifecycle record;
- bounded shutdown escalation;
- transport failure;
- protocol failure;
- authentication or authorization failure;
- capacity or overload rejection;
- domain error;
- persistence or migration failure.

Do not silently convert one into another or report partial startup as success.

## Validation strategy

Test at the lowest layer that establishes the claim, then add one executable smoke path across the selected topology. Negative tests should remove or corrupt the exact boundary artifact and prove the expected diagnostic.

For a managed local lifecycle variant, proportionate evidence includes:

- real start, readiness, liveness, restart, and stop;
- secret permission and symlink rejection before process creation;
- safe stale-record replacement and unsafe-record refusal;
- identity verification against PID reuse;
- graceful shutdown and TERM-to-KILL escalation;
- token redaction from argv, lifecycle records, and logs;
- unchanged protocol and domain behavior through the managed process.

## Removal discipline

When a profile or deployment mode is removed, delete its implementation, tests, commands, contract rows, documentation, and publication references together. Do not leave placeholder service, container, reverse-proxy, persistence, or interface material in a smaller skill.
