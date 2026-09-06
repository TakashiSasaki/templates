# GitHub review-result discovery

This reference is **non-normative GitHub integration guidance** for applying the canonical pull-request review-result discovery and applicability rules. It does not define semantic review completion, finding validity, merge authorization, or a repository-owned review-result schema. The canonical semantics remain under `policy/pull-request/`; current GitHub and connected-tool capabilities remain authoritative for provider fields and transport.

## Observe the review cycle before classifying it

For the review purpose being evaluated, identify the latest applicable review request and its request time, requested candidate identity when available, and provider surface. Do not select a request solely because it is the newest event: distinguish merge-acceptance, diagnostic whole-stack, security, and other explicitly different purposes.

Then inspect the GitHub surfaces that can carry review-result evidence for that cycle:

- submitted pull-request reviews and their bodies;
- ordinary pull-request or issue comments;
- inline review comments;
- resolvable review threads, including their current resolved state and comments;
- review-request / requested-reviewer state or timeline information when it helps identify the cycle;
- reactions on the pull request, review comments, or other relevant objects when the applicable workflow gives them semantic meaning;
- provider-specific completion, failure, limitation, or acknowledgement signals exposed by the current integration.

The list is capability-aware rather than a permanent GitHub schema. Use the current provider/tool contract to discover equivalent surfaces when names or APIs change.

## Reconstruct one logical result

Do not stop after finding one submitted review. Correlate results by reviewer or review system, review purpose, request cycle, timestamps, source references, and revision bindings. A clean review body does not negate an actionable inline thread or ordinary comment. An empty thread list does not negate a body-only or comment-only finding.

Keep independently actionable findings independently dispositionable even when several are carried by one top-level body or ordinary comment. Use `github-review-finding-representation.md` for remediation-friendly representation guidance without redefining finding semantics.

## Interpret reactions conservatively

A reaction has result semantics only when the applicable workflow, review procedure, or provider contract defines that meaning. For example, an acknowledgement-style reaction may demonstrate that a request was noticed if the integration documents that behavior, but it must not be promoted to completed review, approval, or `no findings` without a documented semantic contract.

Otherwise classify the reaction as uninterpreted provider state or as corroboration for separately established evidence. Preserve the underlying event for traceability without inventing meaning from its glyph.

## Bind the result to the candidate revision

When a submitted review or provider result exposes a commit ID, head SHA, stack tip, or equivalent candidate identity, compare it with the current proposed candidate before relying on it. For merge-acceptance evidence governed by the canonical independent exact-head rule, require equality with the current PR head unless the canonical stacked-coverage rule explicitly supplies the required cumulative bindings.

If the current head differs, classify the completed review as stale for exact-head merge acceptance. If no reviewed identity can be established, classify applicability as unknown and keep completion/no-findings fail-closed. Do not erase older findings merely because completion evidence became stale; re-evaluate each finding's causal condition against the current candidate.

## Suggested adapter classification

The GitHub adapter may use the following provider-facing classifications while gathering evidence:

- `REVIEW_NOT_REQUESTED`;
- `REVIEW_PENDING`;
- `REVIEW_COMPLETE_NO_FINDINGS`;
- `REVIEW_COMPLETE_WITH_FINDINGS`;
- `REVIEW_EVIDENCE_STALE`;
- `REVIEW_APPLICABILITY_UNKNOWN`.

These are execution classifications, not new Policy authority. Project them into the canonical merge-gate authorization states only after the required discovery, purpose, revision, independence, and finding-disposition checks succeed.
