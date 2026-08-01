# ADR-0002: Adopt existing repository instructions without destructive replacement

## Status

Accepted and implemented. Repository-layout details are updated by ADR-0004.

## Context

`agent-policy init` is safe for repositories that do not already contain agent instructions. It refuses to overwrite a handwritten `AGENTS.md`, which is correct for initialization but leaves mature repositories without a supported migration path.

Existing repositories may already contain handwritten instruction files, repository-specific policies, generated or handwritten skills, verification commands, and CI integration. Their meaning cannot be reconstructed safely by copying or mechanically splitting prose. File creation, hashing, preview generation, cutover, rollback, and lock generation must nevertheless remain deterministic and repeatable outside any particular agent.

## Decision

Repository onboarding has two modes:

- `init`: initialize an unmanaged repository that has no conflicting handwritten instruction output.
- `adopt`: migrate an unmanaged repository that already has handwritten instructions or related policy assets.

The deterministic adoption mechanics belong to the `agent-policy` CLI in `TakashiSasaki/templates:policy`. The integrated `skills/bootstrap-agent-policy/` package orchestrates either `init` or `adopt` by invoking one full, pinned `TakashiSasaki/templates` commit SHA.

The CLI adoption workflow has four explicit phases:

1. `inspect`: classify repository state and inventory relevant files without writing.
2. `prepare`: create adoption configuration, state, project-policy scaffold, and generated preview without replacing the handwritten primary instructions.
3. `preview`: regenerate and verify the preview while reporting whether inventoried source files changed.
4. `finalize`: after separate explicit authorization, preserve the original instructions, switch configured output to the final path, render generated instructions, update the lock, and mark adoption complete.

Dry-run is the default for `init`, `adopt prepare`, and `adopt finalize`. `adopt preview` is an explicit regeneration operation. `finalize` is never selected implicitly by classification or by generic bootstrap `--apply`.

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

The bootstrap skill is responsible for:

- selecting `init` or `adopt` from inspection results;
- reading and interpreting existing policy prose;
- proposing shared profiles and project-policy decomposition;
- helping author project-local policy modules;
- reviewing semantic coverage between handwritten instructions and generated preview;
- invoking only the permitted CLI phase with the pinned toolchain revision.

The CLI does not use a language model and does not automatically transform free-form instructions into normative policy modules.

## Repository-state model

Inspection classifies a repository as one of:

- `unmanaged-empty`: no `.agent-policy.yml` and no relevant instruction or policy assets;
- `unmanaged-existing`: no `.agent-policy.yml`, but existing instruction or policy assets are present;
- `managed`: `.agent-policy.yml` exists and normal `validate`, `render`, and `check` apply;
- `inconsistent`: partial generated state, conflicting adoption state, unsafe paths, or another condition preventing safe onboarding.

Automatic mode selection is informational and read-only. A write operation must explicitly choose `init` or `adopt`.

## Adoption state and cutover

Preparation records a schema-validated state file containing the pinned toolchain repository and full revision, primary instruction path, source hashes, selected profiles, project-policy paths, preview path, verification configuration, and generated-skill selection.

File hashes, not Git ancestry, are the cutover precondition. Preparation renders to a non-conflicting preview path. Finalization requires unchanged source hashes, valid configuration and project policy, a current preview and lock, a safe unused backup path, and a complete successful final render/check plan.

The cutover is transactional. If final rendering, lock creation, state update, or post-render checking fails, the original instruction file and pre-finalization configuration are restored.

## Trust model

The bootstrap package is integrated under `skills/bootstrap-agent-policy/` rather than maintained as a separate orphan branch. This supersedes the original layout assumption without weakening the trust boundary:

- the manifest pins a full `TakashiSasaki/templates` commit SHA;
- the route set omits finalization;
- pin, route, script, installer, and safety-constraint changes receive independent trust-anchor review;
- mutable branches and tags are not executable references.

## Consequences

Mature repositories can adopt `agent-policy` without temporarily discarding existing instructions. The deterministic mechanics can be exercised in tests and CI, while semantic migration remains reviewable and agent-assisted.

The implementation is more complex because it needs a state machine, generic output checking, transactional finalization, and rollback tests. This complexity is accepted because replacing handwritten instructions is destructive and cannot depend only on natural-language skill guidance.

## Non-goals

This decision does not:

- automatically split or rewrite handwritten policy prose;
- automatically modify arbitrary product-specific skill manifests;
- create, commit, push, merge, deploy, or modify GitHub settings;
- introduce another long-lived bootstrap or adoption branch;
- allow a mutable branch or tag as the executable toolchain reference;
- combine preparation and finalization into one unattended operation.
