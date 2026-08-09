# MCP Apps implementation guidance

Use this guide only when a concrete Skill selects the MCP Apps extension `io.modelcontextprotocol/ui`. The extension is versioned independently from MCP core: the initial template uses core MCP `2026-07-28`, while `MCP_APPS.md` records the selected MCP Apps specification revision.

`MCP_APPS.md` is the public extension contract. This document is maintainer-oriented implementation guidance.

## Architecture boundary

Keep these channels distinct:

```text
MCP Server  <--- core MCP 2026-07-28 --->  MCP Host
                                              |
                                              | Host-controlled bridge
                                              | JSON-RPC over postMessage
                                              v
                                      sandboxed MCP App View
```

The MCP Server remains a standard MCP server. The View is HTML/JavaScript rendered in a Host-controlled sandbox. The Host proxies only capabilities it intentionally exposes. Do not treat the View as trusted Host code.

## Core and extension versioning

Do not encode the Apps revision in the core protocol-version field. Core and extension revisions have different authorities and may change independently.

```text
Core MCP revision:        see RUNTIME.md
MCP Apps extension ID:    io.modelcontextprotocol/ui
MCP Apps spec revision:   see MCP_APPS.md
```

Core `server/discover` and per-request metadata remain governed by MCP `2026-07-28`. The Apps `ui/initialize` View↔Host lifecycle is a separate bridge operation and does not restore the removed Legacy core `initialize` session.

## UI resources

Expose each View as an MCP resource with a stable `ui://` URI. For the initial Apps contract, use the selected Apps specification's MCP App HTML media type, `text/html;profile=mcp-app`.

Keep the resource identifier stable even if the source file, bundler, or generated asset layout changes. `RUNTIME.md` owns build and distribution choices; `MCP_APPS.md` owns the public URI and association behavior.

A bundled source layout may use:

```text
mcp/
  apps/
    README.md
    <app implementation files>
```

but the protocol URI must not be inferred from that filesystem path.

## Tool association

Associate a tool with its View through the selected Apps metadata contract, including `_meta.ui.resourceUri` for the stable Apps revision used by this template.

Do not rely on the Host scraping tool descriptions or guessing a UI resource. Every association should be explicit, resolvable, and testable.

## Visibility

Model visibility and App visibility are separate concerns. Use the selected Apps visibility metadata deliberately:

- model + app: ordinary tools that both the model and the View may invoke;
- app-only: UI implementation helpers that should not appear in the model-visible tool inventory;
- model-only where supported/needed: operations intentionally unavailable to the View.

App-only visibility is not authorization. The Host still enforces which server, tool, identity, and user-approved action the View may invoke.

## Results and progressive enhancement

Prefer a progressive-enhancement design:

- `content` gives the model and non-App Hosts a meaningful core result;
- `structuredContent` carries JSON suitable for richer presentation;
- the UI resource supplies presentation and interaction code.

Do not make the only copy of an important result available inside the View. If the Host cannot render Apps, the caller should still be able to understand or use the core result unless the operation contract explicitly requires an App-capable Host.

## View↔Host bridge

The View communicates with the Host through the Apps bridge rather than calling arbitrary MCP endpoints directly. Keep the bridge bounded:

- perform the Apps `ui/initialize` lifecycle required by the selected extension revision;
- send only declared App requests and notifications;
- let the Host mediate MCP tool calls and user consent;
- do not read Host DOM state, cookies, local storage, or credentials outside the bridge contract;
- handle Host denial as an explicit failure state.

## Sandbox, CSP, and permissions

Minimize browser authority. Declare only required resource/connect domains and browser permissions. Treat wildcard CSP origins and broad camera, microphone, or clipboard permissions as exceptional design decisions requiring explicit rationale and tests.

The Host sandbox protects both sides. A View should assume it cannot navigate the parent document, reach arbitrary network origins, or inspect Host-private browser state.

## Standalone browser UI

Do not reuse `WEB_INTERFACE.md` as the MCP Apps contract. A Host-embedded MCP App and a standalone Web page have different trust, routing, lifecycle, and capability boundaries.

Select `browser-interface` only when a standalone browser surface is intentional. Shared frontend code is acceptable, but each execution context must satisfy its own contract.

## Evidence

Protocol-level evidence should verify server-side extension declaration, resource metadata, tool association, fallback, and visibility semantics without depending on a specific commercial Host implementation.

End-to-end Host evidence may additionally verify iframe sandboxing, bridge initialization, postMessage routing, CSP/permission enforcement, user consent, rendering, and teardown. Keep protocol conformance evidence separate from Host-specific UX evidence.
