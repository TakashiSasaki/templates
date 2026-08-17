# ADR-0002: Adopt existing repository instructions without destructive replacement

## Status

Accepted and implemented. The original separate `init`/`adopt` user-facing mode model and bootstrap-package layout are superseded by ADR-0007. The migration safety and transactional cutover decisions in this ADR remain applicable.

## Context

Fresh repositories and mature repositories have different preservation requirements. A repository with no existing instruction assets can be brought directly under management, while a repository with handwritten instructions, repository-specific policies, existing skills, verification commands, or CI integration must preserve those assets until their meaning has been reviewed.

That semantic meaning cannot be reconstructed safely by copying or mechanically splitting prose. File creation, hashing, preview generation, cutover, rollback, and lock generation must nevertheless remain deterministic and repeatable outside any particular agent.

## Decision

Repository onboarding has one public operation: **adoption**. Read-only inspection derives the safe strategy from repository state:

- **fresh adoption** for `unmanaged-empty` repositories with no instruction assets that require preservation;
- **migration adoption** for `unmanaged-existing` repositories with handwritten instructions or related policy assets.

The user does not select between `init` and `adopt`. The deterministic mechanics belong to the `agent-policy` CLI in `TakashiSasaki/templates:policy`. Fresh adoption may use the hidden `init` primitive internally. The single `skills/agent-policy/` package orchestrates onboarding through one immutable full-SHA runtime and remains the repository-facing entry point after adoption.

Migration adoption has four explicit phases:

1. `inspect`: classify repository state and inventory relevant files without writing.
2. `prepare`: create adoption configuration, state, project-policy scaffold, and generated preview without replacing the handwritten primary instructions.
3. `preview`: regenerate and verify the preview while reporting whether inventoried source files changed.
4. `finalize`: after separate explicit authorization, preserve the original instructions, switch configured output to the final path, render generated instructions, update the lock, and mark adoption complete.

Fresh adoption can complete directly from preparation to managed state and then run validation/checking. Migration finalization is never selected implicitly by classification or by generic bootstrap `--apply`.

## Responsibility boundary

The CLI is responsible for:

- repository-root and path-boundary enforcement;
- symlink-escape rejection;
- deterministic inventory and SHA-256 hashing;
- schema-valid configuration and adoption-state generation;
- state-derived fresh or migration preparation;
- generated preview rendering;
- source-hash and stale-preview checks;
- atomic backup, cutover, rollback, and lock generation;
- machine-readable diagnostics and idempotent state transitions.

The single `agent-policy` skill is responsible for:

- invoking inspection through the immutable runtime;
- selecting fresh or migration adoption from inspection results;
- reading and interpreting existing policy prose during migration;
- proposing shared profiles and project-policy decomposition;
- helping author project-local policy modules;
- reviewing semantic coverage between handwritten instructions and generated preview;
- invoking only the permitted CLI phase with the selected full-SHA toolchain revision; and
- using `.agent-policy.lock` as the managed repository's toolchain authority after adoption.

The CLI does not use a language model and does not automatically transform free-form instructions into normative policy modules.

## Repository-state model

Inspection classifies a repository as one of:

- `unmanaged-empty`: no `.agent-policy.yml` and no relevant instruction or policy assets;
- `unmanaged-existing`: no `.agent-policy.yml`, but existing instruction or policy assets are present;
- `managed`: `.agent-policy.yml` exists and normal `validate`, `render`, and `check` apply;
- `inconsistent`: partial generated state, conflicting adoption state, unsafe paths, or another condition preventing safe onboarding.

Strategy selection is informational and read-only. Mutation requires explicit `--apply`; migration finalization requires a later, separate explicit command.

## Adoption state and cutover

Migration preparation records a schema-validated state file containing the pinned toolchain repository and full revision, primary instruction path, source hashes, selected profiles, project-policy paths, preview path, verification configuration, and generated-skill selection.

File hashes, not Git ancestry, are the cutover precondition. Preparation renders to a non-conflicting preview path. Finalization requires unchanged source hashes, valid configuration and project policy, a current preview and lock, a safe unused backup path, and a complete successful final render/check plan.

The cutover is transactional. If final rendering, lock creation, state update, or post-render checking fails, the original instruction file and pre-finalization configuration are restored.

Fresh adoption does not require an adoption-state file or migration cutover because there is no handwritten primary instruction to preserve.

## Trust model

ADR-0007 places the repository-facing trust seed in the single `skills/agent-policy/` package. `skills/agent-policy/runtime-manifest.json` records the stable default full SHA and runtime-lock digest, while a managed repository's `.agent-policy.lock` selects its own immutable full SHA.

The trust boundary preserves these constraints:

- only full `TakashiSasaki/templates` commit SHAs are executable toolchain references;
- generic bootstrap exposes no migration-finalization route;
- pin, runtime-lock digest, route, script, installer, cache-identity, and safety-constraint changes receive independent trust-anchor review;
- malformed managed pins fail closed rather than falling back silently; and
- mutable branches and tags are not executable references.

## Consequences

Both fresh and mature repositories use one onboarding concept and one installed repository-facing skill. Mature repositories can adopt `agent-policy` without temporarily discarding existing instructions. The deterministic mechanics can be exercised in tests and CI, while semantic migration remains reviewable and agent-assisted.

The implementation is more complex because migration needs a state machine, generic output checking, transactional finalization, and rollback tests. This complexity is accepted because replacing handwritten instructions is destructive and cannot depend only on natural-language skill guidance.

## Non-goals

This decision does not:

- automatically split or rewrite handwritten policy prose;
- automatically modify arbitrary product-specific skill manifests;
- create, commit, push, merge, deploy, or modify GitHub settings;
- introduce another long-lived bootstrap or adoption branch;
- allow a mutable branch or tag as the executable toolchain reference;
- combine migration preparation and finalization into one unattended operation.
