# Implementation evidence lifecycle

`lifecycle.implementation-evidence` provides an artifact-neutral mechanism connecting declared contracts to implementation boundaries, positive/negative proofs, authoritative commands, and release gates.

The generic contract does not know Webapp surfaces, routes, UI states, Skill resources, or any other artifact vocabulary. `contract-item` targets carry a contract ID plus artifact-defined `itemKind` and `itemId`; artifact/capability validators own exact item coverage and target-specific proof strength.

Template mode is deliberately empty. Use planning mode after product requirements and their intended contract targets are known but before implementation evidence exists. A concrete implemented product switches to product mode and records implementation evidence plus the explicit product requirement ledger.

Validation responsibilities are intentionally split rather than duplicated:

- the registered JSON Schema owns document structure and mode-specific completeness, including the mandatory non-empty planning/product requirement ledger, proof-kind declaration for each requirement, planning target declaration, verified product implementation-boundary status, required proof metadata, and at least one selected release gate per product record;
- `validate_implementation_evidence.py` runs after registered-contract schema validation and owns semantic relationships that JSON Schema cannot express conveniently: unique identities, registered-contract target references, requirement-to-record references, optional product requirement-target matching, proof-kind constraints, command/gate references, proof-command execution by selected gates, and unused command/gate detection;
- artifact/capability validators own item existence, complete target coverage, and target-specific proof-strength policy.

A structurally incomplete document must therefore fail registered-contract schema validation before semantic evidence validation runs. The semantic validator mirrors critical ledger/proof relationships because release-readiness validation can invoke the semantic path directly; it does not create a second authority.

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

Requirement IDs are stable machine-facing identifiers; their descriptions are intentionally opaque to Composition. Lowercase IDs remain valid, and uppercase hyphenated IDs such as `REQ-SEVERITY-BROWSER-FILTER` are also valid for requirement rows. Each product requirement must reference at least one implementation-evidence record and must declare at least one sufficient positive proof kind. The existing record rules then close the graph through an implementation boundary, positive and negative proofs, authoritative commands, and a selected release gate.

Product requirements may retain a non-empty `targets` array from planning. When present, the generic validator requires the target set to match the targets of the linked `recordIds` exactly. This is an internal consistency check, not a substitute for version-control review of the planning-to-product transition: a validator cannot reconstruct historical intent after both fields have been edited.

The ledger is mandatory in product mode so that a consumer cannot evade traceability by omitting machine-readable intent altogether. The proof-kind declaration is also mandatory so that a consumer cannot evade evidence-strength validation by omitting the machine-readable minimum for a requirement. Composition still does not infer requirements or proof strength from prose: the human or coding agent must enumerate the product requirements and choose sufficient proof kinds. Template mode carries `requirements: []` and makes no product claims.

## Proof kind and deferred state

The existing `evidenceProof.kind` is the execution-strength classification; it is not a claim that every proof is browser-backed. Use `inspection` for static source/HTML/JSON inspection, `unit-test`, `integration-test`, or `migration-test` for executable process-level checks, and `end-to-end-test` or `accessibility-test` for browser interaction and keyboard/focus behavior. Artifact/capability validators decide which kinds are sufficient for a target.

A product proof may be `deferred` when the required environment is unavailable. Deferred evidence is retained as an explicit incomplete state and may allow structural validation to describe the composition as valid, but release readiness rejects every non-`verified` proof. Static inspection must therefore never be silently promoted to browser interaction evidence.

Every planning/product requirement declares `requiredPositiveProofKinds`. For example, a CLI requirement can require `integration-test`, while a browser interaction requirement can require `end-to-end-test` or `accessibility-test`. This prevents a static `inspection` proof from satisfying a caller-visible interactive requirement without making Composition infer product semantics from requirement prose. When several kinds are acceptable, list each acceptable kind; when a required environment is unavailable, keep the corresponding proof `deferred` rather than weakening the declared requirement.

## Planning requirement ledger

Use `mode: "planning"` after explicit product requirements and their intended machine contract targets are known but before implementation records exist. Planning mode is deliberately narrow: `commands`, `releaseGates`, and `records` stay empty; `requirements` is non-empty; every requirement has a stable ID, description, non-empty `targets`, empty `recordIds`, and non-empty `requiredPositiveProofKinds`.

Example:

```json
{
  "id": "REQ-CLI-FILTER",
  "description": "The packaged CLI filters caller-visible records by severity.",
  "targets": [
    {
      "kind": "contract-item",
      "contractId": "cli_interface",
      "itemKind": "entrypoint",
      "itemId": "records"
    }
  ],
  "recordIds": [],
  "requiredPositiveProofKinds": ["integration-test"]
}
```

This gives coding agents a machine-readable requirement inventory before coding and tells selected artifact/capability validators which proof-strength policy should apply before product records exist. The generic lifecycle validates that planning targets refer to registered contracts; the owning artifact/capability validator is responsible for validating exact item identity and sufficient proof kinds.

Preserve stable requirement IDs when moving to `product`. Retaining the planning `targets` is recommended because product validation will then check that linked records implement exactly those targets, but v5 does not require redundant product targets when record targets already provide the canonical implementation mapping. `template` means no product requirement claim is active; `planning` means target-bound requirements are explicit but implementation is incomplete; `product` means the implementation/evidence graph is active. Only product mode can pass release readiness.
