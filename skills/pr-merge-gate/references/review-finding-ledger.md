# Logical review finding ledger

This reference is provider-neutral procedure support for `pr-merge-gate`. It does not create review semantics, a repository-file storage requirement, or a provider-specific schema. Canonical requirements for review reacquisition and finding closure remain under `policy/pull-request/`.

## Purpose

Maintain one logical record for every known material actionable review finding until its current-head disposition is validated and closure evidence is recorded. The ledger makes the unresolved finding backlog explicit even when findings are split across inline threads, top-level review bodies, summaries, issue comments, or execution-local state.

The ledger is a logical tracking model, not a mandatory JSON/YAML artifact. Store it on the surfaces supported by the current provider and execution environment. Suitable representations include an inline review thread, a reply to a review, a pull-request issue comment, a pull-request body section, or agent execution state. Do not create a repository file solely to satisfy this procedure unless repository authority independently requires one.

## Required logical fields

For each material finding, preserve enough state to recover:

- **stable locator / identity** — a provider locator when available, otherwise a stable finding-level identity such as source-review identity plus a deterministic ordinal or concise unique label;
- **source review** — the review/submission from which the finding became known;
- **reviewed head** — the revision against which the reviewer made the claim;
- **current applicability** — applicable, falsified, superseded, unrelated, or still unknown for the current proposed head;
- **primary disposition** — one category from `review-feedback-disposition.md` once evidence is sufficient;
- **decisive evidence** — the evidence that verifies or falsifies the claim;
- **mutation required?** — whether closure requires a head-changing repair;
- **repair / action** — the generalized repair, regression guard, documentation clarification, no-change explanation, or scope disposition;
- **repair/current head** — the current proposed head on which the disposition is being validated;
- **validation evidence** — focused and/or required qualification evidence that proves the repair or no-change disposition for that head;
- **closure evidence / surface** — thread resolution, review reply, issue comment, PR body entry, or other available audit surface recording semantic closure;
- **final state** — unresolved, repair-ready, validation-pending, semantically-closed, or intentionally out-of-scope/non-blocking as supported by the disposition.

These are logical fields. A provider may combine several fields in one comment or expose additional metadata. Transport representation must not redefine the semantic meaning of a finding or disposition.

## Build the known-finding backlog

After receiving review evidence:

1. enumerate independently actionable findings from every available review surface, including top-level review-body findings that have no resolvable thread;
2. assign or recover a stable locator for each finding;
3. deduplicate only findings that truly describe the same root cause and remediation unit, preserving aliases back to each source occurrence;
4. verify or falsify each hypothesis against the current proposed head and applicable authority;
5. assign the existing primary disposition only when evidence is sufficient;
6. record whether a head mutation is required and, if so, the compatible repair group; and
7. leave the item in the unresolved backlog until the required current-head validation and closure evidence exist.

A provider showing zero unresolved threads does not imply an empty finding backlog. Conversely, an old thread need not remain semantically blocking when current evidence has produced a validated no-change disposition.

## Reacquisition readiness

Before intentionally initiating a new merge-acceptance review acquisition cycle, evaluate the logical ledger under `pull-request.disposition-known-findings-before-review-reacquisition`.

Reacquisition is ready only when every known material actionable finding has reached a current-head validated disposition and the required closure evidence has been recorded. Current applicability is evidence used to choose the disposition; it is not by itself permission to drop a known finding from the precondition.

- An applicable finding may close through a repair validated for the current proposed head with closure evidence recorded, or through an evidence-backed no-change disposition when applicable authority establishes that no mutation is required.
- A finding whose current applicability is `falsified` remains in the unresolved backlog until the falsification is captured as an evidence-backed no-change disposition, validated for the current proposed head, and closure evidence is recorded.
- A finding judged superseded or unrelated may become intentionally out-of-scope/non-blocking only after the evidence-backed disposition and closure evidence required by the applicable procedure have been recorded.

Do not use provider thread state alone as the decision. Do not create an appeasement mutation for a falsified finding. Do not force an unrelated suggestion into scope. An explicitly authorized final human-handoff diagnostic whole-stack audit follows the same known-finding disposition precondition while remaining non-merge evidence.

## Head movement and selective invalidation

When the proposed head changes, re-evaluate ledger fields according to actual binding rather than resetting every item mechanically.

- Exact-head CI or review evidence bound to the former proposed commit becomes stale when the head changes and must be reacquired when that evidence is required for the new exact head.
- A disposition whose decisive evidence is independent of the changed content may remain valid if current applicability is re-established.
- A finding repaired by the mutation moves to validation-pending until required evidence for the new head succeeds.
- A finding about an unchanged, still-applicable fact need not be rediscovered from the provider merely because another finding caused a commit.

The ledger therefore tracks semantic applicability separately from transport freshness and exact-head qualification evidence.

## Closure surfaces

For inline findings, prefer a concise reply that records the disposition and decisive validation before resolving the thread. For body-only findings, record the same information on an available review/PR surface that preserves an independently identifiable finding locator. If the execution environment keeps an internal ledger during work, mirror enough final closure evidence to a durable provider surface when the task or repository requires auditable handoff.

Semantic closure means the finding has a validated outcome. Provider resolution is evidence that the disposition was recorded, not the semantic outcome itself.
