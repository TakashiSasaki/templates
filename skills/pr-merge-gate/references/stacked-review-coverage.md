# Stacked review coverage

This reference is provider-neutral procedure support for the pull-request merge gate. The canonical pull-request policy remains authoritative.

Use individual independent exact-head review as the ordinary per-member merge-acceptance path. Treat whole-stack review as an architecture, dependency, overlap/gap, completeness, final-state, and test-sufficiency audit unless the same completed review also establishes every cumulative binding below. Cumulative multi-member acceptance review is an optional optimization, not a stacked-progression requirement.

For a cumulative review, record an evidence envelope containing:

- integration base exact SHA and tree;
- ordered stack membership;
- each member branch and exact head SHA;
- stack tip exact SHA;
- cumulative reviewed scope;
- review contract;
- reviewer independence and review identity;
- review completion state; and
- material limitations.

A tip-only review, approval state, empty review list, or review request does not prove lower-member coverage. Match every member claimed as covered to explicit evidence in the envelope. If a member is absent, a head is ambiguous, the order differs, the scope is incomplete, or the contract and reviewer independence cannot be established, classify coverage as incomplete and keep merge authorization fail-closed.

When the provider cannot establish lower-member cumulative coverage clearly, preserve any useful audit findings and fall back to individual exact-head review for uncovered members when review acquisition is authorized. Do not create a repeated cumulative-review or clarification loop merely to regain multi-member acceptance coverage.

Re-evaluate applicability on member head movement, stack reordering, integration-base movement, cumulative-scope change, or review-contract change. Reuse an unchanged evidence item only when its own bindings and remaining stack applicability are known to hold. Lower-member merge may move a later member's base; evaluate that movement rather than applying an unconditional all-evidence invalidation rule or rewriting the upper head solely because the lower member merged.
