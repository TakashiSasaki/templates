# WebMCP testing and implementation evidence

`capability.webmcp` reuses `lifecycle.implementation-evidence`. It does not define a separate evidence ledger.

For every declared WebMCP tool, the deterministic target identity is:

```text
contract-item / webmcp_tools / tool / <stable tool id>
```

## Required proof coverage

A product WebMCP claim should include executable proof for:

Positive paths:
- discovery in each applicable route/state;
- valid invocation against the declared input contract;
- expected shared domain/application behavior.

Negative paths:
- malformed or schema-invalid input;
- unauthenticated/unauthorized invocation where relevant;
- unavailable route/state and stale-registration behavior;
- execution failure and cancellation;
- consequential-action confirmation guard;
- untrusted-output handling where `outputTrust` is `untrusted`;
- denied-origin discovery/invocation whenever cross-origin exposure is declared.

Cross-origin products additionally require a positive allowed-origin discovery proof and a negative denied-origin proof.

## Browser boundary

WebMCP is a browser-facing public claim. Unit/contract tests are useful intermediate evidence, but final support claims require an execution capability that exercises the real browser boundary, normally an end-to-end browser test. Tests must verify the actual registered tool inventory rather than only application helper functions.

## Annotation consistency

If an implementation emits upstream tool annotations/hints, test that they are consistent with the templates-owned effect/trust semantics. The hints never replace product authorization or evidence.
