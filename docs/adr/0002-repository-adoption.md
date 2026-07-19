# ADR-0002: Adopt existing repository instructions without destructive replacement

## Status

Accepted and implemented.

## Context

`agent-policy init` is safe for repositories that do not already contain agent instructions. It refuses to overwrite a handwritten `AGENTS.md`, which is the correct behavior for initialization but leaves mature repositories without a supported migration path.

Existing repositories may already contain handwritten instruction files, repository-specific policies, generated or handwritten skills, skill manifests, verification commands, and CI integration. Their meaning cannot be reconstructed safely by copying or mechanically splitting prose. At the same time, file creation, hashing, preview generation, cutover, rollback, and lock generation must be deterministic and repeatable outside any particular agent.

The directly cloneable `bootstrap-agent-policy` orphan branch is already the trust seed for unmanaged repositories. Adding a separate adoption branch would duplicate the manifest, pinned-toolchain invocation, installation scripts, tests, and trust-anchor review process.

## Decision

Repository onboarding has two modes:

- `init`: initialize an unmanaged repository that has no conflicting handwritten instruction output.
- `adopt`: migrate an unmanaged repository that already has handwritten instructions or related policy assets.

The deterministic adoption mechanics belong to the CLI on `main`. The `bootstrap-agent-policy` orphan branch remains the single onboarding skill package and orchestrates either `init` or `adopt` by invoking one full, pinned `main` commit SHA.

The CLI adoption workflow has four explicit phases:

1. `inspect`: classify repository state and inventory relevant files without writing.
2. `prepare`: create an adoption configuration, state record, project-policy scaffold, and generated preview without replacing the handwritten primary instruction file.
3. `preview`: regenerate and verify the preview while reporting whether inventoried source files changed.
4. `finalize`: after explicit authorization, atomically preserve the original instruction file, switch the configured output to its final path, render generated instructions, update the lock, and mark adoption complete.

Dry-run is the default for `init`, `adopt prepare`, and `adopt finalize`. `adopt preview` is an explicit regeneration operation for prepared generated artifacts. `finalize` is never selected implicitly by automatic repository classification or by a generic bootstrap `--apply` operation.

## Responsibility boundary

The CLI is responsible for:

- repository-root and path-boundary enforcement;
- symlink-escape rejection;
- deterministic inventory and SHA-256 hashing;
- schema-valid configuration and adoption-state generation;
- generated preview rendering;
- source-hash and stale-preview checks;
- atomic backup, cutover, rollback, and lock generation;
- machine-readable diagnostics and idempotent state transitions.

The bootstrap agent skill is responsible for:

- selecting `init` or `adopt` from CLI inspection results;
- reading and interpreting existing policy prose;
- proposing shared profiles and project-policy decomposition;
- helping author project-local policy modules;
- reviewing semantic coverage between handwritten instructions and the generated preview;
- invoking only the permitted CLI phase with the pinned toolchain revision.

The CLI does not use a language model and does not automatically transform free-form instructions into normative policy modules.

## Repository-state model

The inspection phase classifies a repository as one of:

- `unmanaged-empty`: no `.agent-policy.yml` and no relevant existing instruction or policy assets;
- `unmanaged-existing`: no `.agent-policy.yml`, but existing instruction or policy assets are present;
- `managed`: `.agent-policy.yml` exists and normal `validate`, `render`, and `check` operations apply;
- `inconsistent`: partial generated state, conflicting adoption state, unsafe paths, or another condition that prevents safe onboarding.

Automatic mode selection is informational and read-only. A write operation must explicitly choose `init` or `adopt`.

## Adoption state

Preparation records a generated, schema-validated adoption-state file under `.agent-policy/`. It includes:

- the pinned toolchain repository and full revision;
- the phase and completion state;
- the primary handwritten instruction path;
- inventoried source paths and byte hashes;
- selected profiles;
- preview and final output paths;
- the repository revision when available as non-authoritative context.

File hashes, not Git ancestry, are the cutover precondition. Unrelated working-tree changes do not automatically block adoption, but changes to inventoried source files do.

## Preview and cutover

Preparation renders to a non-conflicting preview path, initially `.agent-policy/preview/AGENTS.md`. The normal renderer and checker treat configured output paths generically rather than special-casing `AGENTS.md`.

Finalization requires all of the following:

- the handwritten source hash still matches the prepared state;
- configuration and project policy validate;
- the preview is current for the recorded inputs and toolchain;
- the backup path is inside the repository and does not already conflict;
- no non-generated file would be overwritten except the explicitly selected primary instruction after it is preserved;
- render and check can complete for the final configuration.

The cutover is transactional. If final rendering, lock creation, state update, or post-render checking fails, the original instruction file and pre-finalization configuration are restored.

## Branch and trust model

No third long-lived or unrelated branch is added.

- `main` contains the CLI, schemas, renderer, adoption state machine, tests, and documentation.
- `bootstrap-agent-policy` remains the directly cloneable onboarding skill and trust seed.

The bootstrap manifest pins a full `main` commit SHA. Updating that SHA is a separate trust-anchor change and must be reviewed independently from ordinary policy or CLI changes.

## Implementation

The four `agent-policy adopt` phases are implemented and tested on `main`. The `bootstrap-agent-policy` branch performs read-only classification, requires an explicit route for mutation, applies either initialization or adoption preparation, and deliberately exposes no automatic finalization route.

## Consequences

Mature repositories can adopt `agent-policy` without temporarily discarding their existing instructions. The same mechanics can be exercised in tests and CI, while semantic migration remains reviewable and agent-assisted.

The implementation is more complex because it needs a state machine, generic output checking, transactional finalization, and rollback tests. This complexity is accepted because replacing handwritten instructions is a destructive operation and cannot depend only on natural-language skill guidance.

## Non-goals

This decision does not:

- automatically split or rewrite handwritten policy prose;
- automatically modify arbitrary product-specific skill manifests;
- create, commit, push, merge, deploy, or modify GitHub settings;
- introduce another orphan branch;
- allow a mutable branch or tag as the executable toolchain reference;
- combine preparation and finalization into one unattended operation.
