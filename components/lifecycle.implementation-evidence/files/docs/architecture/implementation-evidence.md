# Implementation evidence lifecycle

`lifecycle.implementation-evidence` provides an artifact-neutral mechanism connecting declared contracts to implementation boundaries, positive/negative proofs, authoritative commands, and release gates.

The generic contract does not know Webapp surfaces, routes, UI states, Skill resources, or any other artifact vocabulary. `contract-item` targets carry a contract ID plus artifact-defined `itemKind` and `itemId`; artifact validators own exact coverage rules.

Template mode is deliberately empty. A concrete product switches to product mode and records implementation evidence plus an explicit product requirement ledger.

Validation responsibilities are intentionally split rather than duplicated:

- the registered JSON Schema owns document structure and product-mode completeness, including the mandatory non-empty requirement ledger, mandatory proof-kind declaration for each requirement, verified implementation-boundary status, required proof metadata, and at least one selected release gate per product record;
- `validate_implementation_evidence.py` runs after registered-contract schema validation and owns semantic relationships that JSON Schema cannot express conveniently: unique identities, requirement-to-record references, proof-kind constraints, contract-target and transition existence, command/gate references, proof-command execution by selected gates, and unused command/gate detection;
- artifact validators own artifact-specific target coverage.

A product document that is structurally incomplete must therefore fail registered-contract schema validation before semantic evidence validation runs. The semantic validator mirrors the mandatory requirement-ledger and proof-kind-declaration rules because release-readiness validation can invoke the semantic path directly; it does not create a second authority.


## Explicit product requirements

Every product-mode document must declare at least one explicit requirement in the same canonical document:

```json
{
  "requirements": [
    {
      "id": "REQ-SEVERITY-BROWSER-FILTER",
      "description": "Browser UI can filter records by severity.",
      "recordIds": ["browser-severity-filter"],
      "requiredPositiveProofKinds": ["end-to-end-test", "accessibility-test"]
    }
  ]
}
```

Requirement IDs are stable machine-facing identifiers; their descriptions are intentionally opaque to Composition. Lowercase IDs remain valid, and uppercase hyphenated IDs such as `REQ-SEVERITY-BROWSER-FILTER` are also valid for requirement rows. Each requirement must reference at least one implementation-evidence record and must declare at least one sufficient positive proof kind. The existing record rules then close the graph through an implementation boundary, positive and negative proofs, authoritative commands, and a selected release gate.

The ledger is mandatory in product mode so that a consumer cannot evade traceability by omitting machine-readable intent altogether. The proof-kind declaration is also mandatory so that a consumer cannot evade evidence-strength validation by omitting the machine-readable minimum for a requirement. Composition still does not infer requirements or proof strength from prose: the human or coding agent must enumerate the product requirements and choose sufficient proof kinds. Template mode carries `requirements: []` and makes no product claims.


## Proof kind and deferred state

The existing `evidenceProof.kind` is the execution-strength classification; it is not a claim that every proof is browser-backed. Use `inspection` for static source/HTML/JSON inspection, `unit-test`, `integration-test`, or `migration-test` for executable process-level checks, and `end-to-end-test` or `accessibility-test` for browser interaction and keyboard/focus behavior. Artifact validators decide which kinds are sufficient for a target.

A product proof may be `deferred` when the required environment is unavailable. Deferred evidence is retained as an explicit incomplete state and may allow structural validation to describe the composition as valid, but release readiness rejects every non-`verified` proof. Static inspection must therefore never be silently promoted to browser interaction evidence.

Every product requirement declares `requiredPositiveProofKinds`. The validator checks only the declared proof-kind edge. For example, a CLI requirement can require `integration-test`, while a browser interaction requirement can require `end-to-end-test` or `accessibility-test`. This prevents a static `inspection` proof from satisfying a caller-visible interactive requirement without making Composition infer product semantics from requirement prose. When several kinds are acceptable, list each acceptable kind; when a required environment is unavailable, keep the corresponding proof `deferred` rather than weakening the declared requirement.
