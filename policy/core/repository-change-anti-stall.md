# Repository-change anti-stall policy

## Purpose

Repository-change orchestration MUST optimize for material progress, not visible tool activity. Repeated retrieval attempts, connector discovery, polling, or progress messages without a knowledge-state or repository-state delta are diagnostic activity, not progress.

This policy defines bounded diagnostic exploration, invalidated-path memory, strategy switching, stagnation detection, progress reporting, waiting semantics, and resume requirements. The repository-change orchestrator and its Work ledger MUST implement these semantics without turning the ledger into an execution transcript or duplicating the review finding ledger.

## Material progress

An iteration counts as **material progress** only when it changes at least one decision-relevant state, for example when it:

- obtains new evidence;
- supports or rejects a current hypothesis;
- narrows the failure scope or evidence gap;
- establishes a finding;
- changes implementation, branch, commit, PR, or merge state;
- changes exact-head validation or CI state;
- resolves or explicitly rejects a review finding with rationale;
- advances the qualification or mergeability frontier; or
- makes the next safe action materially more specific.

Tool calls, API-name discovery, searches, log-download attempts, and status messages do not count by themselves. A successful call that only reproduces already-known information is also not material progress.

Orchestration SHOULD track a compact `last_material_progress` and `progress_frontier`, rather than an activity counter.

## Strategy identity and repeated attempts

A diagnostic strategy is identified by the combination of:

- objective;
- evidence source;
- diagnostic method;
- relevant hypothesis; and
- observed failure mode.

Changing an endpoint name, response format, or connector action while pursuing the same evidence from the same source is ordinarily the same strategy. A **strategy switch** changes the evidence source, diagnostic method, or hypothesis in a way that can produce a new knowledge-state delta.

Repeated failures MUST be bounded. As a baseline, two failures with the same objective, evidence source, method, and failure mode require a strategy reassessment; a third identical retrieval MUST NOT be issued merely because another equivalent API spelling might work.

The baseline is not a universal hard-coded retry count. The agent MUST classify the failure before deciding whether another same-strategy attempt is justified:

| Failure class | Default treatment |
| --- | --- |
| Cheap deterministic retry | One bounded retry MAY be useful when inputs can be corrected or a deterministic race is plausible. |
| Transient failure | A bounded retry MAY be appropriate when the response supplies credible transient evidence such as rate limiting or service unavailability. |
| Authentication failure | Refresh or repair authorization if permitted; otherwise invalidate the path for the current authorization context. |
| Capability unavailable | Invalidate the path for the applicable runtime/capability context; do not retry without evidence of capability change. |
| Evidence unavailable | Switch source or method; repeated retrieval from the same source is not progress. |
| Semantic failure | Change the hypothesis, reproduction, or implementation; transport retries do not address semantic failure. |

Any exception to the baseline MUST have an explicit reason tied to the failure classification or a demonstrated execution-context change.

## Invalidated paths and negative capability memory

When a path is demonstrated unavailable, orchestration MUST record an **invalidated path** with enough state to prevent accidental retry:

- `path` — capability or evidence route, such as `gh-cli` or `direct-github-network`;
- `reason` — observed failure, such as `executable-not-installed` or `dns-resolution-unavailable`;
- `applicability` — scope such as current session, current runtime, connector version, or authorization context; and
- `retry_condition` — concrete evidence that would justify trying the path again.

An invalidated path MUST NOT be retried inside its applicability scope without evidence that the retry condition became true. “It may work now” is not evidence. Legitimate retry evidence includes a changed runtime, newly exposed connector capability, refreshed authorization, or independently observed network recovery.

Invalidated paths are operational negative-capability memory. They are not review findings and MUST NOT be copied into the review finding ledger unless they independently constitute a review finding.

## Diagnostic strategy switching

When the required evidence cannot be obtained within the current strategy budget, orchestration MUST prefer a diagnostic strategy switch over endpoint discovery. Examples include moving from raw CI logs to:

- check annotations;
- a successful-baseline versus failing-head diff;
- focused local or repository reproduction;
- generated-artifact inspection;
- workflow source plus failing-step inputs; or
- bounded delta inspection or bisect.

Trying another endpoint that exposes the same unavailable evidence is not necessarily a strategy switch. The transition MUST state the remaining evidence gap and why the new method can reduce it.

## Diagnostic budget and stagnation detection

Each diagnostic objective MUST have a bounded budget expressed in one or more dimensions, such as:

- same-source failures;
- no-progress tool calls;
- external round trips;
- repeated semantically equivalent progress messages; and
- optional elapsed diagnostic time when the environment can measure it reliably.

Recommended baselines are:

- same-source same-failure attempts: reassess after 2 failures;
- no-progress tool calls: perform a stall check after about 3 calls; and
- semantically equivalent progress reports: reassess after about 2 consecutive reports.

These numbers are guardrails, not the definition of a stall. The primary signal is absence of material knowledge-state, repository-state, validation-state, review-state, or qualification-frontier change while the same evidence gap persists. Tool discovery dominating productive actions is an additional stall signal.

When a budget is reached, the default transition is **change strategy**, not “stop working.” The objective is **blocked** only when suitable alternate strategies are exhausted, unavailable, unauthorized, or would violate scope or safety constraints.

## Tool and capability discovery

Tool discovery MUST be capability-first and bounded:

1. State the capability needed to advance the objective.
2. Perform one sufficiently scoped discovery step, or the minimum bounded set required by the connector interface.
3. Select an available action.
4. If that action cannot produce the needed evidence, switch diagnostic strategy rather than repeatedly searching tool names.

Tool-name exploration is not diagnostic progress unless it materially changes known capability state.

## Progress reporting

Progress reports MUST communicate knowledge and frontier changes rather than narrate activity. A useful report prioritizes:

- what materially changed;
- what was learned;
- what remains unknown;
- whether and why the strategy changed; and
- the next safe action.

Semantically equivalent consecutive reports such as “checking logs,” “checking logs another way,” and “continuing to inspect failure logs” are themselves a stagnation signal. After roughly two equivalent reports without material progress, orchestration MUST reassess the evidence gap and strategy before emitting another equivalent update.

## Waiting, stalling, blocking, and parallel work

Orchestration MUST distinguish these states:

- `external_wait` — an external process such as CI or review is making normal observable progress and the agent is not diagnostically stuck;
- `diagnostic_stall` — agent activity continues without material progress while an evidence gap remains;
- `blocked` — no authorized, in-scope, materially different strategy remains after bounded reassessment;
- `productive_parallel_work` — work performed while another dependency is pending that directly advances the declared completion frontier.

A long-running CI job that is progressing normally is `external_wait`, not `diagnostic_stall`.

Parallel work while waiting MUST directly advance completion. Appropriate examples include downstream stacked-branch preparation, PR-body synchronization, review-debt audit, exact-head applicability audit, deterministic test preparation, and known documentation synchronization. Unrelated architecture exploration, optional features, cleanup, or scope expansion MUST NOT be justified as parallel work merely because an external dependency is pending.

## Work ledger and resume contract

The Work ledger MUST preserve enough anti-stall state to make resume different from restarting the investigation. At minimum, when relevant, a durable checkpoint SHOULD make recoverable:

- current objective;
- current failure scope;
- current evidence gap;
- attempted paths as compact strategy-level summaries;
- invalidated paths and retry conditions;
- current hypothesis;
- current strategy and strategy attempt count;
- exhausted strategies;
- strategy switch reason;
- diagnostic budget state;
- progress frontier;
- last material progress; and
- next safe action.

The ledger MUST NOT record `call 1`, `call 2`, `call 3` as a transcript. On resume, the agent MUST restore invalidated/exhausted paths before any diagnostic retry and MUST selectively refresh only facts whose freshness matters. A new session MUST NOT repeat an invalidated path without satisfying its retry condition.

The review finding ledger remains authoritative for review findings. The Work ledger records only their orchestration effect, such as “review debt blocks final review request,” plus the canonical reference needed to recover the finding state.

## Review and completion interaction

Anti-stall behavior never relaxes exact-head validation, review-debt resolution, review applicability, or completion requirements. A strategy switch changes how evidence is acquired; it does not lower the evidence standard.

Before a final review request, unresolved review findings MUST still be resolved or explicitly rejected under the review policy. After the final review request, any final-review-stop rule remains controlling; anti-stall checkpointing MUST NOT create forbidden post-request reads, polls, or mutations.
