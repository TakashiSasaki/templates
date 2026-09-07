# WebMCP security

WebMCP is an additional invocation surface, not a privileged path.

## Hard invariants

A WebMCP invocation must enforce the same product authorization, validation, state-transition, confirmation, and externally observable side-effect semantics as the corresponding human or API path. Authenticated browser session state supplies identity context; it does not replace per-operation authorization.

## Injection and trust

Tool names, descriptions, annotations, inputs, and outputs can influence agents. Treat third-party and user-controlled content as untrusted data. Product-owned `effect` and `outputTrust` fields are security-relevant classifications; browser annotations remain hints and cannot weaken them.

Prompt injection or tool poisoning in metadata must not grant permissions, suppress required confirmation, or change the operation being authorized. Untrusted tool output must not be interpreted as instructions to invoke unrelated tools or disclose sensitive data.

## Consequential actions

Consequential tools must retain the domain operation's confirmation semantics. Do not infer consent from agent prose, WebMCP annotations, prior unrelated interactions, or the presence of an authenticated session.

## Origin boundaries

Default exposure is same-origin. Cross-origin exposure requires an explicit HTTPS origin allowlist, the WebMCP `tools` Permissions Policy to permit the relationship, positive evidence that allowed origins can discover the intended tools, and negative evidence that denied origins cannot.

Never use wildcard-like product semantics as a shortcut for origin review. Registration metadata should expose the minimum origin surface required by the product contract.

## Stale registration and confused deputy risks

Registrations must be scoped to the owning route/state/session lifetime and unregistered when that lifetime ends. A stale tool must not retain authority that the current page state no longer has. The execute path must re-check applicability and authorization rather than trusting discovery-time state.

## Path divergence

Human UI and WebMCP can exercise different code paths even when they represent the same operation. Evidence must specifically test for divergence in validation, authorization, confirmation, and failure behavior; shared domain/application operations are the preferred architectural control.
