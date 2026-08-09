# Public interface selection contract

## Status

Selection status: SELECTED

## Execution policy

Preferred agent interface: native MCP tool already registered in the host
Fallback 1: NONE
Fallback 2: NONE

The fixture exposes one Modern stdio MCP route. When the Host advertises `io.modelcontextprotocol/ui`, that same MCP route may render the associated App View; MCP Apps is not a second route. A Host without Apps support receives the ordinary core MCP tool result.

## Contract index

| Selected profile or interface | Authoritative contract | Retention rule |
|---|---|---|
| `mcp-enabled` core protocol | `MCP_INTERFACE.md` | Required |
| MCP Apps extension | `MCP_APPS.md` | Required because `RUNTIME.md` selects `io.modelcontextprotocol/ui` |
| Runtime and extension selection | `RUNTIME.md` | Required |

No packaged CLI, standalone browser interface, Streamable HTTP endpoint, or headless service is selected.

## Cross-interface invariants

The domain operation is `src/text_stats.mjs` for every tool adapter in the fixture. App presentation does not change the primary `text_stats` arguments, result, side effects, or safety policy. App-only `refresh_stats` is hidden from the model-visible inventory by Host policy, and model-only `model_summary` is unavailable to an App View. Host mediation does not bypass authorization or cross-server isolation.

## Availability and failure behavior

Unavailable preferred interface behavior: Surface the stdio process, Modern discovery, extension negotiation, resource, bridge, protocol, or tool failure; do not create another transport or use a Legacy revision.
Fallback activation conditions: NONE; a non-App Host stays on the same MCP route and uses the core result rather than activating another interface.
Failure classification exposed to callers: Distinguish core transport/protocol failure, unsupported revision, unsupported/denied Apps capability, UI resource failure, View bridge failure, tool failure result, and successful core result.

## Decision rationale

Rationale: The fixture proves that MCP Apps is progressive enhancement of one MCP route. Keeping the routing contract unchanged makes the extension boundary explicit and prevents a Host-embedded View from being confused with a standalone browser interface.
