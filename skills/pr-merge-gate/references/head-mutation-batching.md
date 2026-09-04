# Stable candidate-head mutation batching

This reference is provider-neutral procedure support for `pr-merge-gate`. It does not create a new acceptance gate, freshness interval, waiting period, or semantic pull-request rule. It controls when already-justified head-changing repairs are applied so exact-head evidence is not repeatedly invalidated by avoidable mutation churn.

## Stabilize before intentionally acquiring expensive acceptance evidence

Before intentionally requesting independent review or starting another expensive revision-bound acceptance evaluation, establish as far as reasonably possible that the authorized implementation is complete, known self-audit findings are dispositioned, focused validation is complete, required generated projections are internally coherent, known compatible head-changing repairs are batched, no known material defect remains unresolved, and no known downstream immutable-identity materialization is waiting on an upstream semantic repair.

This is a candidate-stabilization discipline, not a new acceptance gate. It has no fixed duration, does not require perfection, does not prevent PR creation, and does not require waiting for earlier CI or review before dependency-safe implementation continues. Naturally triggered CI may run before stabilization. Do not deliberately request independent review for a candidate already known to be intermediate or for a downstream identity that is already known to become stale after an unresolved upstream semantic repair.

## Preserve a stable candidate while evidence is in flight

Once a candidate head has entered CI or independent review, treat that SHA as stable unless a justified repair, scope correction, conflict resolution, or other necessary head-changing action is ready to apply.

Continue read-only investigation, self-audit, review-thread analysis, and preparation work while CI or review is in flight. Do not create no-op commits, cosmetic churn, speculative edits, or one-finding-at-a-time commits merely to show progress or refresh evidence.

A newly discovered material defect immediately blocks merge readiness even if the current head is left unchanged temporarily for investigation. Keeping the SHA stable for batching never makes a known-defective head acceptable.

## Accumulate only known, justified mutations

When multiple findings or self-audit defects are being resolved in the same candidate cycle:

1. verify or falsify each candidate issue with read-only evidence when possible;
2. record which verified items actually require a head-changing repair;
3. prepare compatible repairs and their regression evidence together;
4. apply one coherent mutation batch when the currently known, actionable set is ready; and
5. then invalidate and reacquire the exact-head evidence affected by the new SHA.

Batch only work that is already known and justified. Do not wait an arbitrary amount of time for hypothetical future findings, broaden scope to make a batch look worthwhile, or postpone a ready material repair solely to save CI/review cost.

If two repairs conflict, require different authority decisions, or would make one combined change harder to reason about or validate, keep them separate. Coherence is more important than minimizing commit count.

## Immediate-mutation exceptions

Apply a head-changing repair immediately rather than batching when delay would create a concrete operational or safety risk, allow a known harmful external action to continue, invalidate an active release/publication decision, or otherwise make continued use of the current candidate itself materially unsafe.

An ordinary desire for faster feedback, a pending check, or a preference to have visible activity is not such an exception.

## Evidence invalidation

A mutation batch creates one new candidate head. Mark evidence stale according to its actual bindings:

- exact-head CI, exact-head review, and head-bound scope evidence for the former SHA are stale;
- target-branch evidence is affected only when its own binding changed;
- evidence independent of the changed head remains reusable when current policy establishes continued validity.

Request or collect new exact-head CI/review evidence only after the coherent replacement candidate is ready. Do not deliberately produce a sequence of partial candidate SHAs that each trigger the same expensive evidence cycle when the remaining known repairs could have been applied together.

## Relationship to review feedback disposition

`review-feedback-disposition.md` decides what a verified review item means and what remediation it requires. This reference decides when compatible, already-justified head-changing remediations should be applied.

Neither procedure changes finding severity or merge authorization. A verified material defect remains blocking until repaired and revalidated even when its repair is waiting in the current mutation batch.

## Closure

Mutation batching is an efficiency discipline, not acceptance evidence. Candidate stabilization is likewise an efficiency discipline, not acceptance evidence. Reacquire every exact-head gate invalidated by the mutation before reporting the replacement candidate as successful, and require the normal merge-gate workflow to reach its required state.
