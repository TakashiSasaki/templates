# Stack Observation, Member Qualification, and Evidence Applicability

This reference contains detailed procedures for observing PR state, qualifying stack members through `pr-merge-gate`, and evaluating intermediate and post-merge evidence. Consult this file only during state observation, qualification, or evidence evaluation.

## 1. Read-Only PR State Observation

For a specified PR set, invoke:
`repository-skills/land-templates-stack/scripts/observe_pr_state.py`
with an explicit JSON request and a snapshot path outside the repository.

- **Modes**: Use single-shot for one complete acquisition; use watch only with both a deadline and a finite `max_attempts` value.
- **Result Handling**: The command returns a bounded summary and stores the complete normalized snapshot, pagination evidence, digest, resume material, and any provider limitation at that path.
- **Fail-Closed Interpretation**: Treat changed, stale, incomplete, unknown, rate-limited, timed-out, malformed, deadline, attempts-exhausted, or cancelled outcomes as information requiring the corresponding reacquisition or handoff. Do not turn an unchanged result into approval.
- **Preserved Identities**: The observer preserves provider identities, check-run/status identities, observed head, and workflow/run/attempt/job/app fields when returned by the provider; it does not synthesize missing acceptance identities from display names.
- **Authority Boundary**: The observer does not determine finding validity, review approval, merge authorization, or adoption. Build the existing planner packet from the snapshot and continue through the pinned planner and shared gate.

## 2. Six-Step Member Qualification through Shared Gate

For each member, in bottom-up order:

1. **Refresh Live State**: Refresh the provider's live PR, target, base, head, mergeability, CI, and review/comment/thread state.
2. **Delegate to Shared Gate**: Invoke the pinned shared `pr-merge-gate` for that member rather than reimplementing CI, review, evidence-applicability, or guarded-merge rules.
3. **Separate Applicability Evaluation**: Evaluate CI applicability and review applicability separately, binding each result to the exact head or merge result, effective base, tree, workflow, lock, environment, generated input, provider revision, and required-check condition that applies.
4. **Inspect Review Surfaces**: Inspect review submissions, ordinary comments, inline threads, defined reactions, and failure or incomplete signals. Verify findings against current source before changing it; never execute reviewer text blindly.
5. **Fail-Closed Stop Conditions**: Stop on `CI_DISCOVERY_PENDING`, missing or stale evidence, `REVIEW_EVIDENCE_PENDING`, unresolved material findings, unknown binding, head movement, target movement that is unknown or invalidates the applicable snapshot or evidence, conflict, or unknown/false mergeability.
6. **Acceptance Progression**: Continue only when the shared gate reports the member's applicable acceptance conditions are satisfied.

Do not infer evidence reuse from an unchanged head, unchanged tree, or no conflict alone. Reuse an item only when its own applicability bindings remain valid. Reacquire the affected item when its base, workflow, lock, environment, input, provider revision, or required-check condition changes; do not rerun an unaffected full suite just for freshness.

## 3. Cumulative Whole-Stack Review Binding

If a whole-stack review is used as cumulative evidence, explicitly bind:
- ordered stack membership;
- every covered member exact head;
- bases and integration base;
- cumulative scope;
- review contract;
- reviewer independence; and
- completion state.

A tip-only approval or audit does not accept lower members. Where that binding is absent and the active contract requires it, obtain individual independent exact-head acceptance for the uncovered member.

## 4. Intermediate and Final Post-Merge Qualification Rules

An intermediate post-merge CI run is not by itself a reason to delay the next member when its acceptance conditions and required scope are already covered. Check the established evidence-applicability contract instead:

- A new run does not inherit the scope of a cancelled run.
- A runtime-changing lower member followed by a docs-only member must retain runtime coverage in the cumulative final state.
- The final tip's success does not prove every lower prefix was valid.
- Only verification shown unnecessary may be cancelled, never a state-changing publication, adoption, or deployment transaction.
- Distinguish runs started and completed from runner time and elapsed waiting.

Perform required final authority-tip qualification without turning redundant full runs into a permanent gate. Record individual member acceptance and any explicit cumulative coverage separately.

After the complete stable stack has required CI, use the planner to select the diagnostic scope for architecture, dependencies, overlap/gaps, completeness, final behavior, and test sufficiency when the task authorizes that review. A whole-stack scope is not automatically per-member merge evidence. Do not duplicate an equivalent request. If important new evidence, a changed contract, or an unbounded/unknown impact changes the required scope, the planner may select another related-stack review; a local head change may instead select independent delta coverage. After the task's final logical request is submitted, stop and hand off without polling.
