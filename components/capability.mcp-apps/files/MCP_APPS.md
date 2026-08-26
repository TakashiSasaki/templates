# MCP Apps extension guidance

This guidance is materialized by `capability.mcp-apps`, which requires `capability.mcp`. MCP Apps is an optional Host-embedded UI extension and is not the standalone browser interface governed by `WEB_INTERFACE.md`.

## Authority boundary

`contracts/mcp-apps.json` is the machine-readable authority for:

- whether MCP Apps is in `template`, `planning`, or `product` state;
- the stable Apps extension identity and selected extension revision;
- the stable `ui://` View item inventory;
- core MCP tool-operation to View association identity and relationships.

`contracts/mcp-interface.json` owns the core MCP revision, transport inventory, and operation inventory. `RUNTIME.md` owns runtime/SDK and deployment choices. This Markdown file retains qualitative Host capability, fallback, visibility, bridge, sandbox, permission, and failure-handling guidance that the machine contract does not encode.

Do **not** use a Markdown selection marker, prose, static HTML inspection, or a unit-only test as a substitute for the machine contract and implementation evidence.

## Productization sequence

1. Keep `contracts/mcp-apps.json` in `template` mode while no caller-visible Apps capability is intended.
2. Before coding, place the core MCP contract in `planning` and declare the stable planned tool operation IDs needed by the App.
3. Switch the Apps contract to `planning`. Declare the canonical `mcp-apps` extension identity (`io.modelcontextprotocol/ui`, revision `2026-01-26` for schema v2), every planned View by stable `id` and `purpose`, and every planned association by stable `id`, `operationId`, `viewId`, and `purpose`.
4. Bind every planned extension/View/association item exactly to implementation-evidence planning targets. The validator rejects phantom item IDs, associations to undeclared or non-tool planned MCP operations, undeclared Views, duplicate tool associations, and planned Views with no association. Composition validation must pass before product coding starts.
5. Promote the same extension identity/revision, stable IDs, and relationships to `product`; add View `resourceUri`/media type and executable success/negative behavior without silently renaming or rebinding the planned items.
6. Add one implementation-evidence record for each product `mcp_apps` extension, View, and association target and link every record from at least one product requirement with the required proof strength.
7. Treat unavailable executable/browser proof as deferred; do not convert it into a release-ready claim.

The current product extension is `io.modelcontextprotocol/ui` revision `2026-01-26`.

## Machine evidence targets

Planning and product item identities use the same target keys:

```text
contract-item / mcp_apps / extension / mcp-apps
contract-item / mcp_apps / view / <view-id>
contract-item / mcp_apps / association / <association-id>
```

Planning requirements declare the proof floor before implementation. Product evidence must then satisfy the same target-specific strength:

- extension advertisement/fallback: `integration-test` or `end-to-end-test`;
- View rendering/failure behavior: `accessibility-test` or `end-to-end-test`;
- tool-to-View association: `end-to-end-test`.

Both positive and negative product proof are required. The association validator also checks that `operationId` names a declared **tool** operation from `contracts/mcp-interface.json`, that `viewId` names a declared View, that a tool has at most one Apps association, and that every declared View is reachable from at least one association.

## Host capability and fallback

Document:

```text
Host capability requirement: TODO
Behavior when the Host does not advertise MCP Apps: TODO
Behavior when the Host advertises an unsupported Apps revision: TODO
Core-tool fallback: TODO
```

MCP Apps should be progressive enhancement unless the operation explicitly requires an App-capable Host. A broken View must not falsify or erase the underlying MCP result.

## Visibility and invocation

Document model/app visibility, App-only or model-only tool policy, cross-server invocation, and user confirmation for mutating actions. Visibility is not authorization. Host authorization, user consent, and cross-server isolation remain separate controls.

## Results and presentation

Prefer core `content` for meaningful non-App fallback, `structuredContent` for structured dynamic data, and the App resource for presentation/interaction. Do not make a View the only copy of an important result unless the operation explicitly requires Apps.

## View/Host bridge lifecycle

The Apps `ui/initialize` View↔Host lifecycle is distinct from core MCP protocol initialization. The View uses the Host-controlled bridge (JSON-RPC over `postMessage`) rather than arbitrary direct MCP access. Document initialization, allowed App-to-Host calls, Host-to-View updates, teardown, cancellation, and denial behavior.

## Sandbox and browser security

Treat App HTML/JavaScript as untrusted relative to the Host. Document and minimize:

- CSP resource/connect origins;
- browser permissions;
- dedicated-origin requirements;
- navigation/open-link policy;
- clipboard/download authority;
- credential exposure.

Avoid wildcard origins or hidden credential forwarding. Permission and sandbox behavior remain qualitative authority here until a later schema version deliberately structures them.

## Failure and degradation

Distinguish View resource load failure, bridge initialization failure, MCP protocol failure, tool/domain failure, Host capability denial, and teardown/retry behavior. Negative evidence for the machine targets must exercise the applicable failure path rather than merely assert that an error branch exists.

## Standalone Web boundary

MCP Apps does not select `capability.web-interface`. A Host-embedded View and a standalone Web page have different trust, routing, lifecycle, authentication, CSP, and capability boundaries. Shared frontend code is acceptable only when environment-specific adapters and contracts remain distinct.
