# Pull-request policy navigation

## Head, CI, and qualification

- [Target branch head freshness](target-branch-head-freshness.md) - Revalidate target freshness before relying on stacked evidence.
- [Exact-head CI evidence](exact-head-ci-evidence.md) - Bind checks to the exact proposed head.
- [CI discovery fail-closed](ci-discovery-fail-closed.md) - Treat missing or ambiguous checks as a blocking uncertainty.
- [Staged CI and preflight](staged-ci-and-preflight.md) - Use cheap local and staged validation before expensive qualification.
- [Defer revision-bound qualification](defer-revision-bound-qualification.md) - Delay expensive evidence until dependency inputs are stable.
- [Reuse valid evidence](reuse-valid-evidence.md) - Reuse only evidence whose bindings still apply.

## Review acquisition and results

- [Review scope selection](review-scope-selection.md) - Select review scope from exact dependencies and affected invariants.
- [Review acquisition preflight](review-acquisition-preflight.md) - Check request state before asking for independent review.
- [Independent exact-head review](independent-exact-head-review.md) - Request independent coverage for the exact final head.
- [Review result discovery](review-result-discovery.md) - Discover current review results and their applicability.
- [Review result applicability](review-result-applicability.md) - Do not transfer review evidence across incompatible heads or scopes.
- [Review reacquisition after disposition](review-reacquisition-after-disposition.md) - Reacquire only evidence invalidated by a material disposition.
- [Review thread closure](review-thread-closure.md) - Close findings with explicit disposition and exact-head context.
- [Stacked review coverage](stacked-review-coverage.md) - Cover dependent PRs without duplicating equivalent requests.

## Completion and merge boundaries

- [Current mergeability](current-mergeability.md) - Treat live mergeability as a current fact, not a historical summary.
- [Final live-state refresh](final-live-state-refresh.md) - Refresh heads, CI, reviews, and dependencies before handoff.
- [Immutable head guard](immutable-head-guard.md) - Stop when the reviewed head no longer matches the proposed head.
- [Post-merge verification](post-merge-verification.md) - Verify landed provenance separately from merge authorization.
