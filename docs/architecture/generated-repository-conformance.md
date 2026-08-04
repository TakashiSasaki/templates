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

The implementation fixture deliberately starts without `.git`. The evidence-production fixture installs its reviewed producer, initializes a fresh Git repository in that generated tree, commits the complete generated product state, and uses the resulting immutable commit as the candidate revision. No source-template Git history is copied into the clean room.

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

Before execution, the harness initializes a new Git repository, force-adds the generated fixture files, creates one deterministic commit, and supplies that commit's lowercase 40-hex object name to the producer. A failing proof fixture and a command-drift fixture are each committed as their own immutable generated state before the producer runs.

The producer:

1. accepts one explicit lowercase 40-hex revision and no command input;
2. removes inherited `GIT_*` process inputs and disables system and global Git configuration;
3. resolves `HEAD^{commit}` through a fixed Git argument vector and requires it to equal the supplied revision;
4. requires the generated repository index and worktree to have no tracked changes or ordinary untracked files;
5. separately enumerates ignored untracked files with the fixed argument vector `git ls-files --others --ignored --exclude-standard` and requires that set to be empty;
6. requires the exact product-mode implementation evidence produced by the fixture;
7. requires the exact authoritative command text `python product/prove_conformance.py`;
8. requires the exact `generated-product-release` gate and its command membership;
9. invokes `[sys.executable, "product/prove_conformance.py"]` directly with a fixed argument vector;
10. captures actual stdout, stderr, process result, start time, and completion time;
11. calculates SHA-256 from the exact authoritative command text;
12. derives the gate result from the command result;
13. derives approval or rejection from the gate result;
14. writes `product/release-run.json`, including the verified HEAD and clean-worktree result; and
15. writes product-mode `contracts/release-evidence.json` for the verified revision.

The producer never parses the authoritative command string and exposes no command, executable, argument, environment, working-directory, gate-selection, or Git-ref parameter. Its Git and proof invocations are fixed reviewed argument vectors. It is fixture code, not a reusable command dispatcher or release orchestrator.

A passing proof execution produces approved evidence that passes both copied release-validator entry points. A failing proof execution produces a failed command result, failed gate result, and rejected decision; the producer exits nonzero and release validation rejects that record. A mismatched revision, a tracked or ordinary untracked change, an ignored untracked file, or command-registration drift is rejected before the proof is executed and before any run artifact or product release claim is created.

Ignored inputs are checked separately because `git status --porcelain=v1 --untracked-files=all` intentionally omits files matched by ignore rules. This matters for executable caches such as `product/__pycache__/prove_conformance.<tag>.pyc`, which can influence Python execution even though the file is absent from the committed revision.

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
2. construction and verification of an immutable generated-product Git revision;
3. tracked, untracked, and ignored-input preflight for that generated tree;
4. actual release-evidence production for that verified revision;
5. `scripts/validate_contracts.py`;
6. `python -m scripts.validate_contracts`;
7. `scripts/validate_contract_evolution.py`;
8. `python -m scripts.validate_contract_evolution`;
9. `scripts/validate_implementation_evidence.py`;
10. `python -m scripts.validate_implementation_evidence`;
11. `scripts/validate_release_evidence.py --expected-revision <revision>`; and
12. `python -m scripts.validate_release_evidence --expected-revision <revision>`.

The product proof checks 52 outcomes: positive and negative evidence for each of the 26 current implementation targets. The eight validator forms must succeed against a generated product state, with the release forms additionally bound to the exact verified fixture revision.

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
- a supplied revision that differs from the generated repository HEAD;
- a tracked or ordinary untracked change after the generated revision was created;
- an ignored executable input after the generated revision was created;
- actual proof failure in a committed generated revision; and
- command-registration drift in a committed generated revision before evidence production.

For implementation-reference cases, the harness directly invokes `scripts/validate_implementation_evidence.py` from the generated repository root with a fixed argument vector, requires a nonzero exit, and matches the expected stderr diagnostic. It does not call an imported validator from the source checkout. The false-proof case directly invokes the generated reviewed product proof script.

The declarative release cases invoke the copied release-evidence validator with an explicit expected revision. The production cases invoke the copied reviewed producer and then inspect and validate the generated run artifact and release record. Together these cases distinguish copied-entry-point behavior, implementation-reference closure, semantic proof execution, actual generated-tree revision binding, tracked/untracked/ignored input exclusion, command-definition binding, actual result capture, and decision derivation.

## Versioning rule

The generated-repository fixtures do not change an accepted contract document structure or semantic obligation. Fixture-only changes therefore do not increment a domain schema version or register a migration.

The `release_evidence` family remains at version 1. Actual production conformance proves that existing version 1 fields can be populated from reviewed execution; it does not add or reinterpret a field. Future changes to required fields or semantics follow the normal contract-evolution rules.

## Non-goals

The fixtures do not prove that a real application framework renders a page, that a real authorization provider rejects access, that a remote CI provider is trustworthy, that the generated run artifact is immutable after production, or that a deployment platform releases safely. Those are product-owned proofs.

The fixtures prove that a generated repository can replace template examples with explicit product declarations, close every implementation-evidence reference, create and verify an immutable generated-product commit, exclude tracked, ordinary untracked, and ignored revision-external inputs before executing a reviewed product proof, produce release evidence from the actual result without a generic command dispatcher, bind that evidence to the verified revision and current command definitions, and pass the complete retained validator surface without relying on template-only state.
