---
name: pr-merge-gate
description: Enforce fail-closed exact-head CI, independent review, review-thread, base-drift, and final live-state checks before merging a repository pull request.
---

# Pull Request Merge Gate

## Purpose

Provide the final authorization boundary for merging a pull request. This skill is intentionally stricter than ordinary implementation self-audit: it distinguishes missing review from a clean review, binds CI and review evidence to the exact current head, refreshes live state immediately before merge, and requires the merge API to reject a moved head.

This skill does not define feature semantics. Current repository code, schemas or contracts, validators, tests, workflows, release rules, and task-specific documentation remain authoritative for what the pull request must implement and verify.

## Use when

Use this skill whenever:

- a pull request is about to be declared merge-ready;
- the user asks to merge, finish, complete, or carry a pull request through merge;
- CI or external review is pending and final acceptance must be resumed later in the same task;
- a repair or base update changed the PR head after earlier acceptance evidence was collected.

## Do not use when

Do not use this skill to:

- replace task-specific implementation or validation work;
- treat self-review as the required independent review;
- waive a missing reviewer because the review service is unavailable;
- infer merge readiness from historical PR bodies or old green runs;
- modify product or repository semantics merely to satisfy the merge process.

## Canonical authorities

Read live state from the current pull request and target branch, including:

- PR number, base branch/base SHA, and current exact head SHA;
- current target-branch head SHA;
- effective PR diff and changed files;
- current workflow definitions and all checks applicable to the exact head;
- completed external review evidence and the exact commit it reviewed;
- submitted reviews and inline review threads, including unresolved state;
- repository mergeability at the final gate.

Current repository code, tests, workflow definitions, and canonical documentation determine semantic acceptance. Historical review or CI evidence is never authority for a changed head.

## Inputs

Record at the beginning of every gate pass:

1. PR number and title;
2. base branch and PR base SHA;
3. current target-branch head SHA;
4. current exact PR head SHA;
5. intended semantic scope and effective changed-file set;
6. exact-head required check state;
7. review-request state;
8. completed independent review evidence and reviewed SHA, if any;
9. unresolved review-thread count and dispositions;
10. current mergeability.

If the PR head changes, discard this snapshot and start a new gate pass.

## State model

The allowed success path is:

`PR_OPEN -> SCOPE_AUDITED -> CI_GREEN -> REVIEW_REQUESTED -> REVIEW_COMPLETED -> FINDINGS_CLEARED -> FINAL_STATE_REFRESHED -> MERGE_ALLOWED`

Do not skip states. In particular:

- `CI_GREEN -> MERGE_ALLOWED` is forbidden;
- `REVIEW_REQUESTED -> MERGE_ALLOWED` is forbidden;
- `reviews = 0 -> MERGE_ALLOWED` is forbidden;
- absence of review findings is not evidence that review occurred.

Use explicit blocked states when the success path cannot advance:

- `BLOCKED_CI`: a required exact-head check is missing, pending, failed, stale, or unjustifiably skipped;
- `BLOCKED_REVIEW_MISSING`: no completed independent review exists;
- `BLOCKED_REVIEW_PENDING`: review was requested but has not completed;
- `BLOCKED_REVIEW_STALE`: relied-upon review applies to an older head;
- `BLOCKED_REVIEW_FINDINGS`: a material review finding or thread remains unresolved;
- `BLOCKED_BASE_DRIFT`: target-branch movement has not been evaluated or reconciled;
- `BLOCKED_HEAD_CHANGED`: live head no longer equals the head whose final evidence was accepted;
- `BLOCKED_MERGEABILITY`: repository state does not currently allow merge.

## Workflow

### 1. Audit scope

Compare the PR against its base. Confirm the changed-file set is intentional, no temporary/debug/generated artifacts leaked into the diff, and the PR body describes the actual semantic scope. Do not treat a tidy commit history as a substitute for a correct diff.

### 2. Establish exact-head CI

Discover required checks from current workflow definitions and changed scope rather than from a historical checklist. Every relied-upon result must apply to the current exact PR head. A run for an older head is historical evidence only.

Do not advance beyond `CI_GREEN` while any required exact-head check is missing, pending, failed, stale, or incorrectly skipped.

### 3. Require an independent review

Request external review for the current exact head when no completed review for that head exists. The review request must identify the exact head SHA so the target is unambiguous.

A request comment, reviewer assignment, pending review, empty review list, or absence of findings is not a completed review. If completed independent review evidence count is zero, return `BLOCKED_REVIEW_MISSING` or `BLOCKED_REVIEW_PENDING`; never report the review gate clean.

The implementing agent's own self-review does not satisfy this requirement. If the required reviewer or review system is unavailable, remain blocked rather than substituting self-review or inventing a waiver. Only an explicit current repository policy may define an exception.

### 4. Bind review to the exact head

Record the reviewed commit SHA from review metadata or from an unambiguous reviewer response. The relied-upon completed review must apply to the current exact head.

If the PR head changes after review, classify prior review evidence as stale and return `BLOCKED_REVIEW_STALE` until a new review completes for the new head. Do not infer that a small or non-overlapping follow-up commit preserves review validity unless current repository policy explicitly permits that exception.

### 5. Clear findings and threads

Read submitted reviews, reviewer responses, and inline review threads. Address each material finding with code, documentation, evidence, or an explicit justified disposition. After any code/documentation repair changes the head, return to the beginning of the gate and reacquire exact-head CI and review.

Do not merge with an unresolved material review thread.

### 6. Evaluate base drift

Immediately before final acceptance, fetch the current target-branch head. If it differs from the evaluated PR base/current target snapshot, inspect the intervening change and determine whether the PR must be rebuilt, rebased, or otherwise synchronized. Conflict-free mergeability alone does not establish semantic freshness.

If synchronization creates a new PR head, all previous final-head CI and review evidence becomes stale.

### 7. Final live-state refresh

Immediately before merge, fetch live state again and verify all of the following at once:

- current PR head equals the exact accepted head;
- current target-branch head/base drift is evaluated;
- effective diff still matches intended scope;
- all required checks for that exact head are successful or explicitly non-applicable under current policy;
- completed independent review evidence count is at least one;
- the relied-upon review applies to the exact current head;
- no material review finding or unresolved thread remains;
- PR is currently mergeable;
- PR body does not claim stale SHAs, run IDs, review state, or validation state.

If any condition changed, leave `MERGE_ALLOWED` and report the corresponding blocked state.

### 8. Merge with an immutable head guard

Only after the final live-state refresh reaches `MERGE_ALLOWED`, invoke the repository merge operation with `expected_head_sha` set to the exact accepted PR head SHA. In this repository's GitHub connector, use the merge operation's `expected_head_sha` argument; the corresponding GitHub REST merge field is `sha`. Never omit `expected_head_sha` for an agent-performed merge.

If the merge API rejects the operation because the head or repository state moved, do not retry blindly. Refresh live state and run the gate again.

### 9. Verify after merge

Confirm the PR is actually merged, record the merge commit SHA, and confirm the target branch points to the expected merged result or a later intentional commit. For release/publication work, perform any required post-merge verification separately; merge success is not release success.

## Review evidence rules

Keep these distinctions explicit:

- `review requested` != `review completed`;
- `reviews = 0` != `review findings = 0`;
- `review findings = 0` is meaningful only after completed review exists;
- review of SHA A != review of changed SHA B;
- self-review != independent review;
- reviewer unavailable != review waived.

## Stop conditions

Do not declare merge readiness and do not call the merge operation if any of the following is true:

- completed independent review evidence count is zero;
- only a review request or pending review exists;
- relied-upon review targets a different head;
- a material review finding or thread is unresolved;
- any required exact-head CI is not successful;
- target-branch drift is unknown or unresolved;
- current head differs from the accepted exact head;
- current mergeability is unknown or false;
- the merge call cannot be guarded by `expected_head_sha`.

## Evidence to report

Report at completion:

- PR number and title;
- target branch and current target head;
- exact accepted PR head;
- effective scope/changed files;
- exact-head CI summary;
- completed independent review evidence and reviewed SHA;
- unresolved thread/finding status;
- base-drift decision;
- final live-state decision (`MERGE_ALLOWED` or specific `BLOCKED_*` state);
- `expected_head_sha` used for merge;
- merge result and merge commit SHA;
- any separate post-merge release/publication status.
