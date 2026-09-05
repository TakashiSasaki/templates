# Stable candidate-head mutation batching

This reference is provider-neutral procedure support for `pr-merge-gate`. It does not create a new acceptance gate, freshness interval, waiting period, or semantic pull-request rule. It controls when already-justified head-changing repairs are applied so exact-head evidence is not repeatedly invalidated by avoidable mutation churn.

## Stabilize before intentionally acquiring expensive acceptance evidence

Before intentionally requesting independent review or starting another expensive revision-bound acceptance evaluation, establish as far as reasonably possible that the authorized implementation is complete, known self-audit findings are dispositioned, the logical finding backlog in `review-finding-ledger.md` has no known material actionable item awaiting a validated repair or evidence-backed no-change disposition, focused validation is complete, required generated projections are internally coherent, known compatible head-changing repairs are batched, no known material defect remains unresolved, and no known downstream immutable-identity materialization is waiting on an upstream semantic repair.

This is a candidate-stabilization discipline, not a new acceptance gate. It has no fixed duration, does not require perfection, does not prevent PR creation, and does not require waiting for earlier CI or review before dependency-safe implementation continues. Naturally triggered CI may run before stabilization. Do not deliberately request independent review for a candidate already known to be intermediate or for a downstream identity that is already known to become stale after an unresolved upstream semantic repair.

For a final whole-stack review, treat required CI and review as ordered revision-bound evidence rather than parallel latency-hiding work. Freeze the intended final heads first, then require all applicable required CI on those exact heads to have completed successfully before requesting the final review. Pending required CI means the review candidate is not yet qualified for that request. Failed or cancelled required CI requires repair or explicit disposition and requalification. If a head changes, reacquire the required CI for the affected exact head before requesting a replacement review. This ordering does not block construction of later stack members and is not a time-based waiting gate.

## Distinguish diagnostic validation from qualification evidence

Use focused diagnostic validation during implementation to falsify the current change quickly. Diagnostic checks may be repeated as the implementation changes and may intentionally cover only the changed invariant or suspected failure mode. Their purpose is feedback, not a claim that the candidate has completed every required acceptance gate.

Use qualification validation when the current candidate is intended to support revision-bound acceptance, final review, release, publication, or another authority-defined completion boundary. Qualification must include every check required by the applicable repository authority and must bind those results to the exact candidate revision or artifact.

Do not deliberately spend an expensive full qualification cycle on a candidate already known to be intermediate when focused diagnostics can complete the known repair first. Conversely, never substitute a diagnostic pass for required qualification merely because the focused check is faster. Naturally triggered repository CI remains valid observable evidence when applicable; this distinction does not authorize disabling required automatic checks.

## Preserve a stable candidate while evidence is in flight

Once a candidate head has entered CI or independent review, treat that SHA as stable unless a justified repair, scope correction, conflict resolution, or other necessary head-changing action is ready to apply.

Continue read-only investigation, self-audit, review-thread analysis, and preparation work while CI or review is in flight. Do not create no-op commits, cosmetic churn, speculative edits, or one-finding-at-a-time commits merely to show progress or refresh evidence.

A newly discovered material defect immediately blocks merge readiness even if the current head is left unchanged temporarily for investigation. Keeping the SHA stable for batching never makes a known-defective head acceptable.

## Accumulate only known, justified mutations

When multiple findings or self-audit defects are being resolved in the same candidate cycle:

1. enumerate the currently known backlog before mutating when the provider state makes that practical;
2. verify or falsify each candidate issue with read-only evidence when possible;
3. record which verified items actually require a head-changing repair;
4. group only compatible repairs whose authority decision, scope, and validation boundary can be reasoned about coherently;
5. apply one coherent mutation batch when that currently known actionable group is ready; and
6. invalidate and reacquire only the exact-head evidence whose actual binding changed.

Batch only work that is already known and justified. Do not wait an arbitrary amount of time for hypothetical future findings, broaden scope to make a batch look worthwhile, or postpone a ready material repair solely to save CI/review cost. Do not manufacture a no-op or cosmetic commit to retrigger CI/review or create a fresh-looking head.

If two repairs conflict, require different authority decisions, belong to materially unrelated work, or would make one combined change harder to reason about or validate, keep them separate. Coherence is more important than minimizing commit count.

Do not intentionally reacquire merge-acceptance review between compatible repairs that are already known and verified when that would create avoidable one-finding-at-a-time review/head churn. Once the coherent replacement candidate is ready, apply the canonical review-reacquisition rule to the complete known backlog rather than the last edited thread alone.

## Immediate-mutation exceptions

Apply a head-changing repair immediately rather than batching when delay would create a concrete operational or safety risk, allow a known harmful external action to continue, invalidate an active release/publication decision, or otherwise make continued use of the current candidate itself materially unsafe.

An ordinary desire for faster feedback, a pending check, or a preference to have visible activity is not such an exception.

## Evidence invalidation

A mutation batch creates one new candidate head. Mark evidence stale according to its actual bindings:

- exact-head CI, exact-head review, and head-bound scope evidence for the former SHA are stale;
- target-branch evidence is affected only when its own binding changed;
- finding identity, source review, and other semantic ledger state survive a head change unless the change invalidates their applicability;
- evidence independent of the changed head remains reusable when current policy establishes continued validity.

Request or collect new exact-head CI/review evidence only after the coherent replacement candidate is ready. Do not deliberately produce a sequence of partial candidate SHAs that each trigger the same expensive evidence cycle when the remaining known repairs could have been applied together.

## Relationship to review feedback disposition and the ledger

`review-feedback-disposition.md` decides what a verified review item means and what remediation it requires. `review-finding-ledger.md` keeps the entire known backlog and its closure state recoverable across provider surfaces and head changes. This reference decides when compatible, already-justified head-changing remediations should be applied.

None of these procedures changes finding severity or merge authorization. A verified material defect remains blocking until repaired and revalidated even when its repair is waiting in the current mutation batch.

## Closure

Mutation batching is an efficiency discipline, not acceptance evidence. Candidate stabilization is likewise an efficiency discipline, not acceptance evidence. Reacquire every exact-head gate invalidated by the mutation before reporting the replacement candidate as successful, and require the normal merge-gate workflow to reach its required state.
