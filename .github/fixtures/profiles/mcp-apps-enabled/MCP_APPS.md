# MCP Apps extension contract

## Status and authority

Selection status: SELECTED
Extension identifier: io.modelcontextprotocol/ui
Extension specification revision: 2026-01-26
Core MCP revision: see RUNTIME.md

The Apps revision is independent of the core MCP `2026-07-28` revision. The server advertises the Apps extension settings through core `capabilities.extensions`; the Host activates Apps behavior only when its own capability map includes `io.modelcontextprotocol/ui` with `text/html;profile=mcp-app` support.

## Host capability and fallback

Host capability requirement: `capabilities.extensions.io.modelcontextprotocol/ui.mimeTypes` contains `text/html;profile=mcp-app`.
Behavior when the Host does not advertise MCP Apps: The Host ignores Apps-specific metadata and presents the ordinary `text_stats` core MCP result.
Behavior when the Host advertises an unsupported Apps revision: The Host does not activate this fixture's Apps View; core MCP remains usable.
Core-tool fallback: `text_stats` always returns textual `content` plus the same `structuredContent` whether or not Apps is active.

## UI resource inventory

| App/View | Resource URI | MIME type | Source or generator | Associated tools |
|---|---|---|---|---|
| Text statistics result | `ui://text-stats/result` | `text/html;profile=mcp-app` | `mcp/apps/result.html` | `text_stats` |

The resource is bundled HTML5 and contains no external URL dependency. Its read result carries `_meta.ui` with empty connect, resource, frame, and base-URI domain arrays, empty requested browser permissions, and `prefersBorder: true`.

## Tool-to-UI linkage

Tool metadata key: _meta.ui.resourceUri
Association policy: `text_stats` declares `_meta.ui.resourceUri: ui://text-stats/result`; tests require that exact resource to be discoverable and readable with the Apps MIME type.
Unknown or missing UI resource behavior: Treat the App presentation as unavailable and preserve the core tool result; do not fabricate a View or inject result HTML.

## Tool visibility and invocation

Default model/app visibility policy: `text_stats` is visible to both `model` and `app`.
App-only tool policy: `refresh_stats` declares `visibility: ["app"]`; the Host excludes it from model-visible inventory but may invoke it from this same server for the initialized App.
Model-only tool policy: `model_summary` declares `visibility: ["model"]`; the Host rejects an App-mediated call to it.
Cross-server invocation policy: App-mediated use of an app-only tool on a different MCP server is rejected by the Host evidence model.
User confirmation policy for mutating App actions: NOT APPLICABLE; every fixture tool is read-only and deterministic.

Visibility is a Host policy and not an authorization bypass. The raw server `tools/list` response retains the extension metadata, while the Host derives the appropriate model and App views.

## Result and presentation data

Core text/content fallback: The primary tool emits a JSON text summary in `content` for every Host.
structuredContent policy: The primary and helper tools emit `{bytes, lines, words}` as non-negative integer JSON fields for direct rich presentation.
Sensitive-field redaction policy: NOT APPLICABLE; the fixture accepts only caller-supplied text and returns aggregate counts without credentials or hidden state.
Large-data policy: The View receives only the small aggregate `structuredContent`; it does not receive or persist the original text through Apps-specific metadata.

## View and Host bridge lifecycle

View initialization behavior: `mcp/apps/result.html` sends a JSON-RPC `ui/initialize` request containing `appCapabilities.availableDisplayModes: ["inline"]`, waits for the Host response, then sends `ui/notifications/initialized`.
Host bridge transport: JSON-RPC over postMessage
App-to-Host tool-call policy: The Host evidence model permits only app-visible tools on the same MCP server and rejects model-only or cross-server calls.
Host-to-View result/update policy: After bridge initialization completes, the Host may send `ui/notifications/tool-result` with the standard core tool result; the View renders `structuredContent`.
View teardown behavior: The fixture holds no persistent View state or external resource; closing the Host/View context discards bridge state without changing the MCP server result.

The Apps `ui/initialize` / `ui/notifications/initialized` lifecycle is independent of the removed core Legacy `initialize` / initialized notification. Core traffic remains Modern `2026-07-28` throughout.

## Sandbox and browser security

Sandbox policy: The View is treated as untrusted Host-embedded HTML and receives only the Apps postMessage bridge; no parent DOM or Host-private state access is part of the contract.
CSP resource/connect domain policy: All declared connect, resource, frame, and base-URI domain lists are empty; undeclared external origins are denied.
Requested browser permissions: NONE
Dedicated-origin policy: NONE; the fixture requests no dedicated domain and no external origin.
Navigation/open-link policy: NOT SUPPORTED; the View contains no navigation or external link behavior.
Clipboard/download policy: NOT SUPPORTED; the View requests no clipboard or download capability.
Credential exposure policy: No credentials, cookies, tokens, authorization headers, or Host storage are exposed to the View.

## Failure and degradation behavior

UI resource load failure: Mark App presentation unavailable and keep the already returned core tool result usable.
Bridge initialization failure: Do not send Host requests or notifications to the View before the initialized notification; report the bridge failure separately from the tool result.
Tool-call failure presentation: Preserve the MCP tool failure/result classification and present it as a View state only after bridge initialization.
Host capability loss or denial: Stop Apps-specific interaction and continue to treat `text_stats` as an ordinary core MCP tool when possible.
Reload/retry policy: A new View creates a new bridge lifecycle; it does not retry or mutate the core tool call implicitly.

## Standalone Web interface boundary

This fixture does not select `browser-interface` and intentionally has no `WEB_INTERFACE.md`. `mcp/apps/result.html` is a Host-embedded MCP App View, not a standalone browser page, network listener, or fallback route.

The HTML file is therefore governed by this Apps contract and Host sandbox assumptions. Reusing it as a normal Web page would require a separate `browser-interface` selection and a `WEB_INTERFACE.md` contract.

## Required tests

`tests/test_mcp_apps.mjs` verifies extension advertisement, the exact `ui://` resource/MIME pair, restrictive resource metadata, `_meta.ui.resourceUri`, model/app/app-only visibility, same-server app-only call permission, model-only and cross-server denial, core fallback for a Host without Apps capability, required `appCapabilities` in `ui/initialize`, the initialized-notification gate, Apps revision response, and `ui/notifications/tool-result` delivery after initialization.

It also checks that the bundled View contains the Apps bridge lifecycle methods and no external HTTP/HTTPS URL. Core MCP executable behavior is provided by the official TypeScript SDK v2 on Modern stdio.

## Decision rationale

Rationale: Aggregate text statistics are useful as ordinary structured MCP data and also benefit from a small embedded presentation. The fixture therefore demonstrates progressive enhancement with one static sandboxed View, no external origin or browser permission, one app-only refresh helper, and an explicit model-only denial case. The core result remains complete without Apps, making the extension optional rather than a hidden requirement.
