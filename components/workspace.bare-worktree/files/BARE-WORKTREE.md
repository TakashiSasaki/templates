# Bare Worktree Pattern

## Normative semantics

The **Bare Worktree Pattern** uses one bare Git repository as the common Git repository and materializes selected working branches as sibling linked worktrees under a common workspace root.

In this document, **workspace root** is the non-worktree directory that contains the common Git directory and linked-worktree directories. The **common Git directory** is the bare Git repository. A **linked worktree** is one checkout registered with that common Git directory; its **worktree directory** is the directory containing its working files. A **Git branch name** identifies a ref; a **worktree administrative ID** is Git-managed implementation metadata. A **repository topology** describes authority, history, and projection structure. A **local-checkout/workspace topology** describes materialization on a machine. These are distinct axes.

The pattern has these requirements:

1. The common repository MUST be bare and MUST NOT have a working tree of its own.
2. Branches selected for active work MUST be materialized as linked worktrees. Linked worktree directories MUST be sibling directories directly under the workspace root; the workspace root itself MUST NOT be a working tree.
3. A branch name and a worktree directory name MUST be treated as separate identifiers. Automation MUST NOT depend on Git's internal `$GIT_DIR/worktrees/<id>` administrative naming.
4. The pattern MUST NOT check out the same local branch in more than one worktree. Git force mechanisms do not relax this pattern requirement. A remote branch intended for normal work SHOULD normally have a corresponding local tracking branch.
5. HEAD, index, and working-directory state are worktree-specific. Object storage, refs, and repository-wide configuration/state are shared through the common repository. Linked worktrees are therefore not independent repositories.
6. Operations such as fetch, ref updates, configuration changes, and garbage collection can affect other linked worktrees through shared state. Dependency directories, global caches, containers, and other external state are outside this pattern's isolation guarantee.
7. Storage efficiency is relative to multiple full clones. Each worktree can still duplicate checked-out files, dependencies, and build artifacts.

The root `.git` indirection file is an optional convenience, not a Bare Worktree invariant. Likewise, `.bare/` is the seed example's configurable common-Git-directory path, not a fixed canonical path.

## Declaration boundary

`contracts/local-checkout-topology.json` declares intended local-checkout semantics. It does not prove the current Git state, enumerate active worktrees, or list active branches. Declaration validation and live Git/worktree verification are separate operations.

## Non-normative setup example

One conventional layout places a bare repository at `.bare/`, a root `.git` indirection file for convenience, and linked worktrees such as `composition/`, `policy/`, and `site/` beside it. The directory labels in that example are not branch identities; discover actual registrations and branch occupancy from Git before operations.
