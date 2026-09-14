# Local-checkout topology discovery and live verification

`contracts/local-checkout-topology.json` is independent from repository topology. Its absence means no explicit local-checkout topology is selected; it does not imply a single worktree, a repository root, or any default directory layout. A valid declaration is intent, not evidence that current Git state satisfies it.

For `bare-worktree`, use the Composition-pinned adapter in `agent_policy.local_checkout` to validate the declaration before operational use. Before creating, switching, or otherwise mutating worktrees, independently verify all of the following from live Git state:

1. the declared common Git directory is a safe, bare Git directory;
2. the workspace root is distinct from every worktree root;
3. Git's linked-worktree inventory, rather than guessed directory names, contains only sibling directories under that workspace root;
4. the target local branch is not occupied by another linked worktree; and
5. the effective current worktree root is not assumed to equal the workspace or repository root.

HEAD, index, and working-directory state are worktree-specific. Refs, configuration, fetch, garbage collection, and object storage are common-repository state, so parallel worktrees are not independent repositories. Dependency directories, global caches, containers, and other external state remain outside the pattern's isolation guarantee.

The declaration does not enumerate active branches or worktrees. Do not write such ephemeral state into it. Reject malformed declarations, unsafe/symlinked paths, unsupported kinds, and live-state contradictions fail-closed. The root `.git` indirection file is optional convenience, not a required live-state invariant; `.bare/` is a declaration value/example, not a fixed required path.
