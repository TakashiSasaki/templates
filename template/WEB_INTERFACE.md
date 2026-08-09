# Optional human verification web interface

Complete this file only when the concrete skill may provide a **standalone browser-facing page** for verification, diagnostics, demonstration, or limited human operation. This interface is optional and is not part of MCP itself.

A Host-embedded MCP App View is not this interface. When `io.modelcontextprotocol/ui` is selected, Apps-specific `ui://` resources, View↔Host bridge behavior, sandboxing, CSP, permissions, and fallback belong in `MCP_APPS.md`. MCP Apps alone does not select `browser-interface` and does not require this file in a concrete Skill.

## Status and purpose

```text
Supported: UNSELECTED
Purpose: verification / debugging / demonstration / limited operations / other: TODO
Default enablement: disabled / enabled in development / explicitly enabled / always enabled: TODO
Production policy: disabled / restricted / supported: TODO
```

A debug or verification page should normally be disabled unless explicitly enabled. Do not make the MCP server depend on the page being available.

## Deployment authority

`RUNTIME.md` is the sole source of truth for process, listener, port, container, Pod or task, service, gateway, reverse-proxy, external-origin, and deployment-selection choices. Do not repeat those selections here.

```text
Deployment topology: see RUNTIME.md
Listener and port model: see RUNTIME.md
External-origin model: see RUNTIME.md
Deployment selection time: see RUNTIME.md
```

This file defines the browser-visible behavior and safety contract that must remain valid under every topology selected in `RUNTIME.md`.

Using the same process or container is acceptable for a debug-only page when it reduces operational complexity. Logical boundaries must remain explicit even when process and deployment boundaries are collapsed.

## Public routing

```text
External base URL: TODO or DEPLOYMENT-SELECTED
Web UI path or URL: TODO
UI backend API path or URL: TODO or NOT APPLICABLE
MCP endpoint visible to the browser: YES / NO / DEPLOYMENT-SELECTED
MCP endpoint used by the UI backend: TODO
Selected topology and listener model: see RUNTIME.md
```

A separate port is not required. When `RUNTIME.md` selects a shared listener, one listener may route `/`, `/api/`, and `/mcp` separately. A reverse proxy may also present one external origin while forwarding to different internal processes or containers.

Path sharing does not merge security policies. The UI, its backend API, the MCP endpoint, and health endpoints remain separate logical interfaces even when they share a host and port.

## Relationship to MCP and MCP Apps

Choose one standalone-Web interaction model:

```text
UI interaction model:
- backend acts as an MCP client: TODO
- browser calls MCP directly: TODO
- UI uses a non-MCP application API: TODO
- mixed model: TODO
```

For a page intended to verify MCP behavior, the action under test must traverse the actual MCP client, protocol, transport, and server adapter. Do not call the application layer directly and describe that result as MCP verification.

MCP Apps follows a different execution model: a Host renders an App View in a sandbox and mediates its bridge calls. Do not model that Host-embedded View as an external Web URL, do not use this file as the Apps sandbox/permission contract, and do not infer `browser-interface` merely because the Apps implementation contains HTML, CSS, or JavaScript.

If frontend code intentionally supports both standalone Web and MCP Apps modes, retain both `WEB_INTERFACE.md` and `MCP_APPS.md`. Define which routing, authentication, credential, CSP, Host capability, and lifecycle assumptions apply to each mode rather than treating one contract as an alias of the other.

A backend-for-frontend that acts as an MCP client is normally safer than direct browser-to-MCP access. It can keep service credentials out of browser code, apply a narrower authorization policy, normalize diagnostics, and restrict which tools are exposed.

Direct browser-to-MCP access is allowed only when the concrete skill explicitly defines and tests:

- browser authentication and authorization;
- Origin and CORS policy;
- CSRF and cross-site request protections where applicable;
- credential handling;
- allowed MCP methods and tools;
- result redaction and download behavior;
- request size, timeout, and rate limits.

## UI capabilities

```text
Server information display: TODO
Tool inventory display: TODO
Input-schema form generation: TODO
Raw MCP request display: TODO
Raw MCP result display: TODO
Normalized result display: TODO
Transport and protocol diagnostics: TODO
Cancellation and timeout controls: TODO
Additional-input handling: TODO
Trace or correlation information: TODO
```

Do not assume that every MCP capability must be exposed. A verification UI may be intentionally tools-only or read-only.

## Human authorization and safety

```text
Authentication: TODO
Allowed users or network boundary: TODO
Read-only operations: TODO
Mutating operations: TODO
Destructive operations: TODO
Confirmation policy: TODO
Sensitive argument masking: TODO
Sensitive result masking: TODO
Audit logging: TODO
```

Server-supplied tool annotations are hints, not an authorization policy. Use trusted local configuration to decide whether an operation is visible, executable, confirmable, or prohibited.

For debug-only deployments:

- bind to loopback by default unless remote access is explicitly designed in `RUNTIME.md`;
- do not expose the page merely because the MCP service is externally reachable;
- do not enable mutating or destructive operations by default;
- do not display secrets, authorization headers, cookies, tokens, or unredacted sensitive results;
- remove or disable the page in production unless the production policy explicitly permits it.

## Lifecycle and failure isolation

```text
Start, stop, and readiness commands: see RUNTIME.md
Enablement configuration: see RUNTIME.md
Web health behavior: TODO
MCP readiness check: see RUNTIME.md
Failure relationship: independent / shared process with isolated routing / other: TODO
```

The Web UI is not the MCP server's readiness or liveness signal. A broken page must not automatically mark the MCP endpoint unhealthy, and a healthy page must not prove that MCP tool invocation works.

When the Web UI shares a process or container with the MCP server:

- keep routing, authentication, logging, and error handling logically separate;
- avoid loading large UI assets or debug state on MCP-only startup paths when the UI is disabled;
- make UI enablement explicit and deterministic;
- ensure UI shutdown and failure handling do not leave MCP requests in an undefined state;
- document whether one process failure affects both interfaces.

## Shared implementation

The Web UI may reuse:

- the same MCP client library as the bundled ad hoc MCP tool client;
- the same lossless result and pagination representations;
- the same schema rendering and validation utilities;
- the same trusted operation policy and redaction rules;
- the same trace and diagnostic model;
- frontend components also used by an MCP App, when their environment-specific adapters remain separate.

It must not duplicate domain behavior or create a second, inconsistent tool registry. Shared frontend code must not collapse the standalone-Web and MCP Apps trust boundaries.

## Required tests

When the Web UI is supported, test the applicable cases:

- disabled-by-default behavior and explicit enablement;
- every deployment topology selected in `RUNTIME.md`, or a topology-independent contract suite plus deployment-specific smoke tests;
- shared-listener path isolation and separate-listener behavior where selected;
- reverse-proxy routing where selected;
- UI authentication and authorization;
- operation allow, deny, and confirmation policy;
- secret and sensitive-result redaction;
- actual MCP-path verification for pages claiming to test MCP;
- browser-to-MCP Origin, CORS, CSRF, and credential behavior when direct access is supported;
- independent UI and MCP readiness checks;
- UI failure without false MCP health results;
- MCP failure displayed accurately by the UI;
- production-disable or restricted-production policy;
- separate contract behavior when the same frontend is also used as an MCP App.

## Decision rationale

Explain why a standalone human-facing page is or is not supported, why its default enablement is appropriate, how the deployment selections recorded in `RUNTIME.md` support the intended uses, and which security and lifecycle properties remain invariant across those deployments. If the Skill also supports MCP Apps, explain why a separate standalone browser surface is still needed rather than treating the App View as equivalent.

TODO
