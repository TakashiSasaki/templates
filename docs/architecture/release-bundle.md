# Release bundle and handoff

The `release_bundle` contract defines the minimum provider-neutral manifest handed from completed release validation to a release or deployment system. It does not select a CI provider, artifact store, signing format, attestation service, approval product, deployment platform, retention period, or rollback mechanism.

`release_evidence` and `release_bundle` have different responsibilities:

- `release_evidence` records what commands and gates ran, the exact candidate revision they evaluated, their outcomes, provenance, chronology, and the approval decision.
- `release_bundle` records the exact active contract bytes that accompany that approved record at handoff time.

Keeping these concerns separate avoids a circular digest. A release-evidence document can be one artifact in the bundle. A bundle manifest cannot contain the digest of its own final bytes without a self-reference.

## Contract family

`contracts/release-bundle.json` is registered as contract family `release_bundle` with stable migration slug `release-bundle`.

Version 1 has two modes:

- `mode: template` declares the requirement but contains no candidate revision, provenance, handoff claim, or artifact descriptors.
- `mode: product` identifies one exact candidate revision and one deterministic set of active contract documents that is ready for handoff.

A product-mode bundle contains:

- `subject.revision`: the same lowercase 40-hex candidate revision accepted by release-evidence validation;
- visible subject text explaining what the revision represents;
- generation provenance with a run identifier, locator, kind, and UTC generation time;
- `handoff.status: ready` with a visible explanation; and
- one artifact descriptor for every active domain contract except `release_bundle` itself.

Each artifact descriptor contains the stable contract ID, the exact document path registered by `contracts/manifest.json`, and SHA-256 of the current file bytes.

## Why the bundle is a separate contract

The release record is part of the bundle and therefore cannot also serve as the bundle manifest. A separate manifest provides three locally verifiable properties:

1. the release-evidence bytes are digest-bound rather than merely referenced by a locator;
2. every other active contract document is present exactly once under its registered identity and path; and
3. the handoff set can be compared with the current repository without relying on provider-specific artifact metadata.

The bundle contract satisfies the criteria for a separate family because a generated repository can provide one authoritative current handoff declaration, cross-file coverage and digest failures are locally verifiable, and the shape is independent of framework and provider choices.

The bundle manifest itself is excluded from its `artifacts` array. The external handoff envelope must still carry the manifest alongside the listed artifacts. A product-owned packaging or signing layer may hash or sign the completed manifest as a separate object after it is written.

## Deterministic artifact closure

The validator derives the expected artifact sequence from the active `contracts` entries in `contracts/manifest.json`, excluding only `release_bundle`.

Validation requires:

- exact contract-ID coverage with no missing or unknown entry;
- no duplicate contract IDs or paths;
- manifest order rather than arbitrary array order;
- exact equality between each descriptor path and the registered document path; and
- SHA-256 equality with the current file bytes.

Manifest order is an intentional deterministic serialization rule. It makes independently produced descriptors comparable and prevents the repository-authoritative example from accepting multiple orderings for the same set.

The active set includes `release_evidence`. Consequently, any change to its candidate revision, command results, gate results, provenance, chronology, decision, or formatting changes its file digest and invalidates an older bundle.

The active set also includes implementation evidence and every design contract. A change to command definitions, release-gate composition, implementation boundaries, routes, surfaces, UI states, viewports, or another active contract therefore requires a new bundle even when the candidate revision string is accidentally reused.

## Revision roles

Release workflows commonly expose several immutable revisions. They must not be conflated.

### Candidate revision

The candidate revision is the source revision whose reviewed commands ran and whose approval is recorded by `release_evidence`. Version 1 of `release_bundle` binds this revision in `subject.revision` and requires equality with both:

- the explicit `--expected-revision` validator argument; and
- `release_evidence.subject.revision`.

This is the only revision role asserted by the version 1 bundle contract.

### Merge-test revision

A merge-test revision is a temporary or synthetic revision used to test the proposed result of merging a change. GitHub pull-request merge refs are one example. It can be useful validation evidence, but it is not automatically the release candidate.

A workflow may select a merge commit as its candidate, but that selection must be explicit. Merely running CI on a merge-test revision does not authorize substituting it for the candidate revision named by release evidence.

### Released revision

The released revision is the immutable source identity published by a release system. Depending on the repository strategy, it may equal the candidate revision or a later merge commit. Version 1 does not claim that a release occurred and does not add a released-revision field.

The release system must preserve its own auditable mapping from the accepted bundle to the released revision. If that mapping changes the source revision, the prior candidate bundle cannot be silently relabeled; new release evidence and a new bundle are required for the new candidate.

### Deployed revision

The deployed revision is the immutable source identity observed in a target environment after deployment. It belongs to deployment and post-deployment verification, not pre-release handoff. Version 1 does not claim deployment success or environment state.

A deployment system should compare its observed deployed revision with the released revision and retain that result in product-owned deployment evidence.

## Generation chronology

Bundle generation occurs after release evidence is complete. `provenance.generatedAt` must not precede `release_evidence.provenance.generatedAt`, with one-to-nine fractional-second digits compared at nanosecond precision.

The bundle validator first requires valid implementation evidence and valid approved release evidence. A failed command, failed gate, rejected decision, stale command digest, revision mismatch, or impossible chronology blocks bundle validation before handoff closure can succeed.

A product workflow should therefore perform these stages in order:

1. establish the immutable candidate and execution boundary;
2. execute authoritative commands and derive release evidence;
3. validate release evidence for the explicit candidate revision;
4. compute exact file digests for the active contract set;
5. write the bundle manifest;
6. validate the bundle for the same explicit candidate revision; and
7. hand the manifest and listed bytes to the product-owned release system.

## Mandatory regeneration

A new release bundle is mandatory whenever any input that affects the handoff statement changes. This includes:

- the candidate source revision;
- any authoritative command or release-gate definition;
- command, gate, provenance, chronology, or decision results;
- any active contract document or its registered path;
- the active contract inventory;
- the product's evidence-generation or redaction policy when that policy changes bytes, required artifacts, approval meaning, or accepted locators; and
- any retry that produces a different run, result, decision, or artifact set.

Changing a locator without changing the referenced result still changes the release-evidence bytes and therefore requires a new bundle digest set. A workflow must not patch a previously handed-off manifest in place.

## Rejection, retry, supersession, and rollback

The repository-authoritative product contract represents only one current bundle with `handoff.status: ready`.

- A rejected release run produces no ready bundle. The rejected release evidence may be retained as a product-owned diagnostic artifact, but it cannot satisfy the current release validator or bundle validator.
- A retry is a new execution. It must generate new release evidence and a new bundle rather than rewriting the prior run's outcome.
- A superseded bundle remains immutable in the product-owned archive. It is removed from consideration as the current handoff and replaced by a newly validated ready bundle. The current contract path must not pretend that the superseded bytes are still current.
- A rollback must not mutate the original successful bundle. A product may reuse a previously retained immutable bundle only when the rollback target exactly matches its candidate and artifacts and current policy still accepts it. Otherwise, it must execute the current approval policy for the rollback target and generate new release evidence and a new bundle.

Version 1 intentionally does not define a historical bundle ledger or provider-specific supersession record. The next Phase 3 conformance step will prove local stale, mismatched, and superseded-current diagnostics without choosing an archive or release provider.

## Product-owned controls

The contract does not prescribe:

- artifact packaging format;
- storage location or retention duration;
- encryption, signing, transparency logging, or attestation format;
- human approval workflow;
- secret or personal-data redaction;
- remote locator availability;
- release publication;
- deployment execution; or
- environment verification.

Products own these controls. Their implementation must preserve the bundle's exact bytes and semantic bindings.

Redaction requires particular care. Redacting a bundled contract or release record after digest generation invalidates the bundle. A product must redact before computing digests, ensure the redacted content remains valid under the repository contracts, and then generate a new release record or bundle whenever the redaction changes an authoritative artifact.

## Validation boundary

`scripts/validate_release_bundle.py` supports standalone and module entry points:

```text
python scripts/validate_release_bundle.py --expected-revision <commit-sha>
python -m scripts.validate_release_bundle --expected-revision <commit-sha>
```

In template mode, both run without an expected revision and verify that the template claims no product handoff.

In product mode, validation proves:

- implementation and release evidence are valid;
- an explicit immutable candidate revision was supplied;
- the bundle subject equals that revision and the release-evidence subject;
- handoff status is `ready`;
- bundle generation follows release-evidence generation;
- every active contract except the bundle manifest is present exactly once in manifest order;
- each path matches the manifest; and
- each SHA-256 value matches the current file bytes.

It does not prove that an external archive retained those bytes, that a remote locator resolves, that a signature is trustworthy, that a release or deployment occurred, or that an environment runs the expected revision.

## Evolution

The `release_bundle` family begins at version 1. Changes to required fields, artifact coverage, digest algorithms, ordering, revision semantics, handoff readiness, or chronology change accepted documents or release obligations and require a version increment and migration under `contract-evolution.md`.

Provider-specific storage metadata, signing formats, release identifiers, deployment identifiers, and retention settings remain product-owned unless a future concrete generated-repository failure demonstrates a framework-neutral, locally verifiable need for another contract transition.
