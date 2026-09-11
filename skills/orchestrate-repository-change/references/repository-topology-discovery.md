# Repository topology discovery and fail-closed operational procedure

This reference defines the authoritative operational procedure for discovering repository topology before mutation, planning, or PR orchestration.

## Topology discovery contract

Repositories may define their structural topology using a formal contract at `contracts/repository-topology.json` conforming to `schemas/repository-topology.schema.json`.

1. **Discovery check**:
   Inspect `contracts/repository-topology.json` at the root of the repository.
   - If the file is absent: No explicit Composition topology is selected (`single-worktree` compatibility result). Inspect repository-local authority instructions and Git state; absence never proves a unified history or overrides independent authority routing.
   - If the file is present: The repository operates under an explicit topology model (such as `hub-and-orphan`).

2. **Validation and fail-closed invariants**:
   When `contracts/repository-topology.json` is present, it MUST be validated immediately before any mutation:
   - **Schema validity**: Must conform to `schemas/repository-topology.schema.json`.
   - **Supported topology kind**: Currently supports `hub-and-orphan`. Any unknown kind must halt execution (`UNSUPPORTED_TOPOLOGY_KIND`).
   - **Hub invariants**:
     - `hub.role` MUST be `discovery-projection`.
     - `hub.directMutationForbidden` MUST be `true`. Modifying component files directly on the hub branch is prohibited.
     - `submoduleProjection.selfReferencing` MUST be `true`.
     - `submoduleProjection.mountRule` MUST be `branch-name-equals-mount-path`.
     - `synchronization.direction` MUST be `authority-to-hub`.
     - `synchronization.authorityMustAdvanceBeforeProjection` MUST be `true`.
   - **Component invariants**:
     - Each component's branch name MUST exactly equal its mount path (`branch == mountPath`).
     - All component mount paths MUST be leaf directories with no parent-child nesting or prefix collisions.
     - Component branches must be orphan branches holding isolated authority for their respective subtree.

3. **Operational procedure under Hub-and-Orphan topology**:
   When `hub-and-orphan` is discovered:
   - **Mutation isolation**: Mutations to a component MUST be committed on a branch rooted in that component's orphan authority branch (e.g. `feat/<component>-feature` branched from `<component>`).
   - **PR targeting**: Pull requests for component changes MUST set their base branch to the component authority branch (`--base <component>`).
   - **Hub synchronization**: The hub branch declared by `hub.branch` is never edited directly for component code. After a component PR lands on its authority branch, the hub branch is updated via a submodule projection commit advancing the submodule pointer.
   - **Fail-closed response**: Any discovery error, schema violation, branch/mount mismatch, or contract inconsistency MUST immediately halt operations. Do not attempt heuristic repair or fall back to single-worktree behavior when a corrupt contract is present.

## Semantic authority and operational evidence

Composition owns the schema and validator. Policy bundles their exact bytes from
the immutable revision and paths recorded in
`src/agent_policy/_topology_contract/source.json`. Changes must originate in
Composition and be adopted as a new snapshot; the provenance test compares both
files with that Git revision. Consumer schema contents never override the snapshot.

`discover_repository_topology` validates only the declaration and returns an
operational view. It does not prove Git ancestry or execute Git operations. Before
any mutation, the coding agent must verify the declared Hub and authority refs,
independent component histories, branch/mount correspondence, self-referencing
submodule URLs, and immutable gitlink commits. Discover metadata from those same
gitlinks. Reconcile stale projections before relying on them; never treat copied
Hub files as component authority. Ref deletion/rename requires an explicit plan
covering the declaration, gitlinks, `.gitmodules`, and discovery metadata.
Synchronization is provider-neutral; GitHub Actions is an optional executor.
