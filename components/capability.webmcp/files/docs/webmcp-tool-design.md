# WebMCP tool design

Design tools around domain intent rather than controls. `search-docs`, `get-profile`, `update-profile`, and `start-password-reset` are meaningful operations; `click-button` and `run-action` are not stable product contracts.

## Identity

Each entry has two identities:

- `id`: stable Composition contract identity used for evidence and evolution.
- `name`: caller-visible WebMCP registration name.

Changing a caller-visible name does not silently rename the stable contract item. Contract migration must be explicit when compatibility expectations change.

## Shared operation boundary

A WebMCP `execute` callback should be an adapter around an existing domain/application operation. It must not implement alternate authorization, validation, state-transition, confirmation, or side-effect logic.

Conceptually:

```text
Human UI ─┐
REST/API ─┼── shared domain/application operation
MCP ──────┤
WebMCP ───┤
CLI ──────┘
```

## Effect classification

- `read-only`: cannot mutate authoritative product or external state.
- `state-changing`: mutates product state but is not classified as consequential by the product.
- `consequential`: externally observable, security-sensitive, financial, account, irreversible, or similarly guarded operation.

A consequential tool must use `required-by-domain-operation` confirmation. This classification is product authority; upstream annotations are hints and may only mirror it.

## Output trust

Use `untrusted` when returned content can contain user-generated, third-party, remote, or otherwise instruction-like data that an agent must not treat as trusted control text. Do not sanitize the classification away merely because rendering is safe for HTML.

## Applicability

Declare the routes and product states in which registration and invocation are valid. Route/state changes must remove stale registrations or make invocation fail closed. Empty route/state arrays mean the operation is globally applicable within the selected product contract, not that checks may be skipped.
