# Repository Topology Architecture: Hub-and-Orphan

This document details the architectural design and operational contract of the Hub-and-Orphan repository topology.

## Architectural Purpose

Traditional monolithic repositories couple all component histories into a single branching line. In contrast, the Hub-and-Orphan pattern separates component revision histories into distinct, rootless (orphan) Git branches while maintaining an integrated development and discovery projection via a self-referencing Hub branch.

## Key Rules and Invariants

### 1. Hub Role and Authority Boundary
- The Hub branch (typically `main`) is solely a **discovery and integration projection**.
- Component authority resides exclusively on the respective orphan branch.
- Mutating component files directly on the Hub branch without advancing the component branch authority is an invariant violation.

### 2. Branch Identity and Submodule Mount Invariant
- **Rule**: `branch == mountPath`.
- Every component submodule mounted at path `P` in the Hub must track orphan branch `P`.
- Self-referencing submodule URLs point to the repository itself (`.` or canonical remote).

### 3. Leaf-Only Namespace Rule
- Component namespaces must be mutually disjoint leaf paths.
- Nested component paths (e.g. `packages` and `packages/core`) are prohibited because Git submodules and file trees cannot cleanly nest overlapping boundaries.

### 4. Mutation and Synchronization Ordering
- **Authority First**: Any code modification must be authored, tested, and merged into the component's orphan branch.
- **Hub Synchronization**: After the component authority commit is created, the Hub submodule pointer is updated to point to the new commit SHA.
- **Direction**: Strictly `authority -> Hub`.

## Contract and Validation

- Contract: `contracts/repository-topology.json`
- Schema: `schemas/repository-topology.schema.json`
- Validator: `.template-composition/validators/validate_repository_topology.py`

## Declaration and execution boundary

Selection declares intended consumer topology; it does not prove that Git already
implements it. Composer only materializes files. It does not create or switch
branches, update refs, mutate `.git`, run arbitrary hooks, or update remote submodules.
Policy and the coding agent verify actual Git state and perform separately authorized
operations. The Hub name comes from `hub.branch`; `main` is only a seed example.

Synchronization is provider-neutral. GitHub Actions may implement it, but is not
part of topology identity. A projection records the immutable component commit in
a submodule gitlink, then derives discovery metadata from that same gitlink.
A stale projection must remain identified as stale, never become a second content
authority. Rename/deletion requires an explicit authority migration and coordinated
contract, gitlink, `.gitmodules`, and discovery updates; no automatic deletion or
rename executor is provided by this component.
