# Repository-change orchestration

This document explains the rationale for the generated `orchestrate-repository-change` Skill and the provider-neutral merge-gate procedures. It is non-authoritative guidance about execution efficiency. Repository policy, task requirements, schemas, validators, tests, workflows, release rules, and other acceptance authorities continue to decide whether a change is correct and complete.

## Problem model

Repository-maintenance agents can spend substantial wall-clock time on work that adds little acceptance evidence. Common amplification mechanisms include:

- repeated live-state reads after the relevant binding facts have not changed;
- one-finding-at-a-time commits that repeatedly invalidate revision-bound CI and review;
- requesting another review while known material findings from the previous review remain unresolved;
- serial execution of independent reads or validation jobs;
- treating an asynchronous wait as idle time even though bounded read-only work is available;
- rerunning broad validation after changes that invalidate only a narrow evidence subset;
- rewriting lower stacked members and forcing descendants to restack even though their semantic state did not change;
- materializing immutable downstream identity or provenance before a known upstream repair has stabilized;
- adding defensive acceptance gates that are not required by repository authority; and
- over-splitting tightly coupled changes into multiple pull requests whose CI/review/restack fixed costs exceed the benefit of independent merge units.

The objective is not to minimize operations mechanically. The objective is **preserved correctness with less avoidable round-trip, mutation, coordination, and evidence churn**.

## Core diagnostic concepts

### Candidate churn

Candidate churn is avoidable creation of replacement heads after a candidate has started to acquire revision-bound evidence. A justified semantic repair may require a new head; the diagnostic concern is intermediate, cosmetic, or one-finding-at-a-time mutation that repeatedly invalidates the same evidence.

### Review amplification

Review amplification is repeated review acquisition beyond what current authority and actual revision invalidation require. The most costly pattern is review -> fix one finding -> request review -> discover another already-actionable finding -> repeat. The review reacquisition gate interrupts that loop by requiring the complete known material backlog to receive a current-head validated repair or evidence-backed no-change disposition and recorded closure evidence before intentionally starting a new merge-acceptance review cycle.

The same canonical gate applies to explicitly authorized final whole-stack audits under orchestration procedures. Head stabilization and green CI are necessary but not sufficient: before reviewer invocation, the complete known-finding ledger must also show current-head validated disposition and required closure evidence for every known material actionable finding.

### Finding backlog

The finding backlog is the logical set of known material actionable review findings that have not yet reached validated semantic closure. It is independent of provider thread count. A body-only finding can remain in the backlog even when the provider exposes no resolvable thread; a resolved thread can still be semantically incomplete if its repair or no-change disposition was never validated or the required closure evidence was not recorded.

### Coherent mutation batch

A coherent mutation batch groups currently known, verified, compatible repairs that share a compatible authority/scope/validation boundary. It does not mean waiting for hypothetical findings, forcing unrelated work into one commit, or delaying urgent repair. The goal is to avoid knowingly reacquiring expensive exact-head evidence between repairs that are already known and can safely be applied together.

### Stability frontier

The stability frontier is the highest part of a stack whose member heads have no currently planned mutation absent a new material defect, authority decision, scope correction, conflict, or other justified change. It is a planning model, not a merge/review/approval state and not permanent immutability.

Review latency does not by itself block dependency-safe construction beyond the frontier. A known upstream semantic repair may, however, justify deferring downstream **final immutable materialization** when that downstream identity/provenance/generated artifact would necessarily become stale. Downstream logic and tests may still proceed when they do not embed the defective assumption.

### Selective evidence invalidation

Acceptance evidence should be treated as a set of bindings rather than one indivisible snapshot. Any proposed-head change necessarily makes exact-head CI and review evidence for the former commit stale because those artifacts are bound to the exact revision. Other evidence whose bindings genuinely did not change, such as unrelated target-state or environment facts, may remain reusable after applicability is re-established. Target-branch movement can require semantic impact analysis without automatically making every unrelated evidence item stale. Unknown applicability fails closed; known unchanged non-exact-head bindings are reused.

### State-read amplification

A state read is useful when it resolves decision-relevant uncertainty. State-read amplification occurs when materially unchanged live state is reacquired without a changed binding, concrete invalidation signal, or new decision need. Evidence-bound reads should therefore be refreshed according to what can actually have changed rather than through unconditional full snapshots.

### Stacked descendant propagation cost

Changing a lower member can force descendant branch updates, generated/provenance rematerialization, exact-head requalification, and review scope changes. That propagation cost should influence both stability planning and pull-request boundaries. It does not justify preserving a defective lower member; it does justify avoiding unnecessary lower-head churn and deferring downstream revision-bound materialization that is already known to become stale.

### Completion boundary

Implementation completion, validation completion, review completion, merge authorization, merge completion, release/publication completion, and human handoff are different states. A completion mode determines where autonomous work stops; it does not implicitly waive evidence that would be required by a later completion mode. In particular, HANDOFF_READY is not MERGE_READY.

## Critical-path model

A useful conceptual model is:

`inspect -> mutate -> validate -> asynchronous evidence -> remediate -> accept`

The critical path becomes longer when a mutation occurs after revision-bound evidence begins, because the mutation can invalidate that evidence and restart part of the path. Stable candidates and coherent repair batches therefore matter most around expensive asynchronous boundaries such as CI, independent review, release qualification, publication, and deployment.

This does not justify delaying a known urgent repair. Safety, data integrity, publication correctness, and other concrete operational risks take priority over reducing evidence churn.

## Read amplification

Independent reads should be batched or parallelized when supported. Reads that establish inputs for later reads remain dependency ordered. Reuse valid exact-head or live-state evidence while its binding facts remain unchanged; refresh only the evidence affected by a concrete invalidation signal or unresolved uncertainty.

No fixed tool-call quota should be used. Quotas encourage agents to substitute assumptions for necessary evidence. The question is whether a read can change the next decision, not whether the number of reads is below a target.

## Mutation amplification

A semantic mutation unit should normally align with one authority boundary, one coherent purpose, one understandable rollback unit, and one validation boundary. When several verified findings satisfy those conditions, applying them together before restarting revision-bound evidence can reduce head churn. Conversely, unrelated changes remain separate even when combining them would reduce CI or review count.

No fixed batch size applies. The known compatible repair set may contain one item or many. A batch is ready when the currently known compatible actions are understood and can be validated coherently; it is not delayed to wait for speculative future findings.

## Review reacquisition

A completed review produces hypotheses, not commands. Before intentionally starting another merge-acceptance review cycle, account for every material actionable finding already known from submitted review evidence. Each must have either a current-head validated repair or an evidence-backed current-head no-change disposition, and the required finding-level closure evidence must be recorded before reacquisition.

This requirement applies equally to inline threads and top-level/body-only findings. Provider thread resolution is bookkeeping evidence; semantic closure depends on the validated outcome. Closure evidence records that validated disposition on an auditable surface so the finding can be distinguished from unresolved or deferred material findings. Falsified reviewer claims should receive concise no-change evidence rather than appeasement edits, and unrelated suggestions should not be forced into current scope.

Naturally triggered provider behavior is not prohibited, and urgent operational/security/data-integrity repair is not delayed for batching. An explicitly authorized final human-handoff whole-stack audit can occur only after known findings are dispositioned, validated for the current head, and given the required closure evidence; it remains diagnostic rather than merge-acceptance evidence.

## Pull-request boundary selection

A pull-request boundary is useful when the split benefit exceeds the restack, evidence invalidation, and coordination cost. Evaluate:

- authority boundary;
- semantic purpose;
- independent merge value;
- rollback unit;
- validation boundary;
- review comprehensibility;
- expected head stability;
- cross-member coupling;
- descendant propagation cost; and
- evidence invalidation cost.

This is a heuristic, not a mandatory gate or numeric score. Do not optimize for a fixed PR count. Do not over-split tightly coupled work that will churn together, and do not combine unrelated authority decisions merely to reduce fixed review/CI cost.

## Validation ordering

Focused validation has high value when it can falsify a candidate cheaply. Broader required validation still follows before acceptance. Independent checks may run concurrently when doing so reduces wall-clock time without obscuring failure attribution.

The focused-to-broad ordering is a practical sequencing heuristic rather than a replacement for repository-required validation. For a final revision-bound whole-stack review, freeze intended heads and require applicable required CI on those exact heads to succeed before intentionally requesting the review.

## Work while evidence is in flight

Asynchronous wait time can be used for bounded read-only work and dependency-safe later implementation that does not knowingly propagate a material defect. Examples include self-audit, reproductions, regression-test design, authority checks, and implementation above a stable prerequisite.

The work must remain bounded by a concrete scope or trigger. An agent should not turn every wait into an open-ended search for hypothetical defects. Review latency alone is not a reason to mutate stable lower members or stop constructing safe later members.

## Guarded mutations

Provider write preconditions such as compare-and-swap revisions, expected heads, ETags, versions, or generations can close races at the mutation boundary. This can remove an additional race-detection read only when repository authority does not separately require that read or an equivalent commit-boundary live-state revalidation.

Guarded writes do not replace semantic checks or required commit-boundary revalidation. A rejected precondition is an invalidation signal that requires targeted state refresh rather than a blind retry.

## Diagnostic metrics

The following quantities can help identify inefficient execution. They are **diagnostic metrics only**: they are not merge gates, review qualification thresholds, mandatory KPIs, acceptance requirements, or fixed optimization targets. They remain diagnostic observations rather than merge gates.

- `candidate_head_count`: distinct candidate heads created for the same intended semantic acceptance cycle;
- `post_review_head_churn`: head changes after revision-bound review begins;
- `review_amplification`: review cycles beyond those justified by actual invalidation or explicit authority;
- `unresolved_finding_backlog`: known material findings still lacking a current-head validated repair, evidence-backed no-change disposition, or required closure evidence;
- `state_read_amplification`: repeated reads of materially unchanged decision state;
- `evidence_reuse_ratio`: still-valid evidence reused versus unnecessarily reacquired; and
- `stack_descendant_rewrite_count`: descendant head rewrites caused by lower-member changes.

`ci_amplification` may also be useful when diagnosing avoidable intermediate candidate mutations, but CI performance optimization is a separate concern from this workflow model.

A high or low value is not inherently correct. Interpretation depends on risk, authority, invalidation signals, dependency topology, and the nature of the change. No candidate-head count, review count, CI count, tool-call count, or PR-count threshold is promoted into semantic policy by these diagnostics.

## Integration scenarios

These scenarios illustrate how the concepts compose.

### Review-loop prevention

Review #1 yields A/B/C and only A is repaired. Intentionally requesting merge-acceptance review #2 is premature: B and C remain in the known finding backlog until each receives a current-head validated repair or evidence-backed no-change disposition and the required closure evidence is recorded.

### Body-only finding

A material finding appears only in a review summary. It receives a stable finding locator, enters the same ledger and disposition process, and records closure evidence on an available review/PR surface. Absence of a resolvable thread does not imply closure.

### Reviewer misunderstanding

A finding is falsified against the current exact head and applicable authority. Keep it in the unresolved finding backlog until the decisive evidence, evidence-backed no-change disposition, current-head validation, and closure evidence are recorded. Do not create a cosmetic/appeasement mutation merely to make the reviewer comment disappear.

### Coherent repair batch

Several currently known verified findings require compatible head mutations. Apply the coherent repair set before intentionally reacquiring expensive exact-head evidence. Keep unrelated or authority-conflicting repairs separate.

### Stack propagation

S1 is not yet stable, S2 can be implemented without embedding the unresolved S1 assumption, and S3 final immutable identity depends on the eventual S1 SHA. S2 may proceed; S3 final identity materialization is deferred; review latency itself does not stop construction.

### Human-handoff final audit

Implementation and required validation are complete, the known finding backlog is empty, final stack heads are stable, and the task explicitly authorizes one final whole-stack diagnostic audit. Recheck the canonical complete-ledger/closure-evidence gate immediately before reviewer invocation, then request that audit once. Unless the explicit task requires the diagnostic audit to complete before handoff, do not wait for the result. Do not retry the audit, do not merge, and stop autonomous work at HANDOFF_READY once the selected completion contract permits handoff.

## Relationship to existing procedures

`audit-frozen-change` remains the bounded read-only audit procedure for a frozen implementation or artifact. `pr-merge-gate` remains the GitHub-facing pull-request acceptance and merge adapter, including the logical finding-ledger and review-disposition procedures. `orchestrate-repository-change` covers the broader implementation lifecycle, stacked construction, completion boundaries, stability frontier, and PR-boundary heuristics. None replaces semantic acceptance authority.

If empirical use shows that a particular efficiency discipline is required for correctness across multiple consumers, that invariant can later be considered for promotion into atomic policy. Procedure guidance should not be promoted merely because it usually saves time.

## Selectable workflow guidance

Progression and completion are separate choices:

| Dimension | Options | Selection authority |
| --- | --- | --- |
| Progression | serial-pr, stacked-pr | explicit task, repository policy, declared default, then permitted agent choice |
| Completion | agent-review-and-merge, human-handoff | explicit task, repository policy, declared default, then permitted agent choice |

Progression determines construction ordering. Completion determines where the agent stops. Serial-pr does not intrinsically mean "review and merge before task completion": with agent-review-and-merge, one validated member proceeds through review, guarded merge, then the next member; with human-handoff, the current validated member stops at HANDOFF_READY without initiating a new merge-acceptance review request or merge by default.

Stacked progression likewise does not prescribe cumulative review. Under agent-review-and-merge, each stacked member may use its own completed independent exact-head review, or multiple members may be covered by one explicit cumulative review when the canonical coverage bindings are satisfied. A tip-only approval is not lower-member cumulative coverage. Under human-handoff, the validated whole stack remains open and unmerged without initiating a new merge-acceptance review request by default.

An explicit task may authorize one final diagnostic whole-stack architecture/dependency/completeness audit after the complete stack is stable and the task's required exact-head validation has succeeded. That audit request is additionally gated by the canonical complete known-finding disposition and closure-evidence prerequisite immediately before reviewer invocation. The audit does not authorize merge, does not replace later exact-head acceptance review, and must not create a review-retry loop.

Serial pull requests are often easier when each member should be merged before later implementation starts. Stacked pull requests are often useful when a coherent multi-part change can be constructed without review latency blocking later members. Neither strategy is universally preferable; scope, dependency topology, review contract, CI behavior, expected head stability, propagation cost, and human operating preference determine the choice.

A human handoff can be selected with either progression strategy. It means that implementation and authorized validation work are complete while merge authorization is not established. When no applicable pre-existing review evidence establishes another state, independent review is NOT_REQUESTED or OUTSTANDING. When applicable pre-existing review evidence already establishes completed review, preserve REVIEW_COMPLETE; HANDOFF_READY can coexist with that review state. Human handoff does not waive later review requirements, create approval, or imply merge readiness.

The dispatcher applies explicit task instruction before repository-local policy, repository-declared defaults, and any agent choice that is explicitly permitted. A profile remains a shared normative rule-selection bundle; it does not encode serial or stacked progression, completion mode, agent provider, or Skill selection.


## Resumable Work ledger

The Work ledger procedure at `skills/orchestrate-repository-change/references/work-ledger.md` ties the existing workflow state together as a provider-side operational projection. Use a discoverable stack-tip/standalone PR comment or tracking issue for durable checkpoints and execution-local state for frequent updates. Record material transitions, not every tool call. A progress-only repository commit would move the head and stale exact-head evidence; ordinary progress therefore remains outside the tracked source tree.

Resume by discovering or reconstructing the checkpoint, refreshing affected live bindings, choosing the next safe action, performing useful work, and checkpointing material changes. Preserve semantic progress separately from final qualification. Link the existing review-finding ledger instead of duplicating finding dispositions or closure evidence. Provider facts and existing acceptance procedures retain authority.

This procedure source can be developed independently of the repository's pinned self-host toolchain. Source changes do not silently promote the runtime or regenerate a consumer from an unreviewed candidate. Adoption remains a separate release/self-host boundary.
