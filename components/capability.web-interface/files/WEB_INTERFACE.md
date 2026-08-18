# Standalone browser interface contract

This contract is materialized by `capability.web-interface`. It defines an ordinary browser-facing page for verification, diagnostics, demonstration, or product operation. It is independent of MCP Apps.

`RUNTIME.md` owns process, listener, port, container, gateway, reverse-proxy, external-origin, and deployment-selection choices. This file owns browser-visible routing, interaction, security, health, and failure behavior.

## Status and purpose

```text
Supported: UNSELECTED
Purpose: verification / diagnostics / demonstration / product operations / other: TODO
Default enablement: TODO
Production policy: TODO
```

A debug/verification surface should normally be disabled unless explicitly enabled.

## Public routing

```text
External base URL: TODO or DEPLOYMENT-SELECTED
Web UI path/URL: TODO
Backend API path/URL: TODO or NOT APPLICABLE
MCP endpoint visible to the browser: YES / NO / DEPLOYMENT-SELECTED
Selected topology/listener model: see RUNTIME.md
```

A separate port is optional. Shared listener or reverse-proxy deployment does not merge the UI, backend API, MCP endpoint, or health interfaces into one security contract.

## Relationship to MCP and MCP Apps

Choose one interaction model:

```text
UI interaction model:
- backend acts as an MCP client: TODO
- browser calls MCP directly: TODO
- UI uses a non-MCP application API: TODO
- mixed model: TODO
```

A page claiming to verify MCP behavior must traverse the actual MCP client/protocol/transport/server path under test.

MCP Apps is a Host-embedded sandboxed execution model governed by `MCP_APPS.md`; it is not represented by an external Web URL. Shared frontend code must preserve the distinct trust and lifecycle boundaries.

A backend-for-frontend is normally safer than direct browser-to-MCP access because it can keep service credentials out of browser code and expose a narrower operation surface.

Direct browser-to-MCP access requires explicit, tested:

- browser authentication and authorization;
- Origin and CORS policy;
- CSRF/cross-site protections where applicable;
- credential handling;
- allowed methods/operations;
- result redaction/download policy;
- request size, timeout, and rate limits.

## UI capabilities

```text
Information/status display: TODO
Operation inventory: TODO
Schema/form generation: TODO
Raw request display: TODO
Raw result display: TODO
Normalized result display: TODO
Transport/protocol diagnostics: TODO
Cancellation/timeout controls: TODO
Trace/correlation information: TODO
```

Expose only capabilities needed for the stated purpose.

## Human authorization and safety

```text
Authentication: TODO
Allowed users/network boundary: TODO
Read-only operations: TODO
Mutating operations: TODO
Destructive operations: TODO
Confirmation policy: TODO
Sensitive argument masking: TODO
Sensitive result masking: TODO
Audit logging: TODO
```

Do not infer authorization from server-supplied annotations or the mere existence of an operation.

## Lifecycle and failure isolation

```text
Start/stop/readiness commands: see RUNTIME.md
Web health behavior: TODO
Backend/MCP readiness: TODO or NOT APPLICABLE
Failure relationship: TODO
```

A healthy page does not prove that its backend or MCP operations work, and a broken page must not automatically make an otherwise independent service unhealthy.

When interfaces share a process/container/listener:

- keep routing, authentication, logging, and errors logically separate;
- avoid loading UI-only assets/state when the UI is disabled;
- make enablement explicit and deterministic;
- define whether one process failure affects all interfaces.

## Shared implementation

The UI may reuse application/domain operations, protocol clients, schema utilities, trusted operation policy, redaction, and diagnostic models. It must not duplicate domain behavior into a second inconsistent registry.

## Required tests

Test applicable cases:

- default enablement/disablement;
- every supported topology or a topology-independent contract suite plus smoke tests;
- shared/separate listener routing;
- reverse-proxy behavior where supported;
- authentication and authorization;
- allow/deny/confirmation policy;
- sensitive-data redaction;
- actual protocol path for verification claims;
- direct browser Origin/CORS/CSRF/credential behavior when supported;
- independent readiness/health semantics;
- production policy;
- distinct behavior when the same frontend also supports MCP Apps.

## Decision rationale

Explain why a standalone browser surface is needed, why its default/production policy is appropriate, and which security/lifecycle properties remain invariant across supported deployments.

TODO
