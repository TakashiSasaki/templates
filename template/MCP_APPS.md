# MCP Apps extension contract

Retain and complete this file only when a concrete Skill selects `mcp-enabled` and advertises the MCP Apps extension `io.modelcontextprotocol/ui`. MCP Apps is an optional MCP extension, not a separate Skill profile and not the standalone browser interface defined by `WEB_INTERFACE.md`.

`RUNTIME.md` is authoritative for the core MCP revision and the set of selected extension identifiers. This file is authoritative for the exact MCP Apps extension revision and Apps-specific caller-, Host-, and View-visible behavior. `MCP_INTERFACE.md` remains authoritative for core MCP behavior.

## Status and authority

```text
Selection status: UNSELECTED
Extension identifier: io.modelcontextprotocol/ui
Extension specification revision: 2026-01-26
Core MCP revision: see RUNTIME.md
```

Change the status to `SELECTED` only when `RUNTIME.md` includes `io.modelcontextprotocol/ui` in `Optional MCP extensions`, every retained Apps behavior below is concrete, and evidence covers the claimed extension behavior.

## Host capability and fallback

```text
Host capability requirement: TODO
Behavior when the Host does not advertise MCP Apps: TODO
Behavior when the Host advertises an unsupported Apps revision: TODO
Core-tool fallback: TODO
```

MCP Apps is progressive enhancement. Unless an operation intentionally requires an App-capable Host and documents that requirement, an associated tool should retain meaningful core MCP behavior when `io.modelcontextprotocol/ui` is unavailable. Do not make ordinary tool semantics depend on an iframe being rendered unless that dependency is explicit.

## UI resource inventory

Every selected App View is an MCP resource. Use stable `ui://` URIs and the Apps HTML media type defined by the selected extension revision.

| App/View | Resource URI | MIME type | Source or generator | Associated tools |
|---|---|---|---|---|
| TODO | `ui://TODO` | `text/html;profile=mcp-app` | TODO | TODO |

Resource URIs are public protocol identifiers, not filesystem paths. Record implementation sources separately. A bundled implementation may live under `mcp/apps/`, but generated or application-owned resources are also valid when `RUNTIME.md` makes ownership and build behavior explicit.

## Tool-to-UI linkage

```text
Tool metadata key: _meta.ui.resourceUri
Association policy: TODO
Unknown or missing UI resource behavior: TODO
```

Every advertised tool-to-UI association must resolve to a declared App resource. Do not inject arbitrary HTML into a tool result as a substitute for a stable UI resource declaration.

## Tool visibility and invocation

```text
Default model/app visibility policy: TODO
App-only tool policy: TODO or NOT SUPPORTED
Model-only tool policy: TODO or NOT SUPPORTED
Cross-server invocation policy: TODO
User confirmation policy for mutating App actions: TODO
```

Distinguish tools visible to the model, tools callable from an App View, and App-only implementation helpers. App-only tools must not accidentally enter the model-visible inventory. App visibility does not bypass Host authorization, user consent, or cross-server isolation.

## Result and presentation data

```text
Core text/content fallback: TODO
structuredContent policy: TODO
Sensitive-field redaction policy: TODO
Large-data policy: TODO
```

Keep presentation resources separate from dynamic tool results. `content` remains suitable for model/core fallback; `structuredContent` may carry JSON intended for rich rendering. Do not place secrets in presentation data merely because the View rather than the model is expected to consume it.

## View and Host bridge lifecycle

```text
View initialization behavior: TODO
Host bridge transport: JSON-RPC over postMessage
App-to-Host tool-call policy: TODO
Host-to-View result/update policy: TODO
View teardown behavior: TODO
```

The Apps bridge method `ui/initialize` is not the removed core MCP Legacy `initialize` handshake. Core MCP remains `2026-07-28` Modern and request-scoped. Keep View↔Host Apps messages logically separate from Host↔MCP-server core traffic.

The View acts through Host-mediated capabilities; it does not receive unrestricted access to Host DOM state, cookies, storage, credentials, or arbitrary MCP servers.

## Sandbox and browser security

```text
Sandbox policy: TODO
CSP resource/connect domain policy: TODO
Requested browser permissions: TODO or NONE
Dedicated-origin policy: TODO
Navigation/open-link policy: TODO
Clipboard/download policy: TODO
Credential exposure policy: TODO
```

Treat App HTML and JavaScript as untrusted relative to the Host. The Host sandbox and bridge are security boundaries, not presentation details. Declare only the network/resource origins and browser permissions actually required by the View. Avoid wildcard origins, hidden credential forwarding, and direct dependence on Host-private browser state.

## Failure and degradation behavior

```text
UI resource load failure: TODO
Bridge initialization failure: TODO
Tool-call failure presentation: TODO
Host capability loss or denial: TODO
Reload/retry policy: TODO
```

A broken View must not falsify the underlying MCP tool result. Distinguish UI-rendering failure, Host bridge failure, MCP transport/protocol failure, and a negative domain result.

## Standalone Web interface boundary

MCP Apps support does not select the `browser-interface` profile and does not require `WEB_INTERFACE.md`. Select `browser-interface` separately only when the Skill intentionally exposes a standalone browser-facing page outside the Host-embedded MCP App lifecycle.

If the same frontend code can run both as an MCP App and as a standalone Web interface, both contracts remain active and must define which security, routing, authentication, and capability assumptions differ between the two contexts.

## Required tests

When MCP Apps is selected, test at least:

- extension advertisement/selection for `io.modelcontextprotocol/ui`;
- every declared `ui://` resource and its exact media type;
- every tool-to-UI resource association;
- model-visible, app-visible, and app-only visibility rules that are claimed;
- meaningful core fallback when the Host does not support Apps, unless the contract explicitly requires Apps;
- `content` and `structuredContent` behavior used by the View;
- the View `ui/initialize` bridge lifecycle without reintroducing core Legacy initialization;
- allowed and denied App-mediated tool calls;
- CSP, requested permissions, sandbox assumptions, and denied undeclared origins/permissions;
- View load/bridge failure without corruption of the core tool result;
- redaction of credentials and sensitive result fields;
- teardown and cancellation behavior applicable to the selected Host bridge.

## Decision rationale

Explain why the operation benefits from an MCP App instead of core text/structured results alone, why the chosen resource and visibility model is minimal, how non-App Hosts behave, and why any requested browser capability is necessary.

```text
Rationale: TODO
```
