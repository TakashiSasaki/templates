# WebMCP capability

`capability.webmcp` is an independent optional Composition capability for exposing meaningful product operations to browser agents through WebMCP.

## Scope and authority

Composition owns the product contract: which WebMCP interface profile the consumer promises, which domain tools exist, where they apply, their effect and output-trust classifications, and the evidence required to substantiate those claims. The upstream WebMCP specification remains the browser API authority and is not copied into this contract.

Selecting Website or Webapp does not select WebMCP. Selecting WebMCP does not select MCP, MCP Apps, runtime, or standalone Web interface.

Consumer selection is the only adoption authority:

- `components.include` containing `capability.webmcp` means explicit adoption.
- `components.exclude` containing `capability.webmcp` means explicit non-adoption.
- neither means unspecified/default intent.

There is deliberately no `enabled` flag in either WebMCP contract.

## v1 profile

The v1 product profile is imperative WebMCP through `document.modelContext`. Declarative WebMCP is informative/experimental and is not a v1 product promise. Unsupported browsers must follow the declared fallback behavior without implying WebMCP support.

Registration lifetime is scoped with an abort signal so stale registrations can be removed when route, state, identity, or owning UI lifetime changes. Tool execution failure and cancellation must remain observable failure paths rather than being converted into successful results.

## Tool inventory

Tools represent stable domain capabilities and user intent, not UI controls. Stable Composition tool `id` and caller-visible WebMCP `name` are separate identities. Each tool declares an input contract, effect classification, output trust, route/state applicability, and confirmation semantics.

WebMCP annotations and browser hints may mirror product metadata, but they are not security authority. Product-owned classifications remain normative and validators/evidence should detect divergence.

## Security invariant

WebMCP tool execution MUST NOT bypass product authorization, validation, confirmation requirements, state-transition rules, or externally observable side-effect semantics.

When Human UI, REST/API, MCP, WebMCP, or CLI expose the same domain operation, implementations should converge on the same domain/application operation instead of implementing separate business semantics inside a WebMCP callback.

Authenticated browser state may make a tool convenient, but session inheritance is never authorization by itself. Every invocation must enforce the same authorization and validation that the underlying operation requires.

Treat tool descriptions/metadata and untrusted tool output as injection surfaces. Sensitive input/output must be minimized and protected at the product boundary. Consequential operations require the domain operation's confirmation semantics even if a caller or annotation suggests otherwise.

## Origin exposure

Same-origin is the default. Cross-origin exposure is allowed only when the interface contract selects `cross-origin-allowlist`, supplies a non-empty HTTPS origin allowlist, and the implementation correctly applies WebMCP's `tools` Permissions Policy and registration exposure controls. Evidence must prove both allowed discovery and denied-origin behavior.

## Evidence

This capability uses the shared `lifecycle.implementation-evidence` system; it does not create a WebMCP-specific evidence ledger. Tool contract items are stable evidence targets, including positive discovery/invocation/domain-behavior proofs and negative invalid-input, unauthorized, unavailable-state, cancellation/failure, consequential-action, untrusted-output, and cross-origin-denial proofs where applicable. Browser-facing support claims require browser/end-to-end proof at the final product boundary.

## Upstream evolution

Do not add a consumer-selectable upstream WebMCP revision. Evolution is bound by the immutable Composition source revision, `capability.webmcp` component version, contract schema versions/history, migrations, and lifecycle evidence. An upstream breaking change that alters the product-visible promise requires corresponding Composition contract evolution.
