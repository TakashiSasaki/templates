# Generated-repository conformance

The Webapp template must prove that its contracts and validation toolchain remain usable after a repository is generated and product responsibility replaces template responsibility. This document defines the clean-room conformance model exercised by `tests/test_generated_repository_conformance.py` and `tests/test_generated_release_evidence_conformance.py`.

The model is framework-neutral. It does not select a product framework, package manager, backend, authentication provider, browser automation library, CI provider, deployment platform, or production runtime. Its generated product is a deterministic fixture used only to prove that the template can be operationalized coherently.

## Trust and responsibility boundary

The source repository remains a template:

- `contracts/implementation-evidence.json` remains in `mode: template`;
- `contracts/release-evidence.json` remains in `mode: template`;
- source contracts remain example declarations;
- no product implementation directory or product release result is added to the template root; and
- the source checkout is never modified while a conformance fixture is running.

Each test creates a new temporary repository tree, excludes source-control and local-environment residue, and changes only that copy. The generated copy owns its product declarations, implementation locators, proof results, commands, release gates, release subject, command and gate results, provenance, and decision. Assertions after fixture disposal verify that the source evidence documents are still in template mode and that no product directory leaked into the source tree.

The clean-room conformance classes are template-maintainer-only. They run when the source implementation-evidence document is in `mode: template` and are automatically skipped when the files are retained in a generated product repository whose source implementation evidence is in `mode: product`. Separate scope regressions remain active in both modes and verify these execution boundaries.

## Fixture materialization

The implementation fixture performs the following deterministic transition:

1. copy the complete template tree to a temporary repository root while excluding `.git`, `.venv`, Python caches, and test caches;
2. replace or explicitly settle the example surface, route, UI-state, and viewport values as declarations for the fixture product `Conformance Workbench`;
3. change the copied implementation-evidence document to `mode: product`;
4. retain the complete target set derived from surfaces, routes, UI states, viewports, input capabilities, and registered post-version-1 transitions;
5. assign every target a verified repository-local implementation locator;
6. assign every target one verified positive proof and one verified negative proof;
7. bind every proof to the authoritative command ID `generated-product-proof`;
8. select the release gate `generated-product-release` for every record; and
9. make that gate execute the proof command used by every record.

The fixture materializes its implementation and proof locations in `product/conformance-targets.json`. These locations are deliberately simple repository-local JSON pointers. They prove locator integrity and responsibility transfer without implying a framework component model.

The release fixture then materializes:

1. one exact 40-hex fixture revision;
2. a completed result for every authoritative command executed by a registered gate;
3. SHA-256 of each current authoritative command definition;
4. a passing result for every registered release gate;
5. repository-local result locators;
6. UTC execution, decision, and generation times; and
7. one approved release decision.

The release record is written only in the generated copy. It represents an ephemeral product release workspace rather than a source file attempting to name its own commit.

## Reviewed proof command

The implementation fixture registers one authoritative command:

```text
python product/prove_conformance.py
```

The test harness does not parse or dispatch the command string. It directly invokes the known fixture script with the current test interpreter and a fixed argument vector. The script is generated from reviewed test code, reads only repository-local JSON files, performs no network or deployment action, and verifies all positive and negative target results.

This is a narrow conformance mechanism, not a general command executor. Product repositories remain responsible for executing their own reviewed commands in CI with the runtime and isolation appropriate to the selected toolchain.

## End-to-end validation

Across the two generated-repository fixtures, the copied repository executes:

1. the reviewed product proof command;
2. `scripts/validate_contracts.py`;
3. `python -m scripts.validate_contracts`;
4. `scripts/validate_contract_evolution.py`;
5. `python -m scripts.validate_contract_evolution`;
6. `scripts/validate_implementation_evidence.py`;
7. `python -m scripts.validate_implementation_evidence`;
8. `scripts/validate_release_evidence.py --expected-revision <revision>`; and
9. `python -m scripts.validate_release_evidence --expected-revision <revision>`.

The product proof checks 52 outcomes: positive and negative evidence for each of the 26 current implementation targets. The eight validator forms must succeed against a generated product state, with the release forms additionally bound to the exact fixture revision.

## Negative conformance coverage

Deliberately broken generated copies must fail with stable diagnostics for:

- template-mode residue after product implementation claims have been materialized;
- a missing implementation-evidence target;
- an unverified implementation boundary;
- an unknown proof command;
- an unused command;
- an unused release gate;
- a proof command omitted from the selected release gate;
- a false reviewed positive or negative proof result;
- a release subject that differs from the expected revision; and
- release evidence generated for an obsolete command definition.

For the first seven implementation-reference cases, the harness directly invokes `scripts/validate_implementation_evidence.py` from the generated repository root with a fixed argument vector, requires a nonzero exit, and matches the expected stderr diagnostic. It does not call an imported validator from the source checkout. The false-proof case directly invokes the generated reviewed product proof script.

The release cases invoke the copied release-evidence validator with an explicit expected revision. Together these cases distinguish copied-entry-point behavior, implementation-reference closure, semantic proof execution, immutable release-subject binding, and command-definition binding.

## Versioning rule

The generated-repository fixture itself does not change an accepted contract document structure or semantic obligation. Fixture-only changes therefore do not increment a domain schema version or register a migration.

The new `release_evidence` family starts at version 1 because it introduces an accepted document structure and new product release obligations. It has no migration from a nonexistent earlier version. Future changes to its required fields or semantics follow the normal contract-evolution rules.

## Non-goals

The fixtures do not prove that a real application framework renders a page, that a real authorization provider rejects access, that a remote CI provider is trustworthy, or that a deployment platform releases safely. Those are product-owned proofs. The fixtures prove that a generated repository can replace template examples with explicit product declarations, close every implementation-evidence reference, execute a reviewed product proof, bind completed results to one exact revision and the current command definitions, and pass the complete retained validator surface without relying on template-only state.
