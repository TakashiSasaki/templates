# MCP Apps implementation guidance

This guidance accompanies `capability.mcp-apps`.

## Architecture boundary

Keep these channels distinct:

```text
MCP Server  <--- core MCP --->  MCP Host
                                |
                                | Host-controlled bridge
                                | JSON-RPC over postMessage
                                v
                         sandboxed MCP App View
```

The MCP Server remains a standard MCP server. The View is HTML/JavaScript rendered in a Host-controlled sandbox. The Host proxies only intentionally exposed capabilities.

## Machine authority

`contracts/mcp-apps.json` owns the product Apps extension declaration, stable `ui://` View resource inventory, and tool-to-View associations. Each association references a stable core MCP tool-operation ID from `contracts/mcp-interface.json`; prose or source-code adjacency is not an association authority.

The contract intentionally separates three evidence families:

- extension advertisement/fallback: protocol-executable proof;
- View rendering/degradation: browser-level proof;
- core tool → View linkage: end-to-end proof.

This prevents static resource inspection from proving browser behavior and prevents a tool metadata assertion from proving that the Host actually routes the result to the declared View.

## Core and extension versioning

Core MCP and MCP Apps revisions have separate authorities. Do not encode the Apps revision in the core protocol-version field. The Apps `ui/initialize` View↔Host lifecycle does not redefine the core server lifecycle.

## UI resources

Expose each View as a stable `ui://` MCP resource with the declared `text/html;profile=mcp-app` media type. Keep the public resource identifier stable even when the source path, bundler, or generated asset layout changes. Every product View must be referenced by at least one declared tool association.

## Tool association and visibility

Associate a core MCP **tool** operation with a View explicitly in `contracts/mcp-apps.json`. A resource, prompt, protocol helper, missing operation, or duplicated association is not a valid substitute.

Model visibility, App visibility, and authorization are separate concerns. App-only implementation helpers must not accidentally become model-visible, and App visibility never bypasses Host authorization or user consent.

## Results and progressive enhancement

Prefer:

- core `content` for meaningful non-App fallback;
- `structuredContent` for structured dynamic data;
- an App resource for presentation and interaction.

Do not make a View the only copy of important result data unless the operation explicitly requires Apps. Negative proof should show that View/Host failure does not falsify the core result.

## View↔Host bridge

The View uses the Host bridge rather than arbitrary direct MCP access. Keep the bridge bounded, handle Host denial explicitly, and do not access Host DOM, cookies, storage, or credentials outside the bridge contract.

## Sandbox, CSP, and permissions

Minimize browser authority. Declare only required resource/connect origins and browser permissions. Treat wildcard CSP origins and broad camera/microphone/clipboard authority as exceptional decisions requiring rationale and tests.

## Standalone browser UI

`capability.web-interface` is a different execution context. Shared frontend code is acceptable, but each context must satisfy its own routing, lifecycle, authentication, CSP, and capability contract.

## Evidence completion

If a real Host/browser environment is unavailable, keep the applicable View or association proof `deferred`. Do not replace it with source inspection and do not claim release readiness. Generic implementation-evidence/release validation remains responsible for blocking deferred proof from a release-ready state.
