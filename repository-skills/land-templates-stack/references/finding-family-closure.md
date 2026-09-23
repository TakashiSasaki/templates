# Finding-Family Closure and Review Readiness

This reference contains detailed procedures for auditing review finding families and evaluating structured review readiness. Consult this file only when closing a material review finding family or auditing readiness prior to review acquisition.

## 1. Five-Step Finding-Family Remediation

When a material review finding is accepted as valid, record the compact finding-family reference and closure evidence in the existing Work-ledger `work.closure_audit`. The remediation procedure is bounded and semantic:

1. **Symptom and invariant**: State the reported symptom and the violated invariant.
2. **Safety-critical boundary**: Identify the safety-critical boundary and every canonical entry point that relies on it.
3. **Bounded sibling audit**: Inspect only materially reachable sibling dimensions, including opposite statuses, stale bindings, incomplete retrieval, alternate mutation paths, and ownership/identity variants that share the same root cause.
4. **Regression evidence & gaps**: Record the existing regression evidence, deliberate exclusions, and any remaining material gaps.
5. **Family closure condition**: Mark the family closed only when its bounded sibling audit is complete and the current candidate has evidence for every materially reachable case.

Repairing the exact reviewer example does not itself close the family. Do not create a second finding ledger, transcript, or Work ledger. Keep finding text in the existing review-finding authority and store only references and compact closure evidence in the checkpoint.

## 2. Review Readiness Derivation and Fail-Closed Boundaries

The renderer derives the planner packet's structured `review_readiness` from normalized Work state.

- **Fail-Closed Gate**: Missing/unknown readiness, an open family, an incomplete sibling audit, a material gap, or a known planned candidate mutation prevents a new intentional expensive review request.
- **Allowed Actions During Review-Freeze**: The canonical planner may still reuse an applicable completed result, reconcile an existing or submission-unknown request, acquire missing facts, or hand off. Required automatic CI, focused tests, repair work, and read-only observation continue during this review-freeze state.
- **Exclusion from Applicability Identity**: Readiness is current routing state, not historical request/review applicability identity. It is therefore excluded from the planner request binding, review request marker key, and canonical review-request body.
- **Legacy Records**: Existing records that carry the former readiness field are accepted only after their stored digest is validated and that field is removed for applicability comparison. Legacy closure families without explicit sibling-audit evidence, and planner families without an explicit disposition status, remain unknown/incomplete and cannot authorize a new request.
- **Explicit Exceptions**: An explicit urgent or authority-bound exception may permit new review acquisition only when its reason and authority reference are recorded in the structured readiness input. The exception does not erase the underlying gap.
- **Responsibility Boundary**: The readiness gate is not a finding classifier, acceptance gate, or merge authorization surface; human/model judgment and the existing shared gate keep those responsibilities.
