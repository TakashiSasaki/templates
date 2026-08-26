# MCP Apps extension contract

This contract is materialized by `capability.mcp-apps`, which requires `capability.mcp`. MCP Apps is an optional MCP extension and is not the standalone browser interface governed by `WEB_INTERFACE.md`.

`contracts/mcp-interface.json` owns the selected core MCP revision and core transport/operation inventory. `RUNTIME.md` owns runtime/SDK and implementation/deployment choices. `MCP_INTERFACE.md` owns qualitative core MCP behavior. This file owns the Apps extension revision and Apps-specific caller-, Host-, and View-visible behavior.

## Status and authority

```text
Selection status: UNSELECTED
Extension identifier: io.modelcontextprotocol/ui
Extension specification revision: 2026-01-26
Core MCP revision: see contracts/mcp-interface.json
```

Change the status to `SELECTED` only when every retained Apps behavior is concrete and evidence covers the claimed extension behavior.

## Host capability and fallback

```text
Host capability requirement: TODO
Behavior when the Host does not advertise MCP Apps: TODO
Behavior when the Host advertises an unsupported Apps revision: TODO
Core-tool fallback: TODO
```

MCP Apps is progressive enhancement unless the operation explicitly requires an App-capable Host.

## UI resource inventory

Every selected App View is an MCP resource with a stable `ui://` URI.

| App/View | Resource URI | MIME type | Source/generator | Associated tools |
|---|---|---|---|---|
| TODO | `ui://TODO` | `text/html;profile=mcp-app` | TODO | TODO |

Resource URIs are public protocol identifiers, not filesystem paths. Build/distribution layout remains a runtime concern.

## Tool-to-UI linkage

```text
Tool metadata key: _meta.ui.resourceUri
Association policy: TODO
Unknown/missing UI resource behavior: TODO
```

Every advertised association must resolve to a declared App resource.

## Visibility and invocation

```text
Default model/app visibility policy: TODO
App-only tool policy: TODO or NOT SUPPORTED
Model-only tool policy: TODO or NOT SUPPORTED
Cross-server invocation policy: TODO
User confirmation policy for mutating App actions: TODO
```

Visibility is not authorization. Host authorization, user consent, and cross-server isolation still apply.

## Results and presentation

```text
Core content fallback: TODO
structuredContent policy: TODO
Sensitive-field redaction policy: TODO
Large-data policy: TODO
```

Keep presentation resources separate from dynamic results. A View must not become the only copy of a meaningful result unless the operation explicitly requires an App-capable Host.

## View/Host bridge lifecycle

```text
View initialization behavior: TODO
Host bridge transport: JSON-RPC over postMessage
App-to-Host tool-call policy: TODO
Host-to-View result/update policy: TODO
View teardown behavior: TODO
```

The Apps `ui/initialize` bridge lifecycle is distinct from core MCP protocol initialization semantics. Keep View↔Host messages separate from Host↔MCP-server traffic.

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

Treat App HTML/JavaScript as untrusted relative to the Host. Declare only required origins and permissions. Avoid wildcard origins and hidden credential forwarding.

## Failure and degradation

```text
UI resource load failure: TODO
Bridge initialization failure: TODO
Tool-call failure presentation: TODO
Host capability loss/denial: TODO
Reload/retry policy: TODO
```

A broken View must not falsify the underlying MCP result. Distinguish UI rendering, bridge, MCP transport/protocol, and domain failures.

## Standalone Web boundary

MCP Apps does not select `capability.web-interface`. A Host-embedded View and a standalone Web page have different trust, routing, lifecycle, and capability boundaries. Shared frontend code is acceptable only when environment-specific adapters and contracts remain distinct.

## Required tests

Test at least:

- extension selection/advertisement;
- every declared `ui://` resource and media type;
- every tool-to-UI association;
- claimed visibility rules;
- core fallback when Apps is unavailable unless Apps is required;
- View bridge lifecycle;
- allowed/denied App-mediated calls;
- CSP, sandbox, permissions, and denied undeclared origins;
- View/bridge failure without corruption of core results;
- credential/sensitive-field redaction;
- teardown/cancellation.

## Decision rationale

Explain why the operation benefits from an MCP App, why the resource/visibility model is minimal, how non-App Hosts behave, and why every requested browser capability is necessary.

```text
Rationale: TODO
```
