# Optional human verification Web interface

## Status and purpose

Supported: YES
Purpose: local verification and limited read-only operation
Default enablement: explicitly enabled
Production policy: disabled

The interface exists only for local verification. It is not loaded until the startup command receives `TEXT_STATS_WEB_ENABLED=1`.

## Deployment authority

Deployment topology: see RUNTIME.md
Listener and port model: see RUNTIME.md
External-origin model: see RUNTIME.md
Deployment selection time: see RUNTIME.md

`RUNTIME.md` is authoritative for the process, listener, port, enablement, PID file, and shutdown commands.

## Public routing

External base URL: http://127.0.0.1:4567
Web UI path or URL: `/`
UI backend API path or URL: `/api/text-stats`
MCP endpoint visible to the browser: NO
MCP endpoint used by the UI backend: NOT APPLICABLE; the UI uses a non-MCP application API
Selected topology and listener model: see RUNTIME.md

The shared loopback listener also serves `/app.js`, `/app.css`, and `/healthz`. Unknown paths return JSON 404 responses. Known paths reject unsupported methods with HTTP 405 and an `Allow` header. Every request must use the active `127.0.0.1` or `localhost` Host value for the selected port.

## Relationship to MCP

UI interaction model:
- backend acts as an MCP client: NO
- browser calls MCP directly: NO
- UI uses a non-MCP application API: YES
- mixed model: NO

The page verifies the shared deterministic `TextStatsWeb.analyze` application behavior. It makes no claim to verify MCP negotiation, transport, discovery, readiness, or tool invocation.

## UI capabilities

Server information display: NO
Tool inventory display: NO
Input-schema form generation: NO; one fixed text field is rendered
Raw MCP request display: NO
Raw MCP result display: NO
Normalized result display: YES; byte, line, and word counts only
Transport and protocol diagnostics: NO
Cancellation and timeout controls: NO; the operation is local and bounded
Additional-input handling: NO
Trace or correlation information: NO

The page loads script and stylesheet resources from the same origin under a restrictive Content Security Policy. Client-side rendering uses text-only DOM assignment for results and errors.

## Human authorization and safety

Authentication: loopback network boundary; no application credential is accepted
Allowed users or network boundary: a local user on the same host through `127.0.0.1` or `localhost`
Read-only operations: load the page and assets, check Web readiness, and compute text statistics
Mutating operations: NONE
Destructive operations: NONE
Confirmation policy: no confirmation is required for the bounded read-only calculation
Sensitive argument masking: submitted text is never written to diagnostics or returned by the API
Sensitive result masking: only aggregate integer counts are returned and displayed
Audit logging: stderr records method, path, status, startup, and shutdown without headers or bodies

`POST /api/text-stats` accepts only `application/json`, requires an exact same-origin `Origin`, and accepts exactly one string field named `text`. Request bodies are consumed incrementally with a 65536-byte upper bound for both Content-Length and chunked transfer; an oversized request receives HTTP 413 with connection closure before additional protocol messages are accepted. Cross-origin requests receive HTTP 403. Invalid encoding, JSON, media type, or schema receives a bounded 4xx response. No CORS permission header is emitted.

Every response sets no-store caching, content-type sniffing protection, frame denial, no-referrer policy, and a Content Security Policy that permits only same-origin script, style, and API connections.

## Lifecycle and failure isolation

Start, stop, and readiness commands: see RUNTIME.md
Enablement configuration: see RUNTIME.md
Web health behavior: `GET /healthz` returns only `{"ok":true,"interface":"web"}` when the Web listener and router can answer
MCP readiness check: NOT APPLICABLE; no MCP interface is selected
Failure relationship: shared process with isolated routing; request-validation and operation failures do not change Web readiness

The readiness endpoint does not execute the text-statistics operation and does not establish the health of any absent interface. A malformed or rejected API request remains request-scoped. The mode-0600 PID record includes the Linux process start identity. Startup refuses existing or symbolic-link records, and `--stop` refuses stale identity data rather than signaling an unrelated process. TERM and INT stop the listener, remove the owned record, and allow the process to be reaped without a background child.

## Shared implementation

The Web adapter calls `TextStatsWeb.analyze` from `src/text_stats.rb`. The browser page does not contain a second counting implementation or tool registry. The API adds the versioned browser response envelope and enforces routing, origin, input, size, and redaction policy before calling the shared operation.

## Required tests

The fixture tests establish:

- disabled-by-default startup and explicit enablement;
- rejection of non-loopback bind configuration;
- UI, asset, API, health, 404, and method routing;
- Host and same-origin enforcement;
- restrictive browser security headers;
- deterministic versioned success output without text echo;
- media-type, encoding, JSON, schema, Content-Length size, and chunked-transfer size failures;
- health success after request-scoped API failures;
- documented readiness and identity-verified PID-based stop commands;
- rejection of stale, pre-existing, or symbolic-link PID records;
- graceful signal shutdown, PID-record cleanup, and empty stdout;
- prompt failure when the selected fixed port is unavailable;
- complete repository validation and negative missing-contract or implementation cases.

## Decision rationale

A loopback-only, explicitly enabled page is sufficient for local human verification without creating a remotely reachable service or exposing MCP to browser code. The same-process topology keeps the fixture small while retaining separate UI, asset, API, and health routes with independent request policy. Same-origin enforcement, Host validation, body limits, response hardening, and no-body logging provide proportionate browser security. Disabling the interface in production avoids turning a verification surface into an unsupported operational service.
