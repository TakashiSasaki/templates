---
id: core.discover-repository-topology-fail-closed
severity: mandatory
overridable: false
order: 45
---
# Discover repository topology fail-closed before mutation

Before planning, modifying, or orchestrating changes in a repository, inspect `contracts/repository-topology.json` at the repository root. If the file is absent, assume single-worktree repository layout. If the file is present, validate it against its schema and invariants: each component branch MUST match its mount path, namespaces MUST be leaf directories without parent-child overlap, direct mutations to the hub branch for orphan component files are PROHIBITED, and synchronization MUST flow strictly from component authority branches to the hub projection. Any schema violation, unknown topology type, branch-mount mismatch, overlapping namespace, or contract corruption MUST halt operations immediately (fail-closed).
