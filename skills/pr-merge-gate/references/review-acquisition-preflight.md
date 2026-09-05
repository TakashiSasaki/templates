# Revision-bound review acquisition preflight

This reference is GitHub-facing procedure support for `pr-merge-gate`. Canonical semantics remain in `policy/pull-request/review-acquisition-preflight.md`; this file only describes the minimum live-state checks needed to avoid sending a reviewer stale or unresolvable revision bindings.

## Single pull request

Immediately before intentionally invoking a reviewer for a specific candidate:

1. read the current pull request head SHA;
2. verify it equals the intended reviewed SHA;
3. if the reviewer request names or depends on a branch/ref, verify that ref currently resolves to the same SHA;
4. if the request text records an exact head, use the full current SHA rather than a historical or shortened identity when the mechanism permits it; and
5. construct the request only from the refreshed binding.

If the PR head moved, the ref cannot be resolved, or the ref resolves to a different commit, do not invoke the reviewer with the stale binding. Refresh only the affected state, repair the request, and continue. Do not create a no-op commit or move a branch merely to make an old requested SHA resolvable.

## Whole-stack or cumulative request

When one request is intentionally scoped to an ordered stack, preflight every identity the request claims to bind:

- integration/base revision when explicitly part of the review contract;
- ordered member list and parent/base relationship;
- each member's current exact head SHA;
- stack tip exact SHA; and
- the PR on which the request is being posted.

A lower-member head movement can make a previously prepared stack request stale even when the tip PR number is unchanged. Reconstruct the binding set from current live state before invocation rather than copying an earlier status report.

Do not turn this into an ancestry algorithm that the repository does not require. Verify only the topology and identities necessary for the declared review contract and current repository authority.

## Provider result boundary

A successful preflight establishes only that the request was constructed against resolvable current identities. It does not establish that the provider accepted the request, that analysis started, that analysis completed, that the resulting review covered those identities, or that merge acceptance evidence exists.

If the provider later reports an invocation/ref failure, record that as acquisition failure rather than as a clean or completed review. Refresh the affected identity facts before retrying; do not blindly repost the same request.

## Latency discipline

The preflight should be one bounded live-state refresh at the review-acquisition boundary. Do not add a fixed waiting period, repeated polling for reassurance, or unrelated repository reads. If exact-head required CI is still pending under the selected completion procedure, complete that qualification first rather than preflighting a review request that is not yet authorized to be sent.
