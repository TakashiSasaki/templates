# Generated-repository conformance

The Webapp template must prove that its contracts and validation toolchain remain usable after a repository is generated and product responsibility replaces template responsibility. This document defines the clean-room conformance model exercised by:

- `tests/test_generated_repository_conformance.py`;
- `tests/test_generated_release_evidence_conformance.py`; and
- `tests/test_generated_release_evidence_production.py`.

The model is framework-neutral. It does not select a product framework, package manager, backend, authentication provider, browser automation library, CI provider, deployment platform, or production runtime. Its generated product is a deterministic fixture used only to prove that the template can be operationalized coherently.

## Trust and responsibility boundary

The source repository remains a template:

- `contracts/implementation-evidence.json` remains in `mode: template`;
- `contracts/release-evidence.json` remains in `mode: template`;
- source contracts remain example declarations;
- no product implementation directory, execution artifact, or product release result is added to the template root; and
- the source checkout is never modified while a conformance fixture is running.

Each test creates a new temporary repository tree, excludes source-control and local-environment residue, and changes only that copy. The generated copy owns its product declarations, implementation locators, proof results, commands, release gates, actual command execution, release subject, command and gate results, provenance, decision, and repository-local run artifact. Assertions after fixture disposal verify that the source evidence documents are still in template mode and that no product directory leaked into the source tree.

The clean-room conformance classes are template-maintainer-only. They run when the source implementation-evidence document is in `mode: template` and are automatically skipped when the files are retained in a generated product repository whose source implementation evidence is in `mode: product`. Separate scope regressions remain active in both modes and verify these execution boundaries.

## Implementation fixture

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

## Declarative release-evidence fixture

`test_generated_release_evidence_conformance.py` materializes a completed product-mode release record for one fixed revision. It proves that the copied release validator accepts complete command and gate results and rejects:

- a subject revision that differs from the expected revision; and
- a command digest that no longer matches the authoritative command definition.

This fixture isolates release-validator semantics. Its result values are deliberately constructed so failures can target revision and digest binding without depending on process execution.

## Actual evidence-production fixture

`test_generated_release_evidence_production.py` proves the missing execution boundary. It installs `product/produce_release_evidence.py` only in the temporary generated repository.

The producer:

1. accepts one explicit lowercase 40-hex revision and no command input;
2. requires the exact product-mode implementation evidence produced by the fixture;
3. requires the exact authoritative command text `python product/prove_conformance.py`;
4. requires the exact `generated-product-release` gate and its command membership;
5. invokes `[sys.executable, "product/prove_conformance.py"]` directly with a fixed argument vector;
6. captures actual stdout, stderr, process result, start time, and completion time;
7. calculates SHA-256 from the exact authoritative command text;
8. derives the gate result from the command result;
9. derives approval or rejection from the gate result;
10. writes `product/release-run.json`; and
11. writes product-mode `contracts/release-evidence.json` for the supplied revision.

The producer never parses the authoritative command string and exposes no command, executable, argument, environment, working-directory, or gate-selection parameter. It is reviewed fixture code, not a reusable command dispatcher.

A passing proof execution produces approved evidence that passes both copied release-validator entry points. A failing proof execution produces a failed command result, failed gate result, and rejected decision; the producer exits nonzero and release validation rejects that record. Command-registration drift is rejected before the proof is executed and before any run artifact or product release claim is created.

## Reviewed proof command

The implementation fixture registers one authoritative command:

```text
python product/prove_conformance.py
```

The proof script is generated from reviewed test code, reads only repository-local JSON files, performs no network or deployment action, and verifies all positive and negative target results.

The implementation conformance test invokes the proof directly. The evidence-production fixture invokes the same proof through its separately reviewed fixed producer. Neither path interprets command text from the contract.

This is a narrow conformance mechanism, not a general command executor. Product repositories remain responsible for executing their own reviewed commands in CI with the runtime and isolation appropriate to the selected toolchain.

## End-to-end validation

Across the generated-repository fixtures, the copied repository executes:

1. the reviewed product proof command;
2. actual release-evidence production for an explicit fixture revision;
3. `scripts/validate_contracts.py`;
4. `python -m scripts.validate_contracts`;
5. `scripts/validate_contract_evolution.py`;
6. `python -m scripts.validate_contract_evolution`;
7. `scripts/validate_implementation_evidence.py`;
8. `python -m scripts.validate_implementation_evidence`;
9. `scripts/validate_release_evidence.py --expected-revision <revision>`; and
10. `python -m scripts.validate_release_evidence --expected-revision <revision>`.

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
- a release subject that differs from the expected revision;
- release evidence generated for an obsolete command definition;
- actual proof failure during evidence production; and
- command-registration drift before evidence production.

For implementation-reference cases, the harness directly invokes `scripts/validate_implementation_evidence.py` from the generated repository root with a fixed argument vector, requires a nonzero exit, and matches the expected stderr diagnostic. It does not call an imported validator from the source checkout. The false-proof case directly invokes the generated reviewed product proof script.

The declarative release cases invoke the copied release-evidence validator with an explicit expected revision. The production cases invoke the copied reviewed producer and then inspect and validate the generated run artifact and release record. Together these cases distinguish copied-entry-point behavior, implementation-reference closure, semantic proof execution, immutable release-subject binding, command-definition binding, actual result capture, and decision derivation.

## Versioning rule

The generated-repository fixtures do not change an accepted contract document structure or semantic obligation. Fixture-only changes therefore do not increment a domain schema version or register a migration.

The `release_evidence` family remains at version 1. Actual production conformance proves that existing version 1 fields can be populated from reviewed execution; it does not add or reinterpret a field. Future changes to required fields or semantics follow the normal contract-evolution rules.

## Non-goals

The fixtures do not prove that a real application framework renders a page, that a real authorization provider rejects access, that a remote CI provider is trustworthy, that a run artifact is immutable, or that a deployment platform releases safely. Those are product-owned proofs.

The fixtures prove that a generated repository can replace template examples with explicit product declarations, close every implementation-evidence reference, execute a reviewed product proof, produce release evidence from the actual result without a generic command dispatcher, bind that evidence to one exact revision and the current command definitions, and pass the complete retained validator surface without relying on template-only state.
