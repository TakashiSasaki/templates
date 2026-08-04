# Generated-repository conformance

The Webapp template must prove that its contracts and validation toolchain remain usable after a repository is generated and product responsibility replaces template responsibility. This document defines the current clean-room conformance model exercised by:

- `tests/test_generated_repository_conformance.py`;
- `tests/test_generated_release_evidence_conformance.py`; and
- `tests/test_generated_release_evidence_production.py`.

The repository also retains `release_bundle` validation in CI. Phase 3B will extend the generated-repository clean room to produce exact bundle digests and execute those two additional validator forms from product mode.

The model is framework-neutral. It does not select a product framework, package manager, backend, authentication provider, browser automation library, CI provider, deployment platform, or production runtime. Its generated product is a deterministic fixture used only to prove that the template can be operationalized coherently.

## Trust and responsibility boundary

The source repository remains a template:

- `contracts/implementation-evidence.json` remains in `mode: template`;
- `contracts/release-evidence.json` remains in `mode: template`;
- `contracts/release-bundle.json` remains in `mode: template`;
- source contracts remain example declarations;
- no product implementation directory, execution artifact, product release result, or product handoff bundle is added to the template root; and
- the source checkout is never modified while a conformance fixture is running.

Each test creates a new temporary repository tree, excludes source-control and local-environment residue, and changes only that copy. The generated copy currently owns its product declarations, implementation locators, proof results, commands, release gates, actual command execution, release subject, command and gate results, provenance, decision, and repository-local run artifact. Assertions after fixture disposal verify that source implementation and release evidence remain in template mode and that no product directory leaked into the source tree. Phase 3B will add generated-copy ownership and source-mode assertions for the bundle contract.

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

### Python startup boundary

The harness launches the producer through the fixed argument vector:

```text
[sys.executable, "-I", "product/produce_release_evidence.py", "--revision", revision]
```

Isolated mode prevents the script directory, current directory, `PYTHON*` module-path inputs, user site, and repository-local bytecode from participating in interpreter startup or standard-library imports before the producer can inspect the generated repository. The producer also checks `sys.flags.isolated` before its own non-built-in imports and rejects a non-isolated invocation as defense in depth. The harness-level `-I` launch remains the authoritative protection because interpreter startup precedes script execution.

The reviewed proof is also invoked with the current interpreter in isolated mode. Repository files are read through paths derived from the proof script's own location; they are not imported through the ambient module search path.

A regression places a valid ignored sourceless `product/argparse.pyc` beside the producer. A non-isolated pre-fix producer could import that module before revision verification. The corrected launcher and producer boundary prevent the bytecode from executing and reject the revision-external file before producing evidence.

### Git identity and worktree boundary

The producer:

1. removes inherited `GIT_*` process inputs;
2. disables system and global Git configuration;
3. requires `.git` to be a non-symbolic directory at the generated root;
4. resolves the effective absolute Git directory and requires it to equal the generated repository's `.git` directory;
5. resolves the effective top-level worktree and requires it to equal the generated repository root;
6. only after those identity checks, runs revision and cleanliness commands with explicit `--git-dir <root>/.git` and `--work-tree <root>` arguments;
7. disables fsmonitor, untracked-cache, ignore-stat, and sparse-checkout behavior for those fixed invocations;
8. resolves `HEAD^{commit}` and requires it to equal the supplied revision;
9. rejects tracked changes and ordinary untracked files; and
10. separately enumerates ignored untracked files with `git ls-files --others --ignored --exclude-standard` and requires that set to be empty.

The effective-top-level check rejects local Git configuration that redirects `core.worktree` to a different clean directory. Explicit Git-directory and worktree arguments then prevent later status and inventory checks from drifting away from the root whose files the proof executes.

Ignored inputs are checked separately because ordinary porcelain status intentionally omits files matched by ignore rules. This matters for executable caches such as `product/__pycache__/prove_conformance.<tag>.pyc`, which can influence Python execution even though the file is absent from the committed revision.

### Fixed reviewed execution

After Python and Git preflight, the producer:

1. requires the exact product-mode implementation evidence produced by the fixture;
2. requires the exact authoritative command text `python product/prove_conformance.py`;
3. requires the exact `generated-product-release` gate and its command membership;
4. invokes the reviewed proof through a fixed isolated argument vector;
5. captures actual stdout, stderr, process result, start time, and completion time;
6. calculates SHA-256 from the exact authoritative command text;
7. derives the gate result from the command result;
8. derives approval or rejection from the gate result;
9. writes `product/release-run.json`, including the verified HEAD and clean-worktree result; and
10. writes product-mode `contracts/release-evidence.json` for the verified revision.

The producer never parses the authoritative command string and exposes no command, executable, argument, environment, working-directory, gate-selection, or Git-ref parameter. Its Git and proof invocations are fixed reviewed argument vectors. It is fixture code, not a reusable command dispatcher or release orchestrator.

A passing proof execution produces approved evidence that passes both copied release-validator entry points. A failing proof execution produces a failed command result, failed gate result, and rejected decision; the producer exits nonzero and release validation rejects that record. A mismatched revision, a tracked or ordinary untracked change, an ignored untracked file, a redirected Git worktree, a non-isolated producer launch, or command-registration drift is rejected before the proof is executed and before any run artifact or product release claim is created.

## Reviewed proof command

The implementation fixture registers one authoritative command:

```text
python product/prove_conformance.py
```

The proof script is generated from reviewed test code, reads only repository-local JSON files, performs no network or deployment action, and verifies all positive and negative target results.

The implementation conformance test invokes the proof directly. The evidence-production fixture maps the portable command declaration to the current test interpreter plus isolated-mode startup and invokes the same proof through its separately reviewed fixed producer. Neither path interprets command text from the contract.

This is a narrow conformance mechanism, not a general command executor. Product repositories remain responsible for executing their own reviewed commands in CI with the runtime and isolation appropriate to the selected toolchain.

## Current end-to-end validation

Across the generated-repository fixtures, the copied repository executes:

1. the reviewed product proof command;
2. construction and verification of an immutable generated-product Git revision;
3. isolated producer startup before repository-local imports;
4. generated Git-directory and effective-worktree identity checks;
5. tracked, ordinary untracked, and ignored-input preflight for the pinned generated tree;
6. actual release-evidence production for that verified revision;
7. `scripts/validate_contracts.py`;
8. `python -m scripts.validate_contracts`;
9. `scripts/validate_contract_evolution.py`;
10. `python -m scripts.validate_contract_evolution`;
11. `scripts/validate_implementation_evidence.py`;
12. `python -m scripts.validate_implementation_evidence`;
13. `scripts/validate_release_evidence.py --expected-revision <revision>`; and
14. `python -m scripts.validate_release_evidence --expected-revision <revision>`.

The product proof checks 52 outcomes: positive and negative evidence for each of the 26 current implementation targets. These eight validator forms must succeed against a generated product state, with the release forms additionally bound to the exact verified fixture revision.

The repository-wide CI surface now contains ten validator forms because it also executes:

```text
scripts/validate_release_bundle.py
python -m scripts.validate_release_bundle
```

In this Phase 3A foundation, those two forms validate the template-mode bundle contract in CI. Phase 3B will materialize a product-mode bundle from exact generated bytes and add both forms to the clean-room end-to-end sequence.

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
- a repository-local bytecode import opportunity before producer preflight;
- a local Git configuration that redirects the effective worktree;
- actual proof failure in a committed generated revision; and
- command-registration drift in a committed generated revision before evidence production.

For implementation-reference cases, the harness directly invokes `scripts/validate_implementation_evidence.py` from the generated repository root with a fixed argument vector, requires a nonzero exit, and matches the expected stderr diagnostic. It does not call an imported validator from the source checkout. The false-proof case directly invokes the generated reviewed product proof script.

The declarative release cases invoke the copied release-evidence validator with an explicit expected revision. The production cases invoke the copied reviewed producer and then inspect and validate the generated run artifact and release record. Together these cases distinguish copied-entry-point behavior, implementation-reference closure, semantic proof execution, isolated startup, actual generated-tree revision binding, Git metadata/worktree identity, tracked/untracked/ignored input exclusion, command-definition binding, actual result capture, and decision derivation.

Release-bundle unit regressions currently prove exact active-contract coverage, self-reference exclusion, manifest order, path binding, current-byte digest binding, revision equality, and generation chronology. Phase 3B will add those failure cases to generated product copies and actual bundle production.

## Versioning rule

The generated-repository fixture mechanics do not change an accepted contract document structure or semantic obligation. Fixture-only changes therefore do not increment a domain schema version or register a migration.

The `release_evidence` family remains at version 1. Actual production conformance proves that existing version 1 fields can be populated from reviewed execution; it does not add or reinterpret a field.

The `release_bundle` family begins at version 1 in Phase 3A. Its static contract and validator define accepted handoff manifests. Adding clean-room production in Phase 3B will populate those existing fields from exact generated bytes and will not require a version increment unless accepted structure or semantics change.

Future changes to required fields or semantics follow the normal contract-evolution rules.

## Non-goals

The current fixtures do not prove that a real application framework renders a page, that a real authorization provider rejects access, that a remote CI provider is trustworthy, that the generated run artifact is immutable after production, that a bundle was retained or signed, or that a deployment platform releases safely. Those are product-owned proofs.

The current fixtures prove that a generated repository can replace template examples with explicit product declarations, close every implementation-evidence reference, create and verify an immutable generated-product commit, isolate interpreter startup, pin Git identity and worktree selection, exclude tracked, ordinary untracked, and ignored revision-external inputs before executing a reviewed product proof, produce release evidence from the actual result without a generic command dispatcher, bind that evidence to the verified revision and current command definitions, and pass the first eight retained validator forms without relying on template-only state.

Phase 3B remains responsible for proving that the same generated product can compute and validate the exact digest-closed release bundle and thereby pass all ten retained validator forms.
