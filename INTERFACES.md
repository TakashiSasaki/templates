# Public interface selection contract

Retain and complete this file when `packaged-cli` or `mcp-enabled` is selected. It defines how an agent chooses among maintained public interfaces; detailed caller-visible behavior belongs in the profile-specific contract files.

Private helper scripts are not public interfaces. Their bounded invocation contracts remain in `SKILL.md`.

## Status

```text
Selection status: UNSELECTED
```

Change the status to `SELECTED` only after the preferred route, fallbacks, availability behavior, rationale, and every retained profile-specific contract are complete.

## Execution policy

Select exactly one preferred agent interface and define a deterministic fallback order.

```text
Preferred agent interface: UNSELECTED
Fallback 1: UNSELECTED
Fallback 2: UNSELECTED
```

Allowed interface categories:

- native MCP tool already registered in the host;
- existing Streamable HTTP MCP endpoint;
- bundled ad hoc MCP tool client over stdio or Streamable HTTP;
- stable in-place CLI launcher;
- installed human CLI command;
- NONE when no further fallback is permitted.

Do not write “use whichever is appropriate” unless the routes are intentionally interchangeable and nondeterminism is acceptable.

When both MCP transports are supported, state whether an agent should:

1. connect to an already-running Streamable HTTP endpoint;
2. fall back to launching the bundled stdio server through the ad hoc MCP tool client; or
3. bypass MCP and use the structured CLI.

Do not start a second network server merely because the configured endpoint is unavailable unless that fallback is explicitly documented.

## Contract index

| Selected profile or interface | Authoritative contract | Retention rule |
|---|---|---|
| Private helper script | `SKILL.md` | No public-interface contract required |
| `packaged-cli` | `CLI_INTERFACE.md` | Required only when `packaged-cli` is selected |
| `mcp-enabled` | `MCP_INTERFACE.md` | Required only when `mcp-enabled` is selected |
| `browser-interface` | `WEB_INTERFACE.md` | Required only when a browser-facing interface is selected |
| Runtime, commands, packaging, deployment | `RUNTIME.md` | Required for application and service profiles; optional for substantial helper-runtime decisions |
| Headless service public reachability | `RUNTIME.md` and referenced API/deployment material | Does not require `WEB_INTERFACE.md` unless a browser surface exists |

The profile-specific file is the sole source of truth for its caller-visible behavior. Do not copy CLI command contracts into `MCP_INTERFACE.md`, MCP transport behavior into `CLI_INTERFACE.md`, or browser behavior into this routing document.

## Cross-interface invariants

When several maintained interfaces expose the same operation under the same identity, authorization, configuration, and workspace policy:

- inputs, results, side effects, and safety checks must have equivalent meaning;
- transport or presentation differences must not alter domain behavior;
- fallback must not silently weaken authentication, authorization, confirmation, workspace, or write restrictions;
- an agent must be able to determine which route was used and how failures are classified;
- adapters should share tested operation logic when complexity or multiple interfaces justify that architecture.

## Availability and failure behavior

```text
Unavailable preferred interface behavior: TODO
Fallback activation conditions: TODO
Failure classification exposed to callers: TODO
```

Distinguish an unavailable interface from a negative domain result. Do not treat Web readiness as MCP readiness, a listening socket as successful protocol negotiation, or a CLI process exit as proof that its structured result is valid.

## Decision rationale

```text
Rationale: TODO
```

Explain why the preferred interface and fallback order fit the skill, which routes are intentionally unavailable, and how the policy avoids unnecessary process or network startup.
