# MCP 2026-07-28 conformance matrix

This source-maintainer record traces the unpublished Skill template's MCP baseline to the official MCP `2026-07-28` specification. It is not copied into downstream Skills. The official specification for the selected revision is normative; this matrix is only a maintenance index.

## Authority

Normative source: `https://modelcontextprotocol.io/specification/2026-07-28/`

SDK behavior is implementation evidence, not a substitute for the protocol specification. The current representative fixture should use an official SDK path that explicitly supports `2026-07-28` Modern behavior.

## Baseline decisions

- Core protocol revision: `2026-07-28` only.
- Protocol era: Modern only.
- Legacy revisions (`2025-11-25` and earlier): not supported by the initial unpublished template.
- Automatic era fallback: not supported.
- Deprecated Roots, Sampling, Logging, and HTTP+SSE: not advertised by new representative implementations.
- Optional extensions: capability-gated and versioned independently from the core protocol.

## Requirement traceability

| Area | Normative level | Applies when | Template contract | Validation/evidence |
|---|---|---|---|---|
| Every request declares protocol version in `_meta` | core requirement | every Modern request | `RUNTIME.md`, `MCP_INTERFACE.md` | `validate_mcp_protocol_conformance.py`; representative fixture |
| HTTP also carries `MCP-Protocol-Version` matching body metadata | MUST | Streamable HTTP | `RUNTIME.md`, `MCP_INTERFACE.md`, `docs/mcp-transports.md` | semantic validator plus HTTP fixture when selected |
| Unsupported revision returns `UnsupportedProtocolVersionError` | MUST | server | `RUNTIME.md`, `MCP_INTERFACE.md` | semantic validator; representative fixture |
| Server implements `server/discover` | MUST | server | `RUNTIME.md`, `MCP_INTERFACE.md` | semantic validator; representative fixture |
| Client may call `server/discover` before other requests | MAY | client | `MCP_INTERFACE.md` | client fixture when bundled client is selected |
| Extensions use `capabilities.extensions` | core requirement | extension selected | `RUNTIME.md`, `MCP_INTERFACE.md` | extension validator introduced with extension contracts |
| Unsupported extension falls back to core behavior or rejects | MUST | extension mismatch | `MCP_INTERFACE.md` and extension contract | extension-specific evidence |
| Streamable HTTP has one POST-capable MCP endpoint | MUST | Streamable HTTP server | `RUNTIME.md`, `docs/mcp-transports.md` | HTTP fixture when selected |
| Every JSON-RPC client message uses a new POST | MUST | Streamable HTTP client | `RUNTIME.md`, `MCP_INTERFACE.md` | HTTP client evidence when selected |
| Client Accept lists JSON and SSE | MUST | Streamable HTTP client | `RUNTIME.md`, `MCP_INTERFACE.md` | HTTP client evidence when selected |
| Request response supports JSON or request-scoped SSE | MUST | Streamable HTTP | `RUNTIME.md`, `MCP_INTERFACE.md` | HTTP fixture when selected |
| Closing request SSE cancels that request; no later messages | MUST / SHOULD stop promptly | Streamable HTTP SSE | `RUNTIME.md`, `MCP_INTERFACE.md` | cancellation evidence when selected |
| `Mcp-Method` required; `Mcp-Name` conditionally required | REQUIRED | Streamable HTTP requests | `RUNTIME.md`, `MCP_INTERFACE.md` | HTTP header evidence when selected |
| `x-mcp-header` annotations validated by Streamable HTTP clients | MUST for conforming client | bundled HTTP client selected | `RUNTIME.md`, `MCP_INTERFACE.md` | bundled-client evidence when selected |
| Origin validation and HTTP 403 for invalid present Origin | MUST | Streamable HTTP server | `RUNTIME.md`, `MCP_INTERFACE.md`, `docs/mcp-transports.md` | negative security evidence when selected |
| Protocol-level sessions removed | core change | Modern Streamable HTTP | `RUNTIME.md`, `MCP_INTERFACE.md` | semantic validator; absence evidence |
| GET stream and session DELETE removed | core change | Modern Streamable HTTP | `RUNTIME.md`, `MCP_INTERFACE.md` | semantic validator; absence evidence |
| Resumable SSE via `Last-Event-ID` unsupported | core requirement | Modern Streamable HTTP | `RUNTIME.md`, `docs/mcp-transports.md` | absence evidence |
| Long-lived changes use `subscriptions/listen` | core requirement | change notifications selected | `RUNTIME.md`, `MCP_INTERFACE.md` | feature-specific evidence |
| Server-to-client interaction uses MRTR `input_required` | core requirement | additional input selected | `MCP_INTERFACE.md` | interaction evidence when selected |
| Results carry revision-appropriate `resultType` | core requirement | Modern results | `MCP_INTERFACE.md` | result-preservation tests |
| Roots, Sampling, Logging deprecated | deprecation | new implementations | `RUNTIME.md`, `MCP_INTERFACE.md` | deprecated-feature policy |

## Normative keyword policy

Validators may hard-fail an official MUST or MUST NOT when its applicability is mechanically knowable. SHOULD and SHOULD NOT requirements are not silently promoted to protocol MUSTs; the template may nevertheless choose a stricter initial product policy when that choice is stated explicitly. MAY requirements remain capability choices.

Conditional protocol requirements are activated only by the corresponding transport, role, capability, or extension selection. A server-only Skill is not required to implement client-only Streamable HTTP header mirroring, and a Skill that does not select subscriptions is not required to expose `subscriptions/listen`.

## Maintenance rule

When a later MCP core revision becomes the template baseline, update the official-source review, this matrix, `RUNTIME.md`, `MCP_INTERFACE.md`, transport guidance, validators, and executable evidence in one coordinated change. Do not claim support for a new revision by editing the revision string alone.
