# Repository-change orchestration

This document explains the rationale for the generated `orchestrate-repository-change` Skill. It is non-authoritative guidance about execution efficiency. Repository policy, task requirements, schemas, validators, tests, workflows, release rules, and other acceptance authorities continue to decide whether a change is correct and complete.

## Problem model

Repository-maintenance agents can spend substantial wall-clock time on work that adds little acceptance evidence. Common amplification mechanisms include:

- repeated live-state reads after the relevant binding facts have not changed;
- one-finding-at-a-time commits that repeatedly invalidate revision-bound CI and review;
- serial execution of independent reads or validation jobs;
- treating an asynchronous wait as idle time even though bounded read-only work is available;
- rerunning broad validation after changes that invalidate only a narrow evidence subset;
- adding defensive acceptance gates that are not required by repository authority;
- over-splitting tightly coupled changes into multiple pull requests whose CI/review fixed costs exceed the benefit of independent merge units.

The objective is not to minimize operations mechanically. The objective is to preserve semantic correctness and evidence quality while reducing avoidable round trips, candidate churn, and evidence reacquisition.

## Critical-path model

A useful conceptual model is:

`inspect -> mutate -> validate -> asynchronous evidence -> remediate -> accept`

The critical path becomes longer when a mutation occurs after revision-bound evidence begins, because the mutation can invalidate that evidence and restart part of the path. Stable candidates and coherent repair batches therefore matter most around expensive asynchronous boundaries such as CI, independent review, release qualification, publication, and deployment.

This does not justify delaying a known urgent repair. Safety, data integrity, publication correctness, and other concrete operational risks take priority over reducing evidence churn.

## Read amplification

A state read is useful when it resolves a decision-relevant uncertainty. It is redundant when the evidence binding is already known to remain valid and the read is performed only for reassurance.

Independent reads should be batched or parallelized when supported. Reads that establish inputs for later reads must remain dependency ordered. No fixed tool-call quota should be used: quotas encourage agents to substitute assumptions for necessary evidence.

## Mutation amplification

A semantic mutation unit should normally align with:

- one authority boundary;
- one coherent purpose;
- one understandable rollback unit;
- one validation boundary.

When several verified findings satisfy those conditions, applying them together before restarting revision-bound evidence can reduce head churn. Conversely, unrelated changes should remain separate even when combining them would reduce CI or review count.

## Validation ordering

Focused validation has high value when it can falsify a candidate cheaply. Broader required validation still follows before acceptance. Independent checks may run concurrently when doing so reduces wall-clock time without obscuring failure attribution.

The focused-to-broad ordering is therefore a heuristic rather than a new mandatory gate sequence.

## Work while evidence is in flight

Asynchronous wait time can be used for bounded read-only work that does not change the candidate under evaluation. Examples include self-audit, reproductions, regression-test design, authority checks, and preparation of the next independent task.

The work must remain bounded by a concrete scope or trigger. An agent should not turn every wait into an open-ended search for hypothetical defects.

## Selective invalidation

Acceptance evidence should be treated as a set of bindings rather than one indivisible snapshot. A revision change can invalidate exact-revision CI and review while leaving unrelated target-state or environment facts intact. A target-branch change can require semantic impact analysis without automatically making every exact-head result stale.

Selective invalidation is valid only when the unchanged bindings are actually known. Unknown applicability fails closed.

## Guarded mutations

Provider write preconditions such as compare-and-swap revisions, expected heads, ETags, versions, or generations can close races at the mutation boundary. This can remove an additional race-detection read only when repository authority does not separately require that read or an equivalent commit-boundary live-state revalidation.

Guarded writes do not replace semantic checks or required commit-boundary revalidation. A rejected precondition is an invalidation signal that requires targeted state refresh rather than a blind retry.

## Diagnostic metrics

The following quantities can help identify inefficient execution, but they are diagnostic observations rather than merge gates or reviewer-qualification thresholds:

- `state_read_amplification`: repeated reads of materially unchanged decision state;
- `review_amplification`: independent review cycles beyond those required by revision changes or authority;
- `ci_amplification`: CI cycles caused by avoidable intermediate candidate mutations;
- `post_review_head_churn`: head changes after a revision-bound review begins;
- `evidence_reuse_ratio`: valid evidence reused versus unnecessarily reacquired.

A high or low value is not inherently correct. Interpretation depends on risk, authority, invalidation signals, and the nature of the change.

## Relationship to existing procedures

`audit-frozen-change` remains the bounded read-only audit procedure for a frozen implementation or artifact. `pr-merge-gate` remains the GitHub-facing pull-request acceptance and merge adapter. `orchestrate-repository-change` covers the broader implementation lifecycle around those specialized procedures and does not replace their acceptance semantics.

If empirical use shows that a particular efficiency discipline is required for correctness across multiple consumers, that invariant can later be considered for promotion into atomic policy. Procedure guidance should not be promoted merely because it usually saves time.

## Selectable workflow guidance

The following is guidance for choosing an execution strategy; it is not a new acceptance gate or an operating-mode profile.

Progression and completion are separate choices:

| Dimension | Options | Selection authority |
| --- | --- | --- |
| Progression | serial-pr, stacked-pr | explicit task, repository policy, declared default, then permitted agent choice |
| Completion | agent-review-and-merge, human-handoff | explicit task, repository policy, declared default, then permitted agent choice |

Progression determines construction ordering. Completion determines where the agent stops. Therefore serial-pr does not intrinsically mean "review and merge before task completion": with agent-review-and-merge, one validated member proceeds through review, guarded merge, then the next member; with human-handoff, the current validated member stops at HANDOFF_READY without initiating a new review request or merge.

Stacked progression likewise does not prescribe cumulative review. Under agent-review-and-merge, each stacked member may use its own completed independent exact-head review, or multiple members may be covered by one explicit cumulative review when the canonical coverage bindings are satisfied. A tip-only approval is not lower-member cumulative coverage. Under human-handoff, the validated whole stack remains open and unmerged without initiating a new review request.

Serial pull requests are often easier when each member should be merged before later implementation starts. Stacked pull requests are often useful when a coherent multi-part change can be constructed without review latency blocking later members. Neither strategy is universally preferable; scope, dependency topology, review contract, CI behavior, and human operating preference determine the choice.

A human handoff can be selected with either progression strategy. It means that implementation and the authorized validation work are complete while merge authorization is not established. When no applicable pre-existing review evidence establishes another state, independent review is NOT_REQUESTED or OUTSTANDING. When applicable pre-existing review evidence already establishes completed review, preserve REVIEW_COMPLETE; HANDOFF_READY can coexist with that review state. Human handoff does not waive later review requirements, create approval, or imply merge readiness. Existing review evidence may be observed and reported, but the handoff path itself does not initiate review acquisition.

The dispatcher applies explicit task instruction before repository-local policy, repository-declared defaults, and any agent choice that is explicitly permitted. A profile remains a shared normative rule-selection bundle; it does not encode serial or stacked progression, completion mode, agent provider, or Skill selection.
