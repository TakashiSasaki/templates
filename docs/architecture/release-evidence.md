# Release evidence

The release-evidence contract binds one exact product revision to the commands and release gates declared by `contracts/implementation-evidence.json`. It records completed execution and an approval decision without selecting a framework, test runner, package manager, CI provider, artifact store, deployment platform, or release orchestration product.

## Contract family

`contracts/release-evidence.json` is registered as contract family `release_evidence` with stable migration slug `release-evidence`.

Version 1 distinguishes two states:

- `mode: template` is the source-template requirement document. It contains no subject revision, execution provenance, release decision, command results, or gate results. It is valid only while implementation evidence is also in template mode and validation does not request a candidate revision.
- `mode: product` is one completed release record generated in an ephemeral product checkout or release workspace.

A product-mode release record is not a replacement for implementation evidence. Implementation evidence declares authoritative commands, gate composition, implementation boundaries, and expected proofs. Release evidence proves that the current command definitions actually ran for one exact revision and that every selected gate passed.

A generated repository cannot satisfy product validation by retaining template release residue. Once implementation evidence becomes product-owned or a candidate revision is supplied, release evidence must also be materialized in product mode.

## Exact revision binding

Product validation requires an explicit lowercase 40-hex Git revision:

```text
python scripts/validate_release_evidence.py --expected-revision <commit-sha>
python -m scripts.validate_release_evidence --expected-revision <commit-sha>
```

The validator compares the supplied revision with `subject.revision`. It does not infer a revision from a CI-provider-specific environment variable and does not run Git commands. Release orchestration must pass the immutable candidate revision explicitly.

The release orchestrator must separately prove that the commands ran from the tree identified by that revision. Copying an arbitrary well-formed SHA into both the record and the validator argument does not establish this association. A suitable product workflow verifies the checked-out immutable revision, rejects source or index changes made after that revision was selected, and only then begins command execution.

This avoids three ambiguity classes:

- evidence generated for an earlier revision cannot approve a later checkout;
- a mutable branch or tag name cannot substitute for an immutable release subject; and
- a clean record cannot be asserted for a worktree whose content differs from the named revision.

A repository should normally materialize product-mode release evidence in an ephemeral checkout or generated artifact after the candidate commands finish. Committing a file that attempts to name its own commit would create a circular self-reference and is not required.

## Command-definition binding

Each command result records:

- the stable `commandId`;
- SHA-256 of the exact UTF-8 command text currently declared by implementation evidence;
- `passed` or `failed`;
- the process exit code;
- UTC start and completion timestamps; and
- a reviewable result locator.

The validator recomputes the SHA-256 digest. Evidence for an old command definition cannot satisfy a gate after command text changes while retaining the same stable ID. Authoritative command text must be encodable as strict UTF-8; escaped lone surrogate code points are rejected as diagnostics rather than causing validator failure.

The contract records command results; it does not execute the command strings. Product CI remains responsible for directly invoking its reviewed commands with the selected runtime and isolation model. The template does not add a generic command dispatcher.

## Producing evidence from execution

A product-owned release workflow should generate result fields from the actual command execution rather than assigning successful values independently of the process result.

For each candidate revision and authoritative command, the workflow should:

1. resolve and verify the immutable checked-out revision;
2. require the index, tracked worktree, and relevant untracked inputs to match that revision before execution;
3. verify that the command ID and command text are the reviewed definitions for that revision;
4. invoke the reviewed executable and argument vector directly;
5. capture the real start time, completion time, stdout, stderr, and process result;
6. normalize the process result into the nonnegative `exitCode` representation required by the contract;
7. derive `status` from that result;
8. calculate `commandDigest` from the exact authoritative command text;
9. persist the detailed result in a reviewable artifact; and
10. place only the contract-required summary and locator in release evidence.

Gate status must be derived from the command results that constitute the gate. The release decision must be derived from the resulting gate set and the product's approval policy. A failed command must not be rewritten as passed, a failed gate must not be rewritten as passed, and a rejected run must not be represented as approved.

The clean-room producer in `tests/generated_release_evidence_producer_fixture.py` demonstrates this boundary for one known fixture command. The test harness creates a fresh Git repository from the generated product tree and supplies the resulting commit. The producer removes inherited `GIT_*` inputs, disables system and global Git configuration, resolves `HEAD^{commit}` through a fixed argument vector, requires equality with the supplied revision, and requires a clean generated tree before invoking `[sys.executable, "product/prove_conformance.py"]`.

The producer accepts only the candidate revision. It does not parse command text or expose a general execution or Git-ref interface. Its Git and proof commands are fixed reviewed argument vectors.

This fixture is not a product release runner. Real products own their revision-verification mechanism, command mapping, runtime isolation, secret handling, result retention, artifact integrity, approval policy, and CI integration.

## Gate closure

Every release gate declared by product-mode implementation evidence must have exactly one gate result. Every command referenced by those gates must have exactly one command result.

Validation rejects:

- missing, duplicate, or unknown command results;
- missing, duplicate, or unknown gate results;
- command digest drift;
- a failed command;
- a nonzero exit code;
- a failed gate;
- a gate whose command did not pass; and
- a release decision other than `approved`.

A command can belong to more than one gate. Its execution result is recorded once and reused by the gate-closure check.

## Provenance and chronology

Product evidence records one execution provenance object:

- `kind`: `ci-run`, `local-run`, or `other`;
- a run identifier;
- a reviewable locator; and
- the UTC time at which the release record was generated.

The release decision records its UTC decision time and a visible explanation.

For each command, completion must not precede start. The approval decision must not precede the latest command completion, and record generation must not precede the decision. Timestamp comparison preserves all one-to-nine fractional-second digits permitted by the schema, so sub-microsecond ordering violations are rejected rather than rounded to equality. These checks prevent a chronologically impossible approval record without assuming a specific CI system.

The clean-room producer derives timestamps in order from actual wall-clock observations and advances a later timestamp by one nanosecond when the clock does not advance. This preserves the contract chronology even on clocks whose observable resolution is coarser than one nanosecond.

## Validation boundary

`scripts/validate_release_evidence.py` supports standalone and module entry points. It first requires:

1. structurally and cross-contract valid repository contracts; and
2. semantically valid implementation evidence.

It then proves:

- template mode is paired only with template implementation evidence and no expected revision;
- template mode does not claim product results;
- product mode uses product implementation evidence;
- the release subject matches the explicitly supplied revision;
- command and gate result coverage is closed;
- command definitions are strict-UTF-8 digest-bound;
- command, gate, exit, and decision outcomes are release-ready;
- result and provenance locators contain visible text; and
- timestamps are chronologically coherent at the schema's full nanosecond precision.

It does not prove that the supplied revision identifies the executing tree, that a command was actually executed, that stdout or stderr are authentic, that a locator exists remotely, that an artifact is immutable, that a CI provider is trustworthy, that evidence is retained for a particular duration, that a deployment occurred, or that a human approval is required. Those policies and integrity controls remain product-owned.

The actual evidence-production fixture closes the local conformance gap by adding revision/worktree verification and connecting a reviewed process result to the version 1 contract fields. It does not convert the validator into an execution engine.

## Clean-room proof

`tests/test_generated_release_evidence_conformance.py` isolates release-validator semantics by materializing product-mode evidence and invoking both copied release validator entry points from the generated repository root. It proves stable failure for:

- an expected-revision mismatch; and
- command-definition digest drift.

`tests/test_generated_release_evidence_production.py` creates immutable generated-product commits, executes the reviewed proof through the fixed producer, and proves:

- a passing process from a clean matching revision produces passing command and gate results, an approved decision, and evidence accepted by both copied validator entry points;
- a failing process committed as its own generated revision produces failed command and gate results, a rejected decision, a nonzero producer exit, and evidence rejected by release validation;
- a supplied revision that differs from generated `HEAD` is rejected before execution;
- an uncommitted generated-tree change is rejected before execution; and
- command-registration drift committed as its own generated revision is rejected before proof execution and before product release evidence is created.

Both suites are template-maintainer-only. A generated product repository retaining the files skips the clean-room classes after its source implementation evidence is in product mode; separate scope regressions verify that boundary.

## Evolution

This family remains at version 1. Actual evidence-production conformance populates the existing fields from execution and does not change accepted document structure or semantic obligations.

Changes to required release fields, revision binding, command digest semantics, result coverage, pass/fail obligations, provenance, chronology, or decision rules change accepted documents or release obligations and require a version increment under `contract-evolution.md`.
