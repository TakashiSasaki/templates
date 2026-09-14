# Workspace and local-checkout topology

Repository topology and workspace topology answer different questions.

| Axis | Composition-owned choice | What it describes |
| --- | --- | --- |
| Repository topology | Hub-and-Orphan | Repository authority, branch history, and projection structure. |
| Workspace / local-checkout topology | Bare Worktree | How one local workspace materializes a bare common Git repository and linked worktrees. |

They compose independently: **Hub-and-Orphan × Bare Worktree** is a valid combination. Selecting neither declaration does not infer a default repository or local checkout layout.

The normative Bare Worktree contract, invariants, and validator remain [Composition-owned](../../workspace/bare-worktree/). This Site page is only reader navigation and orientation. A declaration expresses intended local-checkout semantics; live Git/worktree verification is a separate operational concern.
