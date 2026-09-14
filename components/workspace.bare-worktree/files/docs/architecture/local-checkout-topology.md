# Local-checkout topology

`workspace.bare-worktree` owns the intended local-checkout topology contract. It is independent from `topology.hub-and-orphan`, which owns repository authority, history, and projection semantics. A consumer can therefore select both: **Hub-and-Orphan × Bare Worktree**.

The declaration records no active worktree or branch inventory. Before mutating a checkout, an operational consumer must independently resolve the common Git directory, identify the current worktree and workspace root, enumerate linked worktrees from Git, verify target-branch occupancy, and account for shared refs, configuration, fetch, and maintenance effects. It must not infer `repository root == worktree root`.

The schema validates the declaration's shape and safe relative common-Git-directory path. The managed validator rejects symlinked declaration inputs. Neither validates that a declared directory currently exists, is bare, or has the declared linked worktrees; those are live-state facts.
