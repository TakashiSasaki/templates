<!-- agent-policy-generated: true -->
# Repository topology discovery and fail-closed operational procedure

This reference defines the authoritative operational procedure for discovering repository topology before mutation, planning, or PR orchestration.

## Topology discovery contract

Repositories may define their structural topology using a formal contract at `contracts/repository-topology.json` conforming to `schemas/repository-topology.schema.json`.

1. **Discovery check**:
   Inspect `contracts/repository-topology.json` at the root of the repository.
   - If the file is absent: The repository operates under the conventional `single-worktree` topology. All mutations, branches, and PRs target the primary development branch in a unified worktree.
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
   - **Hub synchronization**: The hub branch (`main`) is never edited directly for component code. After a component PR lands on its authority branch, the hub branch is updated via a submodule projection commit advancing the submodule pointer.
   - **Fail-closed response**: Any discovery error, schema violation, branch/mount mismatch, or contract inconsistency MUST immediately halt operations. Do not attempt heuristic repair or fall back to single-worktree behavior when a corrupt contract is present.
