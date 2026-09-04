---
name: pr-merge-gate
description: Apply the canonical pull-request Policy profile through fail-closed GitHub exact-head evidence reuse, invalidation-driven live-state refresh, review, and guarded-merge orchestration.
---

# Pull Request Merge Gate

## Purpose

Provide the GitHub-facing orchestration adapter for the canonical `pull-request` Policy profile. This Skill is not a second authority for shared pull-request semantics: the rules under `policy/pull-request/` are canonical, while this adapter defines how to collect and reconcile GitHub live state, preserve valid acceptance evidence, represent transient gate states, request repository review, and execute a head-guarded merge.

Repository code, schemas, contracts, validators, tests, workflows, release rules, and repository-local policy remain authoritative for task-specific semantic acceptance.

## Workflow strategy and completion boundary

This adapter is independent of repository-change progression and review-acquisition method. It evaluates pull-request acceptance evidence without selecting how members were constructed. A completed independent review bound to an exact current member head is valid evidence for that member whether progression is serial-pr or stacked-pr. When one completed review is claimed to cover multiple stacked members, the additional canonical cumulative-coverage bindings must be explicit: ordered stack, integration base, every covered member head, stack tip, reviewed scope, review contract, reviewer independence, completion state, and material limitations.

Review acquisition and completion mode are separate concerns. The agent-review-and-merge path may proceed through the normal evidence and guarded-merge states. The human-handoff path stops at HANDOFF_READY after authorized implementation and validation work; it does not initiate a new review request through reviewer assignment, provider invocation, requested-reviewer state, or any other review-request mechanism, does not close a pull request, and does not authorize or execute a merge or imply REVIEW_COMPLETE, MERGE_READY, or MERGED. Existing reviews may be observed, inspected, and reported. Human handoff is not a waiver of the independent-review or merge requirements that apply to a later continuation. It is not merge-ready.

Do not infer lower-member review coverage from a tip PR review event or approval state. A tip-only review is insufficient to establish lower-member cumulative coverage. Do not make workflow combinations into Policy profiles. Applicability is evaluated from evidence bindings; review-request transport is not itself acceptance evidence.

## Canonical policy rules

Apply every rule selected by `profiles/pull-request.yml`. At the current Policy revision the canonical rule IDs are:

- `pull-request.verify-target-branch-head-freshness` — `policy/pull-request/target-branch-head-freshness.md`
- `pull-request.require-independent-exact-head-review` — `policy/pull-request/independent-exact-head-review.md`
- `pull-request.close-review-threads-before-merge` — `policy/pull-request/review-thread-closure.md`
- `pull-request.require-exact-head-ci-evidence` — `policy/pull-request/exact-head-ci-evidence.md`
- `pull-request.fail-closed-on-unresolved-ci-discovery` — `policy/pull-request/ci-discovery-fail-closed.md`
- `pull-request.reuse-valid-exact-head-evidence` — `policy/pull-request/reuse-valid-evidence.md`
- `pull-request.require-current-mergeability` — `policy/pull-request/current-mergeability.md`
- `pull-request.refresh-live-state-before-merge` — `policy/pull-request/final-live-state-refresh.md`
- `pull-request.guard-merge-against-head-movement` — `policy/pull-request/immutable-head-guard.md`
- `pull-request.verify-merge-result` — `policy/pull-request/post-merge-verification.md`
- `pull-request.require-explicit-stacked-review-coverage` — `policy/pull-request/stacked-review-coverage.md`

If this Skill conflicts with those canonical rules, follow the canonical rules and repair this adapter. If the `pull-request` profile changes, this adapter must be reviewed for corresponding orchestration changes rather than silently retaining an older rule set.

## Adapter-owned mechanics

This Skill owns GitHub-specific execution details, not shared policy meaning. In particular it defines:

- the gate state labels below;
- how a GitHub acceptance snapshot records evidence bindings and invalidation signals;
- how GitHub workflow-run and exact-commit check views are correlated when indexing lags;
- this repository's minimum observation floor before an expected check may be classified as confirmed absent;
- the GitHub connector `expected_head_sha` merge guard;
- the concrete live-state snapshot and evidence report used by repository-maintenance agents.

These mechanics may change without changing the underlying shared Policy rule IDs when the provider or execution surface changes.

## Use when

Use this Skill whenever a repository pull request is about to be declared merge-ready or merged, or when a concrete invalidation signal requires previously accepted evidence to be re-evaluated.

Do not use it to replace task-specific implementation, validation, release, publication, or repository-local acceptance work.

## Inputs

Establish one acceptance snapshot containing:

1. PR number and title;
2. base branch and PR base SHA;
3. observed current target-branch head SHA;
4. exact PR head SHA;
5. intended semantic scope and effective changed-file set;
6. applicable exact-head checks and their accepted evidence;
7. CI discovery conclusion and the live views consulted when discovery was needed;
8. completed independent review evidence, including reviewed SHA;
9. current material review state and unresolved review-thread dispositions;
10. current mergeability;
11. the binding facts for each relied-upon evidence item.

Do not discard the whole snapshot merely because one binding changes. Mark only affected evidence stale and reacquire it. A proposed-head change invalidates exact-head CI, exact-head review, and head-bound scope evidence. Target-branch movement requires impact evaluation and invalidates additional evidence only when that movement changes its applicability or semantic basis.

## Gate state model

The adapter success path is:

`PR_OPEN -> SCOPE_AUDITED -> CI_DISCOVERED -> CI_GREEN -> REVIEW_EVIDENCE_PENDING -> REVIEW_EVIDENCE_ESTABLISHED -> FINDINGS_CLEARED -> FINAL_STATE_REFRESHED -> MERGE_ALLOWED`

`REVIEW_EVIDENCE_PENDING` means that the gate has not yet established valid independent review evidence for the exact merge candidate. `REVIEW_EVIDENCE_ESTABLISHED` means that such evidence has been positively identified and its bindings are valid. Evidence can be an individual completed independent exact-head review for the current member. For multiple stacked members, one completed review may instead establish explicit cumulative coverage when every canonical coverage binding is satisfied. Issuing a review request is not an acceptance state and is not evidence by itself.

Use explicit blocked or transient states rather than collapsing uncertainty into success:

- `CI_DISCOVERY_PENDING`: an expected exact-head check is not yet observable and absence is not established;
- `CI_CONFIRMED_ABSENT`: the confirmed-absence protocol below succeeded; this is not success and must be dispositioned before discovery restarts;
- `BLOCKED_CI`;
- `BLOCKED_REVIEW_MISSING`;
- `BLOCKED_REVIEW_PENDING`;
- `BLOCKED_REVIEW_STALE`;
- `BLOCKED_REVIEW_FINDINGS`;
- `BLOCKED_BASE_DRIFT`;
- `BLOCKED_HEAD_CHANGED`;
- `BLOCKED_MERGEABILITY`.

Never transition directly from a missing review, unresolved CI discovery, stale exact-head evidence, unknown base drift, or unknown mergeability to `MERGE_ALLOWED`.

The state model is an authorization model, not a polling schedule. Do not repeat a successful observation merely for conservatism. Do not add an extra review cycle, waiting period, repeated live-state read, or redundant evidence collection as a new mandatory gate unless current repository authority requires it or a concrete invalidation signal makes existing evidence unusable.

## Candidate-head mutation discipline

Use `references/head-mutation-batching.md` when CI or independent review is in flight and new findings or self-audit results may require head-changing repairs. Keep the current candidate SHA stable while read-only investigation determines the currently known actionable set, then apply compatible justified repairs as one coherent mutation batch rather than repeatedly invalidating exact-head evidence with avoidable one-finding-at-a-time churn.

A known material defect blocks merge immediately even while its repair is being prepared; stable-head batching never makes a defective candidate acceptable. Do not wait an arbitrary interval for hypothetical future findings, broaden scope to fill a batch, or delay a ready repair when delay creates a concrete operational or safety risk. Coherence and timely remediation take priority over minimizing commit count.

After a mutation batch creates a new candidate head, invalidate and reacquire only the evidence actually bound to the former SHA. Do not request new exact-head CI or review for intentionally partial intermediate heads when the remaining known compatible repairs can be completed before presenting the next candidate.

## Stacked merge semantics

For an ordered stack such as A -> B -> C, each member may carry its own completed independent exact-head review. Alternatively, one completed review may cover multiple members only when cumulative review evidence remains bound to the exact integration base, ordered membership, each covered member exact head, stack tip, cumulative scope, review contract, independent reviewer, review completion state, and limitations. Stacked progression does not require cumulative review.

When A is merged and B is retargeted or its base moves, evaluate the changed bindings and remaining applicability. Do not mechanically mark every unaffected item stale, and do not reuse evidence when applicability is unknown. Merge each member only after the applicable evidence and guarded merge conditions for that member are re-established.

See references/stacked-review-coverage.md for the provider-neutral cumulative evidence-binding procedure. That reference does not replace canonical Policy semantics.

## Workflow

### 1. Audit the effective scope

Compare the PR against its base and confirm that the changed-file set and PR description match the intended change. Treat historical PR prose as evidence only; current repository sources and current diff determine acceptance scope.

Record the accepted head, target-head context, and effective scope so unchanged scope evidence can be reused. Recompute the effective diff only when a proposed-head or target-branch change, or another concrete scope signal, can alter that result.

### 2. Establish exact-head CI

Apply `pull-request.require-exact-head-ci-evidence` and `pull-request.fail-closed-on-unresolved-ci-discovery`.

Discover applicable checks from current workflow definitions and changed scope. Bind every relied-upon result to the exact current PR head and the applicability conditions used to select it.

GitHub ref visibility and Actions/check indexing are not atomic. If an expected run is not visible, enter `CI_DISCOVERY_PENDING` and use read-only discovery:

1. re-fetch the PR and confirm the head SHA is unchanged;
2. re-read the current workflow definition and confirm the run is expected for the event, filters, and changed scope;
3. refresh the most specific workflow-run view available for the workflow/event/branch/head;
4. refresh an exact-commit check-run or check-suite view for the same head when available;
5. reconcile discovered runs/checks to the exact head and expected workflow, preferring the newest applicable exact-head evidence over stale or superseded results.

The repository adapter safety floor for absence classification is:

`CI_DISCOVERY_MIN_OBSERVATION_MINUTES = 10`

The floor is a guard, not evidence and not a reason to sleep. Continue useful read-only audit while waiting for positive evidence.

Classify `CI_CONFIRMED_ABSENT` only when all of the following are true:

- the PR head remained unchanged throughout observation;
- the current workflow definition still says the check should exist;
- at least the observation floor elapsed since the later of the triggering PR action and the exact head becoming current;
- repeated read-only refreshes in at least two independently indexed GitHub views still show no applicable exact-head evidence when those views are available;
- no contradictory queued, pending, in-progress, or newly indexed exact-head evidence exists;
- the concrete observations supporting the absence decision are recorded.

A single zero-result view, repeated polling of only one index, or elapsed time alone is insufficient. While `CI_DISCOVERY_PENDING`, do not close/reopen the PR, create a no-op commit, or otherwise mutate state solely to retrigger CI. Only after a positively supported `CI_CONFIRMED_ABSENT` decision may a recovery action be considered, after which discovery starts again for the resulting state.

Enter `CI_DISCOVERED` only when applicable exact-head checks are positively identified or current policy establishes non-applicability. Enter `CI_GREEN` only when every applicable discovered exact-head check has an acceptable result.

Once exact-head CI evidence is accepted, reuse it while the exact head and the conditions that determine check applicability remain unchanged. Do not rerun CI discovery or re-fetch workflow definitions solely to make an already valid result feel newer.

### 3. Establish independent review evidence

Apply `pull-request.require-independent-exact-head-review`. Apply `pull-request.require-explicit-stacked-review-coverage` additionally only when one completed review is claimed to cover multiple stacked members.

Ask the evidence question: **Is there valid independent review evidence covering this exact merge candidate?** The gate evaluates evidence, not the transport by which review was acquired.

For any current member, including a member constructed under stacked-pr progression, valid evidence may be a completed independent review bound to that member's exact current head and applicable review contract. When one completed review is claimed to cover multiple stacked members, valid cumulative evidence must additionally bind to the ordered stack, integration base, every covered member exact head, stack tip, cumulative reviewed scope, review contract, reviewer independence, completion state, and material limitations. A tip-only review or approval event does not establish lower-member cumulative coverage.

If valid evidence is absent, enter `REVIEW_EVIDENCE_PENDING` or `BLOCKED_REVIEW_MISSING`; do not transition to `REVIEW_EVIDENCE_ESTABLISHED` or `MERGE_ALLOWED`. A request, pending review, empty review list, or absence of findings is not completed review evidence. Human handoff does not establish review evidence.

Review acquisition belongs to the selected completion procedure, not to serial or stacked progression. Under agent-review-and-merge, when no completed independent exact-head review exists for a member and no applicable cumulative evidence covers it, the procedure may initiate review for the exact current head and must name the exact SHA. If the head changes after review, the prior review is stale and acquisition must address the new exact head. Reviewer selection and reviewer-specific invocation syntax are repository- or execution-environment concerns and are not defined by this shared adapter.

Under human-handoff, do not initiate a new review request. Existing reviews may be inspected or reported, but the handoff path itself does not acquire review. Human handoff remains a completion boundary and does not turn missing review evidence into acceptance evidence.

If the exact head remains unchanged and the relied-upon completed review has not been invalidated by current review state, do not request another independent review merely for conservatism.

### 4. Clear findings and review threads

Apply `pull-request.close-review-threads-before-merge`.

Inspect submitted reviews and inline review threads. Treat each review item as a hypothesis to verify or falsify against the current proposed head; reviewer prose is not authority and is not an instruction to make appeasement edits.

Use `references/review-feedback-disposition.md` to classify and disposition each material review item after evidence is sufficient. The procedure distinguishes `actual-defect`, `invariant-gap`, `regression-test-gap`, `documentation-ambiguity`, `reviewer-misunderstanding`, and `unrelated-suggestion`. Classification explains remediation ownership; it does not override severity, finding validity, exact-head review requirements, or the canonical thread-closure rule.

Keep an item unresolved while its evidence is insufficient. For verified defects or gaps, prefer the smallest generalized repair and appropriate regression evidence rather than only the reported symptom. For a falsified reviewer claim, record the decisive evidence-backed no-change reason instead of changing correct code merely to satisfy the comment. Historical or stale-head comments may be useful diagnostic inputs, but they are not exact-head acceptance evidence and must be re-evaluated against the current head before they justify a repair or no-change disposition.

Resolve a material review thread only after its required action is complete for the current head or an evidence-backed no-change disposition is recorded. If a repair changes the PR head, invalidate the evidence bound to the former head and reacquire the affected exact-head CI, review, and scope evidence. Do not automatically discard evidence that is not affected by the change.

### 5. Evaluate target-branch freshness

Apply `pull-request.verify-target-branch-head-freshness`.

Establish the current target-branch head. If it differs from the accepted target-head snapshot, inspect the intervening change and decide whether synchronization or other re-evaluation is required. Conflict-free mergeability alone is not evidence that target-branch movement is semantically irrelevant.

Do not treat target-branch movement as an automatic instruction to rerun every gate. Record which accepted evidence is actually affected by the intervening change and reacquire only that evidence.

### 6. Refresh invalidating live state

Apply `pull-request.require-current-mergeability`, `pull-request.reuse-valid-exact-head-evidence`, and `pull-request.refresh-live-state-before-merge`.

Immediately before merge, obtain one current live-state snapshot sufficient to verify:

- current PR head equals the exact accepted head;
- current target-branch head is unchanged or its movement has been evaluated;
- current material review state and unresolved review threads do not invalidate the accepted review evidence;
- current mergeability is true;
- the PR body does not materially misstate the accepted head or acceptance state.

Validate the binding facts of previously accepted scope, CI, and completed-review evidence against that snapshot. Do not unconditionally re-fetch exact-head checks, completed reviews, workflow definitions, or the effective diff when their binding facts remain unchanged and current policy establishes continued validity.

If any binding changed or is unknown, leave `MERGE_ALLOWED` and reacquire only the affected evidence. Additional diagnostic reads are permitted when concrete uncertainty exists, but they are diagnostic work rather than new mandatory acceptance requirements.

### 7. Merge with the GitHub immutable-head guard

Apply `pull-request.guard-merge-against-head-movement`.

Only after the final snapshot reaches `MERGE_ALLOWED`, call the GitHub connector merge operation with `expected_head_sha` equal to the exact accepted PR head SHA. The corresponding GitHub REST merge field is `sha`.

Never omit `expected_head_sha` for an agent-performed merge in this repository. Use the immutable-head guard to close the proposed-head race rather than inserting an extra unrequired head poll between the accepted final snapshot and the merge call. If the merge is rejected because the head or repository state moved, do not retry blindly; refresh live state and run the affected gates again.

### 8. Verify after merge

Apply `pull-request.verify-merge-result`.

Confirm the PR is actually merged, record the merge commit SHA, and confirm the target branch contains the intended merged result or a later intentional successor. Treat release, publication, deployment, and other post-merge readiness as separate boundaries.

## Stop conditions

Do not declare merge readiness or invoke merge while any of the following is true:

- CI discovery is unresolved or confirmed absence has not been dispositioned;
- any applicable exact-head CI is not acceptable;
- completed independent exact-head review is missing, pending, stale, or has unresolved material findings;
- a material review thread remains unresolved;
- target-branch movement is unknown or unresolved;
- current head differs from the accepted head;
- current mergeability is unknown or false;
- an acceptance-evidence binding is unknown or invalid and affected evidence has not been reacquired;
- the GitHub merge cannot be guarded with `expected_head_sha`.

Do not create additional stop conditions solely because a stricter local procedure feels safer. New mandatory gates require current repository authority or a concrete unresolved uncertainty already covered by that authority.

## Evidence to report

At completion report:

- PR number/title and target branch;
- current target-branch head and exact accepted PR head;
- effective changed-file scope;
- exact-head CI summary and the binding facts that kept it valid;
- completed independent review evidence and reviewed SHA;
- unresolved thread/finding status;
- target-branch freshness decision;
- any invalidation signals observed and the evidence selectively reacquired;
- final gate state;
- `expected_head_sha` used for merge;
- merge result and merge commit SHA;
- any separate post-merge release/publication state.
