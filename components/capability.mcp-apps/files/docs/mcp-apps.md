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

## Core and extension versioning

Core MCP and MCP Apps revisions have separate authorities. Do not encode the Apps revision in the core protocol-version field. The Apps `ui/initialize` View↔Host lifecycle does not redefine the core server lifecycle.

## UI resources

Expose each View as a stable `ui://` MCP resource. Keep the public resource identifier stable even when the source path, bundler, or generated asset layout changes.

## Tool association and visibility

Associate a tool with a View explicitly through the selected Apps metadata contract. Model visibility, App visibility, and authorization are separate concerns.

App-only implementation helpers must not accidentally become model-visible. App visibility never bypasses Host authorization or user consent.

## Results and progressive enhancement

Prefer:

- core `content` for meaningful non-App fallback;
- `structuredContent` for structured dynamic data;
- an App resource for presentation and interaction.

Do not make a View the only copy of important result data unless the operation explicitly requires Apps.

## View↔Host bridge

The View uses the Host bridge rather than arbitrary direct MCP access. Keep the bridge bounded, handle Host denial explicitly, and do not access Host DOM, cookies, storage, or credentials outside the bridge contract.

## Sandbox, CSP, and permissions

Minimize browser authority. Declare only required resource/connect origins and browser permissions. Treat wildcard CSP origins and broad camera/microphone/clipboard authority as exceptional decisions requiring rationale and tests.

## Standalone browser UI

`capability.web-interface` is a different execution context. Shared frontend code is acceptable, but each context must satisfy its own routing, lifecycle, authentication, CSP, and capability contract.

## Evidence

Protocol-level evidence should establish extension declaration, resources, tool association, fallback, and visibility without depending on a particular commercial Host. Host-specific end-to-end evidence may additionally cover sandboxing, bridge routing, permissions, rendering, user consent, and teardown.
