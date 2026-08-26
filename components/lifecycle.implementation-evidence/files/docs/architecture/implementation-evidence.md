# Implementation evidence lifecycle

`lifecycle.implementation-evidence` provides an artifact-neutral mechanism connecting explicit product requirements and declared contracts to implementation boundaries, positive/negative proofs, authoritative commands, and release gates.

The generic contract does not know Webapp surfaces, routes, UI states, Skill resources, or any other artifact vocabulary. `contract-item` targets carry a contract ID plus artifact-defined `itemKind` and `itemId`; artifact validators own exact coverage and minimum proof-strength rules.

Template mode is deliberately empty. A concrete product switches to product mode, declares every explicit product requirement, and records implementation evidence.

Validation responsibilities are intentionally split rather than duplicated:

- the registered JSON Schema owns document structure and product-mode completeness, including the mandatory requirement ledger, implementation-boundary/proof fields, proof kind/command/expected-result fields, and selected release gates;
- `validate_implementation_evidence.py` owns semantic relationships that JSON Schema cannot express conveniently: unique identities, requirement → record references, contract-target and transition existence, command/gate references, proof-command execution by selected gates, and unused command/gate detection;
- artifact validators own artifact-specific target coverage and minimum proof strength;
- release readiness is stricter than structural validity and rejects deferred or otherwise non-verified mandatory proof.

A product document that is structurally incomplete must therefore fail registered-contract validation before release production. Structural validation may retain explicitly deferred proof so that an unavailable environment is distinguishable from malformed evidence; that state is not release-ready.

## Explicit product requirements

Product mode requires a machine-readable requirement ledger in the same canonical document:

```json
{
  "requirements": [
    {
      "id": "REQ-SEVERITY-BROWSER-FILTER",
      "description": "Browser UI can filter records by severity.",
      "recordIds": ["browser-severity-filter"]
    }
  ]
}
```

Requirement IDs are stable machine-facing identifiers; their descriptions are intentionally opaque to Composition. Each requirement references at least one implementation-evidence record. Existing record rules then close the graph through implementation boundaries, positive/negative proofs, authoritative commands, and release gates.

This requirement ledger is not a second product-specification authority. It is the explicit-intent entry point to the existing implementation-evidence lifecycle. Humans or agents must still enumerate the real requirements; Composition does not infer omitted natural-language intent.

## Proof kind and deferred state

The existing `evidenceProof.kind` is the proof-strength/execution classification. Use `inspection` for static source/HTML/JSON inspection, `unit-test`, `integration-test`, or `migration-test` for executable non-browser checks, and `end-to-end-test` or `accessibility-test` when artifact-specific rules require real browser interaction such as keyboard/focus or viewport behavior.

A product proof may be `deferred` when the required environment is unavailable. Deferred evidence is retained as an explicit incomplete state and may allow structural validation to describe the composition as valid, but release readiness rejects every non-`verified` proof. Static inspection must therefore never be silently promoted to browser interaction evidence.
