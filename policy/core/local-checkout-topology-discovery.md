---
id: core.discover-local-checkout-topology-fail-closed
severity: mandatory
overridable: false
order: 46
---
# Discover local-checkout topology separately from repository topology

Before a mutation whose safety depends on local checkout layout, inspect
`contracts/local-checkout-topology.json` independently from
`contracts/repository-topology.json`. Absence selects no explicit local-checkout
topology and never infers a default workspace layout. A present but unreadable,
unsafe, malformed, unsupported, or contradicted declaration must halt dependent
operations.

Composition owns local-checkout semantics. Consume the immutable schema and
validator snapshot identified in `agent_policy/_local_checkout_contract/source.json`;
consumer files cannot weaken it. Declaration validation proves only the intended
pattern, not current Git state.

For a declared Bare Worktree pattern, independently resolve and verify the common
Git directory, current worktree root, workspace root, linked-worktree inventory,
and target-branch occupancy using Git state. Never assume repository root equals
worktree root. Treat HEAD/index/working-directory state as worktree-specific and
refs, config, fetch, maintenance, and object storage as shared common-repository
state. Reject unsafe/symlinked declaration paths and any required live-state
contradiction before mutation.
