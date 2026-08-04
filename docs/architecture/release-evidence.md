# Release evidence

The release-evidence contract binds one exact product revision to the commands and release gates declared by `contracts/implementation-evidence.json`. It records completed execution and an approval decision without selecting a framework, test runner, package manager, CI provider, artifact store, deployment platform, or release orchestration product.

## Contract family

`contracts/release-evidence.json` is registered as contract family `release_evidence` with stable migration slug `release-evidence`.

Version 1 distinguishes two states:

- `mode: template` is the source-template requirement document. It contains no subject revision, execution provenance, release decision, command results, or gate results.
- `mode: product` is one completed release record generated in an ephemeral product checkout or release workspace.

A product-mode release record is not a replacement for implementation evidence. Implementation evidence declares authoritative commands, gate composition, implementation boundaries, and expected proofs. Release evidence proves that the current command definitions actually ran for one exact revision and that every selected gate passed.

## Exact revision binding

Product validation requires an explicit lowercase 40-hex Git revision:

```text
python scripts/validate_release_evidence.py --expected-revision <commit-sha>
python -m scripts.validate_release_evidence --expected-revision <commit-sha>
```

The validator compares the supplied revision with `subject.revision`. It does not infer a revision from a CI-provider-specific environment variable and does not run Git commands. Release orchestration must pass the immutable candidate revision explicitly.

This avoids two ambiguity classes:

- evidence generated for an earlier revision cannot approve a later checkout; and
- a mutable branch or tag name cannot substitute for an immutable release subject.

A repository should normally materialize product-mode release evidence in an ephemeral checkout or generated artifact after the candidate commands finish. Committing a file that attempts to name its own commit would create a circular self-reference and is not required.

## Command-definition binding

Each command result records:

- the stable `commandId`;
- SHA-256 of the exact UTF-8 command text currently declared by implementation evidence;
- `passed` or `failed`;
- the process exit code;
- UTC start and completion timestamps; and
- a reviewable result locator.

The validator recomputes the SHA-256 digest. Evidence for an old command definition cannot satisfy a gate after command text changes while retaining the same stable ID.

The contract records command results; it does not execute the command strings. Product CI remains responsible for directly invoking its reviewed commands with the selected runtime and isolation model. The template does not add a generic command dispatcher.

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

For each command, completion must not precede start. The approval decision must not precede the latest command completion, and record generation must not precede the decision. These checks prevent a chronologically impossible approval record without assuming a specific CI system.

## Validation boundary

`scripts/validate_release_evidence.py` supports standalone and module entry points. It first requires:

1. structurally and cross-contract valid repository contracts; and
2. semantically valid implementation evidence.

It then proves:

- template mode does not claim product results;
- product mode uses product implementation evidence;
- the release subject matches the explicitly supplied revision;
- command and gate result coverage is closed;
- command definitions are digest-bound;
- command, gate, exit, and decision outcomes are release-ready;
- result and provenance locators contain visible text; and
- timestamps are chronologically coherent.

It does not verify that a locator exists remotely, that a CI provider is trustworthy, that an artifact is retained for a particular duration, that a deployment occurred, or that a human approval is required. Those policies remain product-owned.

## Clean-room proof

`tests/test_generated_release_evidence_conformance.py` reuses the generated product fixture, materializes product-mode release evidence, and invokes both copied release validator entry points from the generated repository root.

The fixture also proves stable failure for:

- an expected-revision mismatch; and
- command-definition digest drift.

The suite is template-maintainer-only. A generated product repository retaining the test file skips this clean-room class after its source implementation evidence is in product mode; a separate scope regression verifies that boundary.

## Evolution

This family starts at version 1 and has no migration artifact.

Changes to required release fields, revision binding, command digest semantics, result coverage, pass/fail obligations, provenance, chronology, or decision rules change accepted documents or release obligations and require a version increment under `contract-evolution.md`.
