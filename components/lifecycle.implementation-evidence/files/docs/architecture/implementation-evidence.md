# Implementation evidence lifecycle

`lifecycle.implementation-evidence` provides an artifact-neutral mechanism connecting declared contracts to implementation boundaries, positive/negative proofs, authoritative commands, execution capabilities, repository harnesses, and release gates.

The generic contract does not know Webapp surfaces, routes, UI states, Skill resources, or any other artifact vocabulary. `contract-item` targets carry a contract ID plus artifact-defined `itemKind` and `itemId`; artifact/capability validators own exact item coverage and target-specific proof strength.

Template mode is deliberately empty. Use planning mode after product requirements and their intended contract targets are known but before implementation evidence exists. A concrete implemented product switches to product mode and records implementation evidence plus the explicit product requirement ledger.

Validation responsibilities are intentionally split rather than duplicated:

- the registered JSON Schema owns document structure and mode-specific completeness, including the mandatory non-empty planning/product requirement ledger, proof-kind declaration for each requirement, planning target declaration, verified product implementation-boundary status, command execution profiles, safe repository harness locators, required proof metadata, and at least one selected release gate per product record;
- `validate_implementation_evidence.py` runs after registered-contract schema validation and owns semantic relationships that JSON Schema cannot express conveniently: unique identities, registered-contract target references, requirement-to-record references, optional product requirement-target matching, proof-kind-to-command-capability binding, repository harness existence and regular-file identity, exact command-to-harness invocation, negative-path capability, command/gate references, proof-command execution by selected gates, and unused command/gate detection;
- artifact/capability validators own item existence, complete target coverage, and target-specific proof-strength policy. They may require additional execution capabilities beyond the generic proof-kind mapping; Webapp browser-sensitive targets, for example, require a `browser`-capable command.

A structurally incomplete document must therefore fail registered-contract schema validation before semantic evidence validation runs. The semantic validator mirrors critical path-safety and proof relationships because release-readiness validation can invoke the semantic path directly; it does not create a second authority.

## Explicit product requirements

Every product-mode document must declare at least one explicit requirement in the same canonical document. Requirement IDs are stable machine-facing identifiers. Each product requirement references implementation-evidence records and declares sufficient positive proof kinds; records close the graph through an implementation boundary, positive and negative proofs, authoritative commands, execution profiles, and selected release gates.

Product requirements may retain a non-empty `targets` array from planning. When present, the generic validator requires the target set to match the targets of the linked `recordIds` exactly. This is an internal consistency check, not a substitute for the immutable planning checkpoint or version-control review of the planning-to-product transition.

## Proof kind is not execution surface

`evidenceProof.kind` describes the scope/class of a proof. It is not sufficient by itself to establish how the proof executes. Version 6 therefore requires every product command to carry a separate execution profile:

```json
{
  "id": "verify-browser",
  "command": "python tests/test_browser.py",
  "purpose": "Exercise the browser-visible product path.",
  "execution": {
    "capabilities": ["end-to-end", "browser"],
    "harness": {
      "kind": "repository-file",
      "locator": "tests/test_browser.py"
    },
    "supportsNegativePath": true
  }
}
```

The generic lifecycle binds proof kinds to command capabilities:

- `unit-test` requires `unit`;
- `integration-test` requires `integration`;
- `end-to-end-test` requires `end-to-end`;
- `accessibility-test` requires `accessibility`;
- `migration-test` requires `migration`;
- `inspection` requires `inspection`;
- `other` requires `other`.

This mapping deliberately does **not** equate `end-to-end` with `browser`. A packaged CLI or protocol workflow may be end-to-end without using a browser. Artifact validators add the execution surface they actually require. Browser-sensitive Webapp evidence therefore needs both an accepted browser-level proof kind and a command whose capabilities include `browser`.

## Command-to-harness invocation authority

The harness locator is not merely a descriptive filename. The semantic validator derives the command's executable invocation from the exact pair of `command` text and `execution.harness.locator`. Exactly these forms are accepted:

- `python <repository-file>` for a Python script harness;
- `python -m unittest <python.module>` when the harness is the corresponding `.py` module path;
- `./<repository-file>` for a directly invoked repository harness.

No separate invocation label is trusted. A command such as `echo tests/proof.py`, `python -c ... tests/proof.py`, or an opaque shell command that merely mentions the locator cannot claim that harness. If a proof needs additional arguments, environment setup, discovery rules, or another opaque launcher, create a repository-owned wrapper harness and make that wrapper the declared command/harness authority.

A command harness must also be a safe repository-relative regular file, not arbitrary prose and not a symbolic link. Normal consumer validation and release-readiness validation check the same path-safety boundary and require the file to exist as a non-symlink regular file. This does not prove that the harness implementation is semantically honest; it makes the executable identity and obvious command/harness contradictions machine-checkable. When the release lifecycle is selected, `lifecycle.release-execution` binds the inferred invocation to one exact fixed argv shape and revision-bound release evidence records the actual result.

## Positive and negative execution

Both positive and negative evidence must reference an authoritative command. A command used by `negativeEvidence` must declare `supportsNegativePath: true`. A positive-only harness may set the field to `false`; it cannot then be reused as evidence for a claimed negative path.

The boolean is a declared machine contract, not a substitute for running the test. Release execution and CI provide execution provenance. Its purpose is to prevent an evidence graph from claiming a negative-path proof while simultaneously declaring that the referenced command does not own a negative path.

## Deferred state

A product proof may be `deferred` when the required environment is unavailable. Deferred evidence is retained as an explicit incomplete state and may allow structural validation to describe the composition as valid, but release readiness rejects every non-`verified` proof. The intended command execution profile must still be truthful: an unavailable browser environment is represented by a deferred browser-capable proof, not by relabeling static inspection as browser evidence.

The component owns the executable `check-release-readiness` machine operation in `.template-composition/implementation-evidence-actions.json`. Its public argv invokes the provider-owned `.template-composition/run_action.py` dispatcher rather than exposing the internal validator path or validator-specific options. The managed registry schema fixes the complete argv token sequence with `const`; a consumer may replace only whole-token entries listed in `caller_inputs` and must not add, remove, reorder, or inject interpreter options. `{python}` means one executable path for a CPython interpreter satisfying Composition's advertised runtime requirements; interpreter flags are not caller inputs and the canonical action argv contains none. Execute the advertised argv directly from the materialized repository root. The dispatcher owns the internal validator path, internal argv ordering, working directory, and Python invocation semantics.

The release-readiness action returns exit `0` for `ready` and exit `1` for a structured `not-ready` result. Both results are JSON conforming to the advertised `.template-composition/implementation-evidence-release-readiness.schema.json`; the dispatcher also adds that path as `$schema` so the emitted machine result identifies its validation contract. Provider execution failures are not converted into a false semantic `not-ready` result. Human-oriented validator output remains available through the internal validator, but it is not the machine action contract.

Every planning/product requirement declares `requiredPositiveProofKinds`. When several proof kinds are acceptable, list each acceptable kind; when a required environment is unavailable, keep the corresponding proof `deferred` rather than weakening the declared requirement.

## Planning requirement ledger

Use `mode: "planning"` after explicit product requirements and their intended machine contract targets are known but before implementation records exist. Planning mode is deliberately narrow: `commands`, `releaseGates`, and `records` stay empty; `requirements` is non-empty; every requirement has a stable ID, description, non-empty `targets`, empty `recordIds`, and non-empty `requiredPositiveProofKinds`.

The generic lifecycle validates that planning targets refer to registered contracts; the owning artifact/capability validator is responsible for validating exact item identity and sufficient proof kinds. Preserve stable requirement IDs when moving to `product`. Retaining planning `targets` is recommended because product validation then checks that linked records implement exactly those targets. `template` means no product requirement claim is active; `planning` means target-bound requirements are explicit but implementation is incomplete; `product` means the implementation/evidence graph is active. Only product mode can pass release readiness.
