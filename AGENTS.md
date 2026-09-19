<!--
agent-policy-generated: true
configuration: .agent-policy.yml
DO NOT EDIT DIRECTLY
-->

# Repository agent instructions

These instructions were generated from shared policy profiles and repository-specific policy files.

## Policy system

- Semantic configuration: `.agent-policy.yml`
- Pinned shared toolchain: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3`
- Repository policy inputs:
  - `repository-policy/authority-boundary.md`
  - `repository-policy/history-boundary.md`
  - `repository-policy/architecture-decisions.md`
  - `repository-policy/release-trust.md`
  - `repository-policy/toolchain-safety.md`
  - `repository-policy/maintainer-validation.md`
  - `repository-policy/maintainer-merge-routing.md`
  - `repository-policy/documentation-boundary.md`
- Generated operational skills:
  - `.agents/skills/pr-review/SKILL.md`
  - `.agents/skills/orchestrate-repository-change/SKILL.md`
  - `.agents/skills/maintain-progressive-discovery/SKILL.md`

Do not edit this generated file directly. Change `.agent-policy.yml` or its repository policy inputs, then regenerate with the pinned toolchain. Before editing repository files, inspect any repository-local skill catalog that exists and read the relevant generated or handwritten skills.


## Discover repository topology fail-closed before mutation

Before planning repository mutations, inspect repository-local authority instructions
and the declaration at `contracts/repository-topology.json`. Absence selects no
explicit Composition topology; it never overrides authority instructions or proves
that branch histories are related. A present but unreadable, unsafe, malformed, or
unsupported declaration must halt dependent operations.

Composition owns topology semantics. Consume its immutable contract and validator
rather than maintaining an independent Policy definition. The operational adapter
uses the Composition snapshot identified in `agent_policy/_topology_contract/source.json`;
consumer schema files cannot relax its validation. Validation of a declaration is
not proof of the live Git graph. Before mutation, independently verify the current
branch, authority ancestry, immutable gitlinks, submodule repository identity, and
projection consistency against that declaration. Perform operations only on the
corresponding authority and refresh affected bindings before use.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/repository-topology-discovery.md`; rule ID: `core.discover-repository-topology-fail-closed`; severity: `mandatory`._


## Discover local-checkout topology separately from repository topology

Before a mutation whose safety depends on local checkout layout, inspect
`contracts/local-checkout-topology.json` independently from
`contracts/repository-topology.json`. Absence selects no explicit local-checkout
topology and never infers a default workspace layout. A present but unreadable,
unsafe, malformed, unsupported, or contradicted declaration must halt dependent
operations.

Composition owns local-checkout semantics. Consume the immutable schema and
validator snapshot identified in `agent_policy/_local_checkout_contract/source.json`;
consumer files cannot weaken it. Declaration validation proves only the intended
pattern, not current Git state.

For a declared Bare Worktree pattern, independently resolve and verify the common
Git directory, current worktree root, workspace root, linked-worktree inventory,
and target-branch occupancy using Git state. Never assume repository root equals
worktree root. Treat HEAD/index/working-directory state as worktree-specific and
refs, config, fetch, maintenance, and object storage as shared common-repository
state. Reject unsafe/symlinked declaration paths and any required live-state
contradiction before mutation.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/local-checkout-topology-discovery.md`; rule ID: `core.discover-local-checkout-topology-fail-closed`; severity: `mandatory`._


## Define the change contract before editing

Before editing, identify the requested outcome, the allowed change surface, the existing behavior and invariants that must be preserved, explicit non-goals, and the evidence required for acceptance. Treat unspecified behavior as preserved unless the requested change necessarily alters it; do not silently broaden the contract to resolve ambiguity or implementation difficulty.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/change-contract.md`; rule ID: `changes.define-contract`; severity: `mandatory`._


## Preserve the agreed acceptance baseline

Once implementation or audit begins against an agreed change contract, do not retroactively expand its scope, non-goals, completion criteria, required evidence, or stop condition. Rebaseline only with explicit authorization, and record the impact on completed work and prior evidence.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/acceptance-baseline.md`; rule ID: `changes.preserve-acceptance-baseline`; severity: `mandatory`._


## Keep changes within the requested scope

Do not modify files, behavior, dependencies, formatting, or architecture that are unrelated to the requested change. Inspect the final diff and remove incidental changes before reporting completion.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/change-scope.md`; rule ID: `changes.minimize-scope`; severity: `mandatory`._


## Escalate material semantic ambiguity

When an unresolved choice would materially affect observable behavior, data meaning, compatibility, architecture, risk, or scope, do not guess. Present the viable options, trade-offs, impact, and a recommendation, and obtain an explicit decision before making the dependent change.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/semantic-decision-gates.md`; rule ID: `decisions.escalate-semantic-ambiguity`; severity: `mandatory`._


## Do not weaken existing tests

Do not delete, skip, narrow, or relax an existing test merely to make a change pass. For a bug fix, add a regression test that fails before the fix and passes afterward whenever the failure can be reproduced deterministically.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/regression-safety.md`; rule ID: `regression.no-weaken-tests`; severity: `mandatory`._


## Run the repository's required verification

Use the verification command declared by the repository and add focused checks needed for the changed behavior or failure mode. Confirm that the executed checks cover the changed surface and the current revision; a check that is pending, skipped, not triggered, stale, blocked, or merely inspected is not a passing result. Report every required check that was not run or did not pass.

A validation claim is supported only when the claimed check is reachable from and actually executed by the authoritative validation entrypoint used to produce the evidence. A helper or test file existing beside a green workflow is not evidence that its assertions ran. Establish the effective path through workflow selection, canonical checker or test discovery, helper invocation, and the claimed assertion, including material conditions that can skip it. A module outside test discovery, an uncalled wrapper, an unused generated validation projection, or an assertion executed only in an optional/non-required lane cannot substantiate a claim of coverage by the required lane. Successful unrelated checks do not fill that gap.

Use repository-appropriate evidence such as source inspection with execution results, test discovery, workflow wiring tests, or runtime markers; universal static call-graph tooling is not required. Reachability alone is not a passing result: establish execution and the claimed outcome for the applicable revision, configuration, and evidence layer. If the effective path or execution cannot be established, report that coverage as unverified rather than accepting a green aggregate result.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/testing.md`; rule ID: `testing.run-required-checks`; severity: `mandatory`._


## Test material invariants beyond the nominal path

When a change relies on a structured contract, mutable lifecycle, asynchronous completion, relation set, identity mapping, generated projection, resource boundary, or effective containment boundary, identify the material invariants that make the changed behavior correct and add focused adversarial coverage for the applicable negative, transition, stale-state, malformed-input, converse/completeness, or boundary cases.

Derive the cases from the changed invariant rather than from a fixed universal matrix. Do not require unrelated combinations, speculative stress cases, or exhaustive permutations when they do not exercise a material failure mode. A focused test may be unit-, integration-, system-, or workflow-level as long as it reaches the layer where the invariant can actually fail.

When a defect or review finding proves that one dimension of an invariant was previously unguarded, inspect the bounded sibling dimensions that share the same root cause before declaring the repair complete. Examples include success versus failure completion, current versus stale context, listed relation versus required converse, missing versus extra structured fields, and nominal outer bound versus effective inner containment boundary. Add regression evidence for sibling cases that are materially reachable; do not broaden the change into unrelated cleanup.

Close the materially reachable finding family before deliberately sending the repair to expensive final qualification or independent acceptance review. Where correctness depends on a downstream consumer, exercise a small representative path through the actual canonical entrypoint and consumer setup. A mock assertion that a helper received an argument does not establish that the real consumer received the required bytes, state, or resource. Keep unit tests where useful, but obtain evidence at the boundary where the changed invariant can fail; use existing validators rather than duplicating their semantics.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/adversarial-invariant-testing.md`; rule ID: `testing.require-adversarial-invariant-coverage`; severity: `mandatory`._


## Keep verification evidence bound to its layer

Bind every verification result to the exact revision or artifact and to its evidence layer. Report repository-local checks, environment-dependent checks, remote CI, and independent audit separately; success in one layer does not prove success in another.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/evidence-layers.md`; rule ID: `verification.separate-evidence-layers`; severity: `mandatory`._


## Keep derived artifacts synchronized

When a change affects generated, mirrored, compiled, or otherwise derived artifacts, update them from their declared source of truth using the repository's documented process and verify that no stale or missing output remains. Do not hand-edit generated artifacts unless the repository explicitly designates that operation as authoritative.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/generated-artifacts.md`; rule ID: `consistency.synchronize-derived-artifacts`; severity: `mandatory`._


## Maintain progressive-discovery index boundaries

When a repository opts into this profile, maintain `index.md` files as semantic
discovery boundaries rather than as a mirror of the physical filesystem. Add an
authored index only where a meaningful group of related destinations needs an
orientation point; a deep destination may be linked directly and a directory
may deliberately have no index. Classify each relevant directory as needing an
authored index, a generated index, no index, or an explicit authority decision.

An authored index is a small navigation document: a level-one heading, useful
section headings when needed, Markdown links, short descriptions, and blank
lines. It must not duplicate path metadata, timestamps, Git identities,
provenance, release state, or other data owned by a catalog, manifest, schema,
or record. A README explains what a directory is; an index explains where to go
next.

A generated index is a projection of an authoritative inventory or other
declared source of truth. Generate it deterministically, validate its freshness,
and do not hand-edit it. The expected discoverable set must be derived from
authoritative inventories, catalogs, manifests, registries, schemas, contracts,
records, or documentation manifests before consulting an existing index; an
existing index alone cannot prove completeness.

When a relevant source, document, component, recipe, schema, policy rule,
record, generated document, or publication surface changes, re-run the
repository's progressive-discovery maintenance Skill. The Skill may propose
create, update, delete, or regenerate operations in dry-run mode, but it may
mutate authoritative sources only after an explicit apply authorization.
Provider-maintenance documentation and consumer-distributed documentation are
separate surfaces, and a consumer without a publication system must not be
forced to invent one. Repository-local adapters may add validation commands,
authoritative inventory locations, and explicit exclusions, but may not redefine
these generic semantics.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/progressive-discovery/maintain-index-boundaries.md`; rule ID: `discovery.maintain-index-boundaries`; severity: `mandatory`._


## Preserve externally observable contracts

Do not break public APIs, serialized data, configuration formats, command-line interfaces, or migration paths unless the requested change explicitly authorizes the incompatibility and documents its consequences.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/compatibility.md`; rule ID: `compatibility.preserve-contracts`; severity: `mandatory`._


## Revalidate destructive actions against current state

Immediately before deleting, overwriting, migrating, deploying, publishing, force-updating, or otherwise making an irreversible or externally visible change, re-read the target's current state and revalidate its identity, scope, version or revision, protections, and conflicting uses. Prefer dry-run, least-scope, and idempotent operations; do not authorize the action solely from stale observations made earlier in the task.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/destructive-actions.md`; rule ID: `safety.revalidate-destructive-actions`; severity: `mandatory`._


## Bind validated state to the effective operation

When correctness or safety depends on a validated or authorized target identity, scope, or other mutable precondition, ensure that the same effective target and required preconditions remain bound to the operation through use. Account for normalization, indirection, aliases, redirects, rebinding, and concurrent mutation; use stable identity or protected state, an atomic, transactional, or serialized mechanism, or revalidation at a protected commit or use boundary as appropriate. Fail closed if the operation can proceed against a different effective target or after the condition that authorized or validated it has become stale.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/validation-operation-binding.md`; rule ID: `safety.bind-validated-state-to-operation`; severity: `mandatory`._


## Limit rollback to changes owned by the operation

For a multi-step mutation, complete preflight before the first write, revalidate the live state at the commit boundary, and track which paths the current operation created or changed. On failure, roll back only those owned changes; never delete or overwrite pre-existing or concurrently created state as cleanup unless explicitly authorized.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/transaction-ownership.md`; rule ID: `safety.limit-rollback-to-owned-changes`; severity: `mandatory`._


## Report actual state and residual uncertainty

Distinguish implemented, generated, executed, verified, and merely inferred results. State unresolved failures and unverified assumptions explicitly.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/truthful-reporting.md`; rule ID: `reporting.truthful-status`; severity: `mandatory`._


## Separate task completion from review and merge authorization

Repository-change work must distinguish implementation task completion, validation completion, independent review, review completion, merge authorization, and the merged result. Completing implementation or validation does not establish that review was requested, review was completed, or merge authorization exists. Progression controls construction ordering; completion controls the agent's stopping boundary. A progression strategy must not by itself force review acquisition or merge completion.

A repository-change task may declare human-handoff as its completion boundary. Human handoff is valid completion when the agent has completed the authorized implementation and validation work, reports the independent-review state truthfully, reports merge authorization as not established, and leaves every pull request open and unmerged. When no applicable pre-existing review evidence establishes another state, report independent review as not requested or outstanding. When applicable pre-existing review evidence already establishes completed review, preserve and report that REVIEW_COMPLETE state rather than downgrading it merely because human-handoff was selected. When human-handoff is selected, the agent must not initiate a new merge-acceptance review request through reviewer assignment, provider invocation, requested-reviewer state, or any other review-request mechanism by default. An explicitly authorized diagnostic request must be selected by the adaptive review-selection rule after its candidate and coverage are established. Issue the one logical request represented by the final packet after the authorized work is stable; additional diagnostic scope remains permitted when new evidence or changed bindings makes prior coverage inapplicable. The diagnostic result is not ordinary per-member merge-acceptance evidence, does not authorize merge, does not waive future exact-head review requirements, must not create a review-retry loop, and need not complete before handoff unless explicitly required. Existing review evidence may be observed, inspected, and reported, but handoff does not acquire new acceptance evidence.

Human handoff is not a review waiver, does not remove acceptance requirements for a later review or merge, and does not authorize a merge. Reports must not label a handoff review complete unless applicable pre-existing review evidence establishes that state, and must not label the handoff merge ready or merged. When the task explicitly requires a final diagnostic request, select its current scope and binding through the adaptive review-selection rule, issue one logical request after the authorized work is stable, and stop without waiting for its result. A later continuation may acquire additional scope when new evidence or a changed contract makes the prior result inapplicable; this is not a retry loop or a waiver. Use explicit state labels such as IMPLEMENTATION_COMPLETE, VALIDATION_COMPLETE, REVIEW_NOT_REQUESTED, REVIEW_PENDING, REVIEW_COMPLETE, HANDOFF_READY, MERGE_READY, and MERGED only when the corresponding state is established.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/repository-change-completion.md`; rule ID: `changes.separate-task-review-merge-state`; severity: `mandatory`._


## Repository-change anti-stall policy

## Purpose

Repository-change orchestration MUST optimize for material progress, not visible tool activity. Repeated retrieval attempts, connector discovery, polling, or progress messages without a knowledge-state or repository-state delta are diagnostic activity, not progress.

This policy defines bounded diagnostic exploration, invalidated-path memory, strategy switching, stagnation detection, progress reporting, waiting semantics, and artifact-neutral durable-resume requirements. Repository-change execution procedures and their provider-specific checkpoint mechanisms MUST implement these semantics without turning resume state into an execution transcript or duplicating review-finding authority.

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

A diagnostic strategy is identified by the combination of deliberately selected inputs:

- objective;
- evidence source;
- diagnostic method; and
- relevant hypothesis.

Observed failure mode is an outcome of an attempt, not part of strategy identity. Track it per attempt for failure classification and retry decisions without allowing a changed outcome to reset the strategy attempt count.

Changing an endpoint name, response format, or connector action while pursuing the same evidence from the same source is ordinarily the same strategy. A **strategy switch** changes the evidence source, diagnostic method, or hypothesis in a way that can produce a new knowledge-state delta.

Repeated failures MUST be bounded. As a baseline, two failures using the same strategy with the same observed failure mode require a strategy reassessment; a third identical retrieval MUST NOT be issued merely because another equivalent API spelling might work.

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

Each diagnostic objective MUST have a global no-material-progress bound that advances for every diagnostic action that fails to move decision-relevant state, including successful calls that only reproduce already-known information. Implementations MAY also maintain narrower budgets such as:

- same-source failures;
- no-progress tool calls;
- external round trips;
- repeated semantically equivalent progress messages; and
- optional elapsed diagnostic time when the environment can measure it reliably.

A narrower counter MUST NOT be the only bound when other no-progress execution paths remain possible. Every applicable diagnostic path must eventually reach reassessment while the same evidence gap persists.

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

- `external_wait` — a required external dependency such as CI or review is validated as legitimately pending and has a concrete resume condition; granular or changing provider progress need not be observable;
- `diagnostic_stall` — agent activity continues without material progress while an evidence gap remains;
- `blocked` — no authorized, in-scope, materially different strategy remains after bounded reassessment;
- `productive_parallel_work` — work performed while another dependency is pending that directly advances the declared completion frontier.

A long-running CI job that is validly pending is `external_wait`, not `diagnostic_stall`, even when the provider exposes only an unchanged `pending` or `in_progress` status. Orchestration MUST separately define the condition that makes an opaque wait stale, timed out, failed, or otherwise eligible for reassessment; an unchanged status alone is not agent stall.

Observation of an `external_wait` MUST itself be bounded. Orchestration MUST NOT enter an unbounded or long-lived synchronous sleep, watch, or poll loop merely to wait for CI, review, deployment, publication, or another external dependency to finish. Each foreground observation interval MUST have a finite stop condition appropriate to the execution surface, such as a bounded number of status reads, a bounded elapsed observation window when reliable time measurement exists, or a provider operation with an explicit finite timeout. This bounds agent observation activity; it does not impose a universal timeout on the external dependency itself.

If that observation interval ends while the dependency is still legitimately pending, orchestration MUST preserve the dependency as `external_wait`, record its identity and concrete resume condition, and switch to available `productive_parallel_work`. When no authorized productive parallel work remains and further progress depends only on the external result, orchestration MUST checkpoint recoverable state and yield control at a resumable boundary rather than keep a worker or interactive turn occupied solely by synchronous waiting. Yielding control MUST NOT be reported as task completion, acceptance, or satisfaction of the pending dependency. On a later authorized resume, orchestration MUST refresh the dependency state before acting on it.

Parallel work while waiting MUST directly advance completion. Appropriate examples include downstream stacked-branch preparation, PR-body synchronization, review-debt audit, exact-head applicability audit, deterministic test preparation, and known documentation synchronization. Unrelated architecture exploration, optional features, cleanup, or scope expansion MUST NOT be justified as parallel work merely because an external dependency is pending.

## Durable resume state

Any durable checkpoint used to resume repository-change work MUST preserve enough anti-stall state to make resume different from restarting the investigation. At minimum, when relevant, recoverable state SHOULD include:

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

Durable resume state MUST NOT become a call-by-call transcript. On resume, orchestration MUST restore invalidated and exhausted paths before any diagnostic retry and MUST selectively refresh only facts whose freshness matters. A new session MUST NOT repeat an invalidated path without satisfying its retry condition.

Review-finding identity, disposition, repair reasoning, qualification, and closure evidence remain owned by the applicable review procedure. Durable resume state may record only the review state needed for orchestration plus the canonical reference required to recover authoritative finding details; it MUST NOT become a second finding authority.

## Review and completion interaction

Anti-stall behavior never relaxes exact-head validation, review-debt resolution, review applicability, or completion requirements. A strategy switch changes how evidence is acquired; it does not lower the evidence standard.

Before a final review request, unresolved review findings MUST still be resolved or explicitly rejected under the review policy. After the final review request, any final-review-stop rule remains controlling; anti-stall checkpointing MUST NOT create forbidden post-request reads, polls, or mutations.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/core/repository-change-anti-stall.md`; rule ID: `changes.prevent-diagnostic-stall`; severity: `mandatory`._


## Do not expose or commit secrets

Do not print, persist, or commit credentials, private keys, access tokens, session material, or unredacted sensitive configuration. Use established secret-management mechanisms.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/security/secrets.md`; rule ID: `security.no-secrets`; severity: `mandatory`._


## Validate data at trust boundaries

Validate untrusted input before it reaches privileged operations, persistence, command execution, or external requests. Preserve existing authentication and authorization checks.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/security/input-validation.md`; rule ID: `security.validate-boundaries`; severity: `mandatory`._


## Bind cumulative review evidence to an ordered pull-request stack

The ordinary merge-acceptance path for a stacked pull-request member is a completed independent review bound to that member's exact current head. A whole-stack architecture, dependency, or completeness audit is useful diagnostic evidence but is not merge-acceptance evidence for lower members unless it also satisfies every cumulative binding below. Cumulative multi-member acceptance review is optional; stacked progression does not require it. Whole-stack names the members and invariants under examination; it imposes no numeric limit on diagnostic requests.

When a completed review is claimed to cover multiple members of a stacked pull-request topology, acceptance evidence must bind to the integration base exact SHA and tree, the ordered stack membership, each member exact head SHA, the stack tip exact SHA, the cumulative reviewed scope, the review contract, reviewer independence, the review completion state, and material limitations.

A review event, approval state, or tip-only review must not infer lower stack coverage or establish acceptance coverage for lower stack members by inference. Each covered member must be identifiable from explicit cumulative coverage evidence. Missing, ambiguous, or provider-only coverage is incomplete evidence and keeps merge authorization fail-closed.

If a provider cannot clearly attest one or more lower-member cumulative bindings, stop treating that review as cumulative merge evidence. Preserve any valid whole-stack audit findings, then use the ordinary individual exact-head review path for uncovered members when acceptance review is authorized. Do not repeatedly request cumulative clarification or reacquire cumulative review merely to recover an optimization that is not required for stacked progression.

Evaluate applicability again when a member exact head changes, stack ordering changes, integration base changes, cumulative scope changes, or the review contract changes. Reuse unchanged evidence only when its bindings and remaining stack applicability are established; if applicability is unknown, fail closed. A lower member merge may move a later member's base without mechanically invalidating all evidence or requiring an upper-head rewrite solely for base movement, but the changed bindings and remaining coverage must be evaluated before relying on it.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/stacked-review-coverage.md`; rule ID: `pull-request.require-explicit-stacked-review-coverage`; severity: `mandatory`._


## Defer revision-bound qualification until an authority boundary requires it

A pull-request head or stacked-member commit that exists during dependency-safe construction is a **construction head**: an exact Git identity for the current work state, not automatically a final qualification identity. A **construction candidate** (or **provisional candidate**) is a construction state that may continue to change because authorized implementation, upstream dependency work, finding disposition, or other justified mutation is still in progress; full exact-head qualification is not required for a construction candidate. A **qualification candidate** (or **qualification head**) is an intended candidate revision deliberately frozen so required acceptance evidence can bind to that exact revision. A **publication identity** is an immutable revision, digest, artifact, or equivalent identity made authoritative for provenance, release, publication, distribution, or another external consumer boundary.

In an ordered stack, the **construction frontier** records how far dependency-safe implementation has advanced; the **qualification frontier** records which intended candidates have entered revision-bound qualification at an applicable boundary. These are independent views of the existing candidate lifecycle, not new acceptance states. Descendants may be implemented, focused-validated, and represented by pull requests ahead of the qualification frontier while remaining provisional. Review latency alone must not block safe descendant construction; do not propagate a known material prerequisite defect into that construction.

Before intentionally acquiring final descendant evidence, identify expected prerequisite invalidators and the evidence bindings they affect. If a known actionable repair or other currently planned prerequisite movement is expected to invalidate the descendant's exact head, exact-head review, exact-revision CI, provenance, generated or signed artifact, publication identity, or exact-SHA integration binding, defer that intentional final evidence cycle while the invalidator remains. Continue safe implementation and focused diagnostics that do not embed known-invalid behavior. A prerequisite review merely being pending does not establish expected invalidation and must not create a blanket downstream qualification prohibition.

Decide by actual dependency and evidence bindings, not stack position alone. Parallel evidence acquisition can be justified when it does not bind to the moving prerequisite identity, is inexpensive or independently useful, or when delay would create a larger critical-path or safety cost. For deliberately costly speculative qualification despite credible invalidation risk, record the affected bindings and why acquiring evidence now is useful; no numeric cost model is required. These are scheduling reasons, not permission to accept stale evidence or skip a boundary's required qualification. An immediate authority boundary requires its evidence now; deferral must not postpone required qualification or the prerequisite repair necessary to make it valid.

Until an applicable repository authority or explicit task boundary requires revision-bound acceptance, independent review, provenance, release, publication, merge, or another immutable binding, do not intentionally freeze a provisional candidate solely to acquire final revision-bound evidence or materialize a downstream immutable identity that is expected to follow still-mutable prerequisites. The mere existence of a commit SHA, branch head, or pull request does not by itself establish that the candidate has entered final qualification.

Continue authorized implementation, focused diagnostic validation, pull-request creation, dependency-safe downstream work, and naturally triggered CI while a candidate remains provisional. Under a staged CI model, this may include CI preflight, core validation, and applicable focused or conditional integration. Full qualification should normally remain bound to the authority-defined qualification boundary rather than being deliberately reacquired for every provisional head. Do not treat those activities, or an observed successful run on a provisional head, as proof that final qualification has been completed. Do not use this rule to suppress repository-required automatic checks or to substitute focused diagnostics or earlier CI stages for qualification once an applicable boundary requires it.

When a revision-bound boundary is reached, stabilize the actual prerequisite identities, freeze the intended candidate revision or ordered candidate revisions, and acquire every exact-revision evidence item required by the applicable authority. When provenance, publication, release, generated projection, signed material, or another downstream artifact embeds an upstream exact revision or digest as part of its authoritative meaning, perform that final immutable materialization only after the prerequisite identity is stable enough to bind. If a later justified mutation changes an evidence binding, invalidate and reacquire only the affected revision-bound evidence as required by the applicable evidence rules.

This deferral is an execution-efficiency discipline, not an acceptance waiver. It must not delay an urgent security, operational, data-integrity, or publication-integrity repair, and it must not weaken exact-head CI, independent exact-head review, immutable-head merge protection, release trust, provenance, publication, or other authority-defined completion requirements.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/defer-revision-bound-qualification.md`; rule ID: `pull-request.defer-revision-bound-qualification-until-required`; severity: `mandatory`._


## Evaluate merge readiness against the current target branch HEAD

Before declaring a pull request merge-ready, establish the current target branch full commit SHA and evaluate the proposed change against that exact target state. If the proposed head is not based on the current target head, inspect the intervening target change and determine whether it affects scope, validation applicability, review conclusions, mergeability, or another acceptance condition.

Synchronize or rebuild the proposed head only when that impact evaluation or current repository policy requires it. Do not require proposed-head synchronization solely because the target branch moved when the intervening change is established not to invalidate the applicable acceptance evidence.

Target-branch movement invalidates the freshness decision itself, but it does not by itself invalidate unrelated exact-head CI or review evidence. Do not claim target-branch freshness from cached, historical, or inferred branch metadata.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/target-branch-head-freshness.md`; rule ID: `pull-request.verify-target-branch-head-freshness`; severity: `mandatory`._


## Select review scope from current bindings

Select review work from the requested purpose, exact candidate bindings, explicit
coverage, known findings, and the authority-owned impact closure. `whole-stack` is
a scope description, not a review-count allowance and not an instruction to read
all five authority branches for every task.

Before acquiring review, establish the smallest scope that is supported by current
evidence. Reuse an existing completed result only when its purpose, candidate
binding, review contract, independence, completion state, and explicit coverage
cover every required member and invariant. A missing head, unknown scope,
partial or failed result, incomplete pagination, missing metadata, or unknown
applicability is not completed coverage.

Do not acquire the same objective, purpose, candidate, scope, contract, and input
binding twice. In other words, the duplicate key is the same objective, purpose, candidate, scope, contract, and input binding. If an equivalent request is in progress or its submission result is
unknown, reconcile the provider state and existing handle before considering a new
request. A request key is a comparison aid, not a provider idempotency guarantee;
when action ownership or serialized submission cannot be established, preserve the
uncertainty and hand off safely.

For a bounded local change, acquire an independent exact-head review of the change
and its affected closure when no applicable result covers it. A new head does not
automatically require a whole-stack audit. If a shared contract, trust boundary,
dependency topology, cross-member interaction, or unbounded/unknown impact is
changed, expand to the related stack and record the reason. Unknown impact remains
unknown until the required authority-owned inspection or review resolves it.

Additional diagnostic or whole-stack review is permitted when important new
evidence, an incomplete prior result, a changed contract, or newly uncovered scope
justifies it. There is no global numeric cap and no universal rule that forces every
post-review change into targeted scope alone. Cost, elapsed time, line count,
green tests, or a warning threshold may be reported but never establishes a waiver.

The planner is not a semantic validator, reviewer, merge gate, or authorization
issuer. It must use the formal authority validation and the shared
`pr-merge-gate` for those decisions. A diagnostic result remains separate from
independent exact-head merge-acceptance evidence.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/review-scope-selection.md`; rule ID: `pull-request.select-review-scope-from-current-bindings`; severity: `mandatory`._


## Preflight revision-bound review acquisition

Before intentionally requesting an independent review that is expected to cover a named pull-request head, commit, branch ref, or stacked set of revisions, refresh the live identity facts needed to construct that request and verify that every revision binding the request depends on is currently resolvable.

For a single pull request, verify that the intended reviewed commit is the current proposed head and that any branch or ref supplied to the review provider still resolves to that commit. For cumulative or whole-stack review, also verify the ordered stack membership and every explicitly bound integration-base, member-head, and tip identity needed by the review contract. If a required identity is missing, stale, moved, ambiguous, or no longer matches the intended candidate, do not invoke the reviewer with that binding; refresh the affected state and construct a corrected request first.

For descendant exact-head acceptance review, first apply the expected-invalidation gate in `pull-request.defer-revision-bound-qualification-until-required`. A resolvable construction head alone does not establish that intentionally acquiring final review is appropriate. Pending prerequisite review alone is not a prohibition; the canonical gate governs sequencing by the affected evidence bindings.

This preflight protects review acquisition from avoidable transport and identity failures. It is not completed-review evidence, does not establish merge readiness, does not weaken exact-head review requirements, and must not become a fixed waiting period or an excuse to re-read unrelated state. Naturally delayed provider execution can still fail after a correct preflight; report such provider failure separately from substantive review completion.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/review-acquisition-preflight.md`; rule ID: `pull-request.preflight-review-acquisition`; severity: `mandatory`._


## Disposition known findings before review reacquisition

Before intentionally starting a new merge-acceptance review acquisition cycle for a proposed candidate, account for every material actionable finding already known from submitted review evidence and other applicable review-result surfaces and applicable to that candidate. For each such finding, establish either a repair validated for the current proposed head or an evidence-backed no-change disposition validated against the current proposed head and applicable authority, and record enough finding-level closure evidence on an auditable review or pull-request surface to distinguish that finding from unresolved or deferred material findings. Do not intentionally request another merge-acceptance review merely to accumulate more findings while a known material actionable finding lacks either the required current-head validated outcome or the required closure evidence.

Apply this requirement independently of provider representation. A finding in a resolvable thread, a top-level review body, an ordinary pull-request comment, a summary, or another non-resolvable review surface remains subject to the same disposition and closure-evidence requirement when it is independently actionable. Apply the canonical cross-surface review-result discovery rule when reconstructing that known-finding backlog. Provider thread resolution is bookkeeping and does not itself establish semantic closure. Closure evidence records the validated disposition for auditability; the provider surface or resolved UI state does not redefine the semantic outcome.

Treat reviewer text as a defect hypothesis rather than authority. A finding first reported against an older head may be re-evaluated against the current proposed head; if current evidence falsifies it, record the decisive no-change disposition and the required closure evidence instead of making an appeasement edit. Do not force an unrelated suggestion into the current pull-request scope solely to clear the reacquisition gate. The review-result applicability rule governs whether historical evidence can establish completion for a current review cycle; it does not erase an earlier finding whose causal condition remains applicable.

This rule governs intentional acquisition of a new review cycle. It does not require delaying an urgent operational, security, or data-integrity repair in order to batch review work; does not prohibit naturally triggered CI or review-provider behavior; and does not require waiting for hypothetical future findings. Before any explicitly authorized diagnostic or merge-acceptance request, apply the adaptive review-selection rule to the current purpose, candidate, scope, and coverage, including the diagnostic purpose when that is the selected purpose. This applies to every new merge-acceptance review cycle as well as to a diagnostic request. Perform the required known-finding disposition and closure checks before invoking a reviewer; the request must have the validated dispositions and recorded closure evidence required above. A diagnostic audit remains distinct from merge-acceptance evidence and does not satisfy or waive the independent exact-head review requirements for later merge authorization. A newer request for one purpose must not supersede an applicable result for a different purpose merely because it is newer.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/review-reacquisition-after-disposition.md`; rule ID: `pull-request.disposition-known-findings-before-review-reacquisition`; severity: `mandatory`._


## Discover review results across applicable surfaces

Before classifying the current review cycle as complete, problem-free, or containing findings, inspect the applicable provider-supported review-result surfaces for the pull request rather than treating a review-submission object as the complete review result. The inspected set must include submitted review bodies, ordinary pull-request or issue comments that can carry reviewer results, inline review comments and resolvable review threads, and any other provider surface or signal that the applicable review procedure or provider contract defines as capable of carrying review-result semantics.

Do not infer `no findings` from an empty review-submission body, an approval state, an empty thread list, or the absence of findings on any single provider surface. A material actionable finding discovered on any applicable review-result surface remains a finding even when another surface reports approval or contains no finding. When provider mechanics separate a logical review across multiple surfaces, reconstruct the logical result before classifying it.

Treat reactions and similar provider signals as semantic review evidence only when the applicable workflow, review procedure, or provider contract establishes their meaning for the result being classified. A reaction without such a defined meaning is uninterpreted provider state; at most it may corroborate separately established evidence. Do not interpret an acknowledgement or attention signal as review completion, approval, or absence of findings merely from its glyph or provider presentation.

If the execution environment cannot inspect a provider surface that is known to be capable of carrying applicable review-result semantics, or cannot determine whether a discovered signal has result semantics, record the limitation and keep any affected completion or no-findings conclusion fail-closed. This discovery rule determines whether the logical review result has been observed sufficiently; the separate review-result applicability rule determines which observed evidence belongs to the current review cycle and revision.

Retain a bounded observation index of the inspected surfaces, retrieval completeness or errors, and evidence locators, tied to the applicable request or request-less cycle anchor and reviewed revision. Use it to refresh only changed or materially stale observations. An unchanged head does not establish that comments, threads, or review results are unchanged. Thread resolution or disappearance of an attention signal does not independently prove current-head acceptance. Reuse the existing Work ledger and review-finding authority for orchestration and disposition; do not create another acceptance ledger or an unbounded polling loop.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/review-result-discovery.md`; rule ID: `pull-request.discover-review-results-across-applicable-surfaces`; severity: `mandatory`._


## Require an independent exact-head review before merge

Before merging a pull request, require at least one completed review from an independent reviewer or review system for the exact proposed head commit. A review request, pending review, absence of review findings, or zero completed reviews is not review evidence and must block merge. The agent or actor that implemented the proposed change must not count its own self-review as the required independent review.

A submitted or provider-recorded review object is not by itself evidence that the review's required analysis completed. The relied-upon evidence must establish, under the applicable review procedure or review contract, that the required analysis completed for the exact proposed head. A review that reports itself as incomplete, partial, failed, or materially limited such that required analysis was not completed must not satisfy the independent-review requirement, even when a provider records that review as submitted or completed. If current evidence cannot establish whether the required analysis completed, keep merge authorization fail-closed rather than inferring completion from a provider event, review state, or the absence of blocking findings.

Before relying on that evidence, apply the canonical cross-surface review-result discovery rule and the review-result applicability rule. Establish the logical review result across applicable provider surfaces, bind it to the applicable review purpose and cycle, and verify that the relied-upon completion evidence satisfies this rule's exact-head requirement.

The relied-upon review evidence must identify the reviewed exact head through review metadata or an unambiguous completed review result. If the proposed head changes after that review, treat the review as stale and obtain a new completed review for the new exact head before merge.

If the required reviewer is unavailable or does not complete the review, report the pull request as blocked rather than waiving the requirement. Only an explicit repository policy may define an exception; an implementing agent must not invent or self-authorize one.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/independent-exact-head-review.md`; rule ID: `pull-request.require-independent-exact-head-review`; severity: `mandatory`._


## Bind review-result classification to the applicable cycle and revision

Before classifying review as pending, complete, problem-free, or containing findings, determine whether an applicable review request exists for the review purpose being evaluated. When one or more applicable requests exist, identify the latest applicable review request and bind the classification to that review cycle. Do not let an older completed review establish completion or `no findings` for a later applicable request that is still pending, incomplete, failed, or otherwise unresolved.

When no applicable review request exists, a completed independent review result may itself define the current review cycle only when its review purpose, reviewer or review-system independence, completion state, and required revision binding can all be positively established from the result and the applicable review contract or provider semantics. Use the completed result's own source identity and completion event as the cycle anchor; do not invent a review-request event merely to make valid unsolicited or automatically triggered review evidence classifiable. This fallback does not apply when a later applicable request exists for the same purpose and candidate lineage: that request defines the current cycle under the normal supersession rule. If the request-less result's purpose, completion state, independence, or required candidate binding is unknown, keep the affected completion or no-findings conclusion fail-closed.

Determine applicability by purpose as well as time. A diagnostic whole-stack audit, merge-acceptance review, security review, or other explicitly distinct review purpose does not supersede a different purpose merely because its request is newer. When several requests belong to the same purpose and candidate lineage, the latest applicable request defines the current cycle unless repository authority or the review procedure explicitly establishes different aggregation semantics.

When observed review evidence identifies a reviewed commit, head SHA, stack identity, or other revision binding, compare that binding with the current proposed candidate before relying on the evidence. Classify the evidence as current and applicable only when the required revision relation is established by the applicable review contract. For merge-acceptance evidence governed by the independent exact-head rule, this requires the exact current proposed head. If the candidate head changed after that review, the completed review is stale for merge acceptance. If the required revision binding is absent or its applicability cannot be established, keep the affected completion or no-findings conclusion fail-closed rather than assuming that the review covered the current candidate.

Review-cycle completion applicability and finding applicability are distinct. Evidence from an earlier review cycle must not by itself establish completion or `no findings` for a later cycle, but a material actionable finding reported earlier remains part of the known finding backlog while its causal condition remains applicable to the current candidate and until it has a validated repair or evidence-backed no-change disposition. Do not discard a finding solely because the head changed or a newer review request exists.

When current evidence is insufficient to determine which request or request-less result defines the applicable cycle, what purpose the result served, or whether its revision binding applies to the current candidate, record the ambiguity and do not promote the review state to complete or problem-free. Historical evidence may still be retained for traceability and finding disposition without being accepted as current-cycle completion evidence.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/review-result-applicability.md`; rule ID: `pull-request.bind-review-result-classification-to-applicable-cycle-and-revision`; severity: `mandatory`._


## Close review findings before merge

Before merging a pull request, inspect the current submitted reviews, resolvable review threads, and actionable findings for the exact proposed head. Apply the canonical cross-surface review-result discovery rule so findings carried by ordinary comments, review bodies, inline comments, resolvable threads, or other applicable provider-supported surfaces are not omitted merely because they are absent from a submitted-review object or thread list. Treat each independently actionable finding as requiring its own repair or explicit disposition and validation, whether or not the provider exposes that finding as a resolvable thread.

When a resolvable thread exists, do not mark it resolved until the required repair or evidence-backed no-change disposition has been completed and validated for the current head. A code or documentation change by itself is not proof that the finding is resolved, and a provider's resolved UI state is bookkeeping rather than semantic proof of remediation.

When an actionable finding exists only in a top-level review body or another non-resolvable review surface, the absence of a thread does not mean the finding is resolved. Inspect it, repair it or record an explicit finding-level disposition, validate that outcome, and retain enough finding-level closure evidence to distinguish it from unresolved or deferred material findings.

Do not treat an unresolved material finding as complete merely by changing provider UI state. Do not merge while any material actionable finding lacks validated remediation or an explicit validated disposition, unless an explicit repository policy defines a documented exception. After that semantic closure is established, mark the corresponding provider thread resolved when such a thread exists and provider mechanics permit it.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/review-thread-closure.md`; rule ID: `pull-request.close-review-threads-before-merge`; severity: `mandatory`._


## Structure CI as staged validation with an explicit preflight

When repository validation contains checks with materially different cost, scope, or applicability, define an explicit staged CI model appropriate to that repository. Prefer these roles when they are meaningful: **CI preflight** for the cheapest deterministic checks that can reject an obviously invalid candidate; **core validation** for baseline correctness checks that are broadly applicable; **conditional integration** for integration, browser, cross-surface, compatibility, or similar checks whose applicability may depend on the proposed change; and **full qualification** for the broad authority-defined acceptance performed when a completion, merge, release, publication, or equivalent qualification boundary requires it. A repository may collapse or omit a stage when no meaningful distinction exists. Stage names describe validation role and execution cost, not importance.

Place CI preflight before dependent expensive validation when the repository workflow can do so without weakening coverage or creating a larger delay than the work it avoids. A preflight failure must not be interpreted as permission to ignore the defect, and dependent expensive validation need not continue for a candidate already known to be invalid. Independent checks may still run in parallel when they provide useful evidence or parallel execution is operationally cheaper than serialization. Do not serialize CI merely to satisfy the taxonomy. When a newer candidate supersedes an older one, cancel or supersede expensive work whose evidence can no longer satisfy any current evidence requirement when the repository platform safely permits that cancellation. Preserve still-applicable evidence under `pull-request.reuse-valid-exact-head-evidence`; head movement alone is not a cancellation reason. Supersession is not by itself a product defect or passing qualification for the successor.

Apply the same early-rejection discipline to local qualification. Before an expensive dependent suite, use cheap canonical checks for required environment availability, dependency and source identity, and pre-existing undeclared generated contamination when material to that suite. Preventing new generated files is not evidence that existing contamination is absent. When runtime launch is a prerequisite, a bounded real launch probe can reject an unusable environment before semantic suites; it does not replace runtime acceptance. Prioritize checks for the changed capability and its actual consumer path, using the repository's authoritative classification and failing closed on ambiguity.

Where the execution platform supports dependency scheduling, prefer scheduling dependent consumers after their producer to occupying consumer workers solely to poll for producer completion. Preserve independent concurrency; do not introduce a serial producer barrier solely for computation reuse when its cost worsens the critical path. Artifact scheduling must retain all applicable identity, provenance, integrity, and required-check guarantees.

Treat **stage**, **applicability**, and **result** as separate dimensions. Passing CI preflight does not establish core, integration, full-qualification, merge-readiness, or release evidence. Passing an earlier stage must not substitute for an applicable later-stage verification. A classified `not-applicable` decision is applicability evidence rather than a passing result, and uncertain applicability must fail closed under the repository's exact-head CI policy. Staging must not suppress repository-required automatic checks contrary to the workflow or policy that owns those checks.

During dependency-safe construction, treat the revision as a **construction candidate**—a development-time or stacked intermediate revision for which full exact-head qualification is not required. Intermediate heads do not each require full qualification. Use CI preflight, core validation, focused diagnostics, and applicable conditional integration to falsify defects early and confirm development continuity without turning every intermediate construction head into a final qualification identity. Passing CI preflight or core validation (L0/L1) establishes only that construction may proceed; it does not constitute merge-readiness or release evidence (L0/L1 green ≠ merge-ready), and L1/L2 evidence must never substitute for required L3 full qualification. Do not stall dependency-safe construction or stacked progression solely to wait for expensive CI on an intermediate construction candidate.

When an authority-defined revision-bound boundary is reached—such as pull-request merge, release, publication, deployment, or final whole-stack review—treat the stabilized revision as a **qualification candidate**. Stabilize the qualification head (or stacked tip) and acquire every applicable verification required by that authority, including full qualification when that boundary requires it. If the qualification candidate's effective state or an evidence binding changes, the affected prior evidence becomes stale and cannot qualify the successor state. A head-SHA-only change makes **exact-revision-bound** and unclassified/unknown evidence stale, but does not automatically invalidate explicitly **tree-and-context-bound** qualification evidence when the effective candidate tree and every declared non-tree binding are positively re-established under the canonical qualification evidence reuse rules. This history-only exception applies only to CI/qualification evidence. Review evidence remains governed independently by exact-head review policy, so a proposed-head change makes prior exact-head review stale and requires a new completed review for the successor head before merge. Staged CI is an execution-efficiency discipline; it does not weaken exact-head evidence, independent review, release trust, provenance, publication, or other completion requirements.

For stacked descendants, apply `pull-request.defer-revision-bound-qualification-until-required` before intentionally launching or reacquiring expensive full qualification. Construction validation, repository-required automatic CI, and intentional final evidence acquisition are distinct: automatic execution neither freezes a provisional descendant nor proves final qualification. Advance qualification only when the applicable boundary and prerequisite/evidence bindings support it, including the canonical immediate-boundary, safety, usefulness, and critical-path cases. Do not serialize dependency-safe implementation behind ancestor CI or review, and do not repeatedly qualify a descendant while a known prerequisite mutation is expected to stale that evidence.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/staged-ci-and-preflight.md`; rule ID: `pull-request.use-staged-ci-with-preflight`; severity: `mandatory`._


## Require exact-head CI evidence before merge

Before declaring a pull request merge-ready or merging it, identify the checks that are applicable to the current proposed head from the current repository workflow and validation definitions, identify the binding class owned by each relied-upon result, and rely only on CI or validation evidence that applies to that exact head commit under its declared binding contract. **exact-revision-bound** evidence must apply to the exact head commit represented by the current proposed head (or the current provider-required merge-result identity). **Tree-and-context-bound** qualification evidence may apply to that current exact head after a head change only when its validation contract or evidence record explicitly declares that binding class and qualification applicability evaluation positively establishes that the effective candidate tree and every required non-tree binding remain unchanged. A successful result for an older head is historical evidence and must not satisfy the current merge gate unless those reuse conditions are established. An ordinary CI success with no explicit binding classification is **unknown**, not implicitly tree-bound, and must be reacquired after head movement.

The binding classification is part of qualification evidence, not an inference from the apparent source diff. A validation result is tree-and-context-bound only when its contract or evidence record binds the result to the effective tree plus all inputs that can affect its validity, such as generated/materialized state, dependencies and lockfiles, toolchain, validation environment, workflow definition, provider/cross-authority revisions, and repository required-check policy. If any required binding or the binding class itself cannot be established, fail closed rather than treating tree identity as sufficient.

When the repository uses staged CI, the stage taxonomy does not reduce this requirement. Passing CI preflight, core validation, or another earlier stage must not substitute for an applicable later-stage verification. Qualification for the current proposed head consists of every check that current repository authority requires and establishes as applicable at that boundary, including conditional integration and full qualification when required.

Treat check applicability as evidence with its own bindings. When a repository uses a classifier, dependency map, changed-surface rule, or equivalent mechanism to decide whether a verification applies, bind that decision to the exact relevant revision, comparison base or other declared input, classifier definition, and verification definition that produced it. A not-applicable decision is valid only when those bindings establish that the verification cannot be affected by the proposed change under current repository authority. **Not-applicable is applicability evidence, not a passing check result.**

An applicability classifier governing selective or staged verification must satisfy the canonical **classifier contract**:
- **Base-authoritative**: The classifier logic must resolve from the authoritative base revision (or an immutable authority) rather than proposed code, so proposed changes cannot alter their own classification rules. Where workflow dispatch wrappers execute from mutable pull-request candidates, classification and qualification must invoke from an immutable or base-owned control boundary (such as a protected reusable workflow, base-branch dispatch, or independent required check) or fail closed to full qualification if workflow control definitions are mutated.
- **Deterministic and path-based**: Decisions must be computed deterministically from exact repository-relative changed paths between the base and proposed candidate.
- **Fail-closed on ambiguity or error**: Unrecognized paths, empty or malformed diffs, missing base references, or unparseable inputs must fail closed to conservative or full verification.
- **Prohibition of self-exemption**: Changes to the classifier script, classification fixtures, or CI workflow definitions must never self-exempt from verification and must require conservative or full qualification.
- **Explicit escalation**: The workflow must provide an explicit escalation path or explicit full-verification override (such as a pull-request label or manual dispatch) to force full verification for a qualification checkpoint.

Policy defines the semantic properties and standard risk classes (`documentation-only`, `tests-only`, `content`, `runtime-sensitive`, `browser-sensitive`, `publication-sensitive`, `cross-authority-sensitive`, `distribution-sensitive`, `ci-authority-sensitive`, `unknown`) of this contract; the individual repository remains authoritative for its concrete path-to-class mappings.

Selective applicability must not weaken required verification. Do not use applicability classification to substitute focused diagnostic validation for required qualification or to infer that a skipped or unobserved expected check passed. Applicability classification must not suppress repository-required automatic checks contrary to the repository workflow or policy that owns those checks. A repository may itself define conditional automatic execution when the applicability decision is fail-closed and auditable.

Do not treat an expected but not yet observable check as successful, non-applicable, or absent merely because one live query returns no result. Until applicable exact-head checks have been positively identified or their non-applicability is established by current repository policy, keep merge authorization fail-closed.

If a newer applicable exact-head run supersedes an older cancelled or stale run, evaluate the newest applicable evidence rather than treating the superseded run by itself as the current result. Reuse a previously established not-applicable decision only while every fact that binds that applicability evidence remains unchanged; otherwise reclassify only the affected verification scope.

When a provider supports retries, bind observations to the run identity and attempt as well as the applicable revision. Inspect the actual job and step identities, statuses, and conclusions needed for the decision. A later step's position or an aggregate result does not establish another step's success; skipped, pending, and successful are distinct. Do not silently combine an older attempt's success with a newer attempt. Retained successful jobs may contribute only when the provider's retry contract and the evidence bindings establish their continued applicability. Diagnose the root failing job and step before selecting a repair or the smallest valid retry scope, including required dependent gates.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/exact-head-ci-evidence.md`; rule ID: `pull-request.require-exact-head-ci-evidence`; severity: `mandatory`._


## Fail closed while expected CI evidence is unresolved

When current repository definitions make an exact-head check expected but live evidence for that check is not yet observable, treat the situation as unresolved discovery rather than as success, failure, or confirmed absence. Continue read-only discovery while the proposed head and applicability conditions remain unchanged.

Do not classify an expected check as absent from a single empty query, repeated queries against only one live index, or elapsed time alone. A confirmed-absence decision requires corroborating current evidence sufficient to distinguish delayed indexing or execution from a check that did not materialize.

Once applicable exact-head checks have been positively identified and acceptable evidence has been recorded, do not re-enter discovery merely for conservatism while the proposed head and the conditions that determine check applicability remain unchanged. Re-enter discovery only when a concrete invalidation signal makes the prior discovery conclusion inapplicable or uncertain.

Do not mutate the pull request or proposed head solely to manufacture new CI evidence while discovery remains unresolved. If uncertainty remains, keep merge authorization blocked rather than inferring success or non-applicability.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/ci-discovery-fail-closed.md`; rule ID: `pull-request.fail-closed-on-unresolved-ci-discovery`; severity: `mandatory`._


## Reuse valid pull-request evidence until an applicable binding changes

Once scope, validation, review, or other acceptance evidence has been accepted for a defined proposed-head identity and applicability context, reuse that evidence while the facts that bind it remain unchanged.

Do not make repeated observations, extra review cycles, waiting periods, or redundant evidence collection mandatory solely because they are more conservative. Additional diagnostic work may be performed when concrete uncertainty exists, but it must not silently enlarge the acceptance baseline or become a new merge requirement unless current repository policy requires it.

Reacquire only the evidence affected by a concrete invalidation signal. Target-branch movement requires impact evaluation, but it does not by itself invalidate unrelated exact-head evidence whose applicability and semantic basis remain unchanged. Changes to scope, validation definitions, review state, or another evidence-binding condition invalidate the corresponding evidence. Elapsed time alone does not invalidate exact-head evidence unless current repository policy defines an explicit freshness limit.

During stacked pull-request progression and candidate landing, **merge progression does not itself invalidate qualification evidence. A change to the qualified candidate state or to an evidence binding does.** Merely because an ancestor member of a stack was merged, subsequent members' CI or qualification evidence must not be treated as stale solely for that reason. Before scheduling or executing new validation, perform an explicit **qualification applicability check** comparing the qualification candidate, current head, effective tree identity, base evolution, validation-run bound identity, exact-head and exact-tree bindings, provider revision, cross-authority revision, generated or materialized state, dependency, lockfile, and toolchain identity, validation workflow identity, and repository required-check policy.

An applicability check must distinguish at least three outcomes: **applicable**, **stale**, and **unknown**. If applicability is unknown or cannot be positively verified, keep evaluation fail-closed and treat the evidence as requiring reacquisition; unknown must never be treated as applicable.

Qualification evidence binding classification must be explicit and auditable. Treat evidence as **tree-and-context-bound** only when the validation contract or evidence record identifies the effective candidate tree and every non-tree binding required for that result, including relevant generated/materialized state, dependency/lockfile/toolchain identity, validation environment, workflow definition, provider or cross-authority revision, and required-check policy. Treat evidence as **exact-revision-bound** when its contract, provider semantics, or evidence record requires an exact commit/head or merge-result identity. If the binding class or any required binding cannot be established, applicability is **unknown** and the evidence must be reacquired. An ordinary successful CI result is never inferred to be tree-and-context-bound merely because the source tree appears identical.

Existing qualification evidence may be reused when:
- the effective candidate tree is identical;
- no conflict resolution occurred;
- generated or materialized output is unchanged;
- dependency, lockfile, and toolchain identities are unchanged;
- the validation environment identity is unchanged;
- the validation workflow identity is unchanged;
- provider and cross-authority revisions are unchanged;
- exact-head, exact-tree, and all other bindings required by the evidence continue to hold; and
- repository hosting provider rulesets, branch protection, or required merge-result policies do not mandate a fresh check.

Qualification evidence is stale and must be reacquired upon concrete invalidation:
- conflict resolution;
- effective tree change;
- generated or materialized output change;
- dependency, lockfile, or toolchain change;
- validation environment change;
- validation workflow change;
- provider revision change;
- cross-authority revision change;
- breach or destruction of an exact-head, exact-tree, or immutable binding; or
- change in qualification input.

History-only evolution—such as ancestor pull-request landing, history-only rebase, tree-identical head movement, or commit-graph reorganization—does not automatically invalidate qualification evidence solely because the commit SHA changed. However, when evidence is exact-revision-bound—for example, to an exact commit SHA or provider-required merge-result identity—that binding semantics must be respected; an identical tree alone does not waive explicit exact-commit or merge-result bindings. Tree-and-context-bound evidence may survive a history-only head change only after all declared bindings are positively re-established for the successor candidate.

When evidence becomes stale, running the full validation or CI suite is not the default. Selective invalidation requires identifying the affected validation or binding and rerun only what is required to restore qualification.

Reuse of qualification or CI evidence does not by itself imply reuse of review evidence. Review applicability continues to follow the repository's existing review policy, and merge-acceptance review requirements remain governed by their applicable review contract.

If the continued validity of relied-upon evidence cannot be established, fail closed and reacquire the affected evidence rather than inventing a broader gate.

For local stage reuse, the same commit SHA alone is insufficient. Bind evidence to the effective source inputs, including relevant dirty, untracked, or ignored inputs actually consumed; validator/build definitions; dependency locks; runtime; provider revisions; artifact integrity; and result format and stage meaning. Re-establish these bindings through use, including after waiting for a lock or another process. Isolate stage-generated mutation from a reusable source snapshot so an earlier stage cannot silently change a later stage's inputs. Incomplete, interrupted, stale, or mismatched stage evidence must not become a reuse hit. Local reuse remains local evidence and cannot authorize skipping remote qualification. Keep disposable runtime caches off implementation and qualification branches; the existing Work-ledger storage rules continue to govern operational checkpoints separately.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/reuse-valid-evidence.md`; rule ID: `pull-request.reuse-valid-exact-head-evidence`; severity: `mandatory`._


## Require current mergeability before merge

Immediately before merge authorization, verify from current repository state that the pull request can be merged. Historical mergeability, conflict-free status observed for an older head, or an earlier successful dry run must not substitute for the current state.

If mergeability is unknown, false, or changes before the merge operation completes, keep or return merge authorization to a blocked state and refresh the relevant current evidence before attempting merge again.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/current-mergeability.md`; rule ID: `pull-request.require-current-mergeability`; severity: `mandatory`._


## Refresh mutable live state and validate evidence bindings before merge

Immediately before authorizing or executing a pull-request merge, refresh the mutable repository state that can invalidate the accepted snapshot, including the current proposed head, current target-branch head, current review state, unresolved review-thread state, and current mergeability. Validate that relied-upon scope, exact-head validation, and completed review evidence are still bound to the resulting current state.

Do not unconditionally reacquire exact-head validation, completed review, or scope evidence whose binding facts remain unchanged and whose continued validity is established by current policy. Re-evaluate only the acceptance evidence affected by a changed head, target branch, scope, validation definition, review state, thread state, mergeability state, or other concrete invalidation signal.

If a required current value is missing, stale, materially different, or cannot be reconciled to the accepted evidence, leave merge authorization blocked and reacquire the affected evidence.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/final-live-state-refresh.md`; rule ID: `pull-request.refresh-live-state-before-merge`; severity: `mandatory`._


## Guard merge against proposed-head movement

When executing a pull-request merge, bind the operation to the exact proposed head commit whose current acceptance evidence was approved, using the strongest supported immutable-head precondition available on the execution surface. The merge must not silently apply to a different head that appeared after final acceptance.

If the merge surface cannot enforce an immutable proposed-head precondition, treat that limitation as part of the final acceptance risk: refresh current state immediately before execution and verify the result afterward rather than assuming the earlier accepted snapshot is still current.

If the merge operation reports that the proposed head or repository state changed, do not retry blindly. Refresh current state and re-run the affected acceptance gates for the resulting proposed head before attempting merge again.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/immutable-head-guard.md`; rule ID: `pull-request.guard-merge-against-head-movement`; severity: `mandatory`._


## Verify the merge result after execution

After executing a pull-request merge, verify from current repository state that the pull request is actually merged, record the resulting merge identity, and confirm that the target branch contains the intended merged result or a later intentional successor.

Do not report merge completion solely because the merge operation returned without a transport error. If the observed repository state does not establish that the intended result was merged, report the merge outcome as unresolved or failed and investigate before claiming completion.

Treat any release, publication, deployment, or other post-merge readiness requirement as a separate acceptance boundary; successful merge verification does not by itself establish those later states.

_Source: `TakashiSasaki/templates@c5c01e0e59e217571991420f4dc884c3e58e73f3:policy/pull-request/post-merge-verification.md`; rule ID: `pull-request.verify-merge-result`; severity: `mandatory`._


## Preserve the policy-toolkit authority boundary

This branch is the development source for application-type-independent operating policy and its toolchain. Keep shared policy semantics in the shared `policy/` corpus and keep repository-maintainer rules in `repository-policy/`; do not place policy-repository maintenance requirements into the shared corpus merely because this repository consumes them.

Do not introduce Web application, Agent Skill, CLI-product, service, deployment-topology, surface, route, state, or other artifact-category architecture into the shared policy corpus. Artifact-specific contracts remain owned by their corresponding consumer branches or repositories.

_Source: `repository-policy/authority-boundary.md` in this repository; rule ID: `policy-repo.preserve-authority-boundary`; severity: `mandatory`._


## Preserve unrelated branch histories

The `policy`, `skill`, `site`, and `webapp` branches have unrelated histories. Do not merge, rebase, or cherry-pick across those branch histories to distribute policy. Consumers adopt reviewed shared policy through immutable full commit SHAs and generated projections instead.

_Source: `repository-policy/history-boundary.md` in this repository; rule ID: `policy-repo.preserve-history-boundary`; severity: `mandatory`._


## Require architecture decisions for trust-contract changes

Changes to the policy configuration schema, rule merge or override semantics, lock-file format, or bootstrap trust model require an architecture decision record before the dependent implementation is treated as complete. Keep the decision, implementation, tests, and maintained documentation synchronized.

_Source: `repository-policy/architecture-decisions.md` in this repository; rule ID: `policy-repo.require-architecture-decisions`; severity: `mandatory`._


## Preserve the immutable release trust model

Keep `release/toolchain.json` and `skills/agent-policy/runtime-manifest.json` synchronized to the same reviewed full toolchain commit SHA. Require the runtime manifest to bind that stable revision's `requirements-runtime.lock` by SHA-256. Never replace an executable identity with a mutable branch or tag.

Stable runtime movement uses a frozen reviewed candidate followed by a separate promotion change that records the candidate SHA and matching runtime-lock digest. Do not attempt self-referential promotion in which a commit must contain its own SHA. Update verifier dependencies only when the promoted candidate actually requires a different probe environment.

Keep `release/skill-installer.json` synchronized with the separately reviewed full-SHA installer script and the full-SHA `skills/agent-policy` source revision embedded by that installer. Publish remote installation commands only with the descriptor's full installer revision, never with `policy`, a tag, a short SHA, or another mutable reference. Installer publication likewise uses a reviewed candidate followed by a later promotion change so the published command never requires a commit to contain its own SHA.

Treat `release/skill-installer.json` and repository-level documentation that intentionally publishes the remote installer command as the installer-publication surface. The installed `skills/agent-policy/README.md` is a distributed consumer artifact, not an installer-publication authority; it must not embed a specific installer-script revision or skill-source revision because those identities may be superseded by a later promotion. It may describe the immutable-installation contract and direct readers to the release descriptor and current repository-level installation documentation.

_Source: `repository-policy/release-trust.md` in this repository; rule ID: `policy-repo.preserve-release-trust-model`; severity: `mandatory`._


## Preserve policy-toolchain safety boundaries

For policy-toolchain implementation paths that read or write a target repository, resolve paths against the repository root and reject escape through absolute paths, parent traversal, `.git`, or symbolic links. Do not silently overwrite repository files unless the tool can establish that the file is its own generated output.

Generated bootstrap material must never authorize execution through a mutable Git reference. Security-sensitive changes must preserve these boundaries in both positive and negative-path tests.

_Source: `repository-policy/toolchain-safety.md` in this repository; rule ID: `policy-repo.preserve-toolchain-safety-boundaries`; severity: `mandatory`._


## Run the policy-toolkit maintainer validation baseline

For changes to the policy toolchain, run the repository's locked Policy CI-equivalent validation appropriate to the changed surface, including release-state verification, lint, tests, compilation, and command smoke tests. At minimum, do not report a source change complete without `python -m pytest` and `python -m compileall -q src scripts skills/agent-policy/scripts` succeeding in a compatible validated environment.

Treat the exact GitHub Actions `Policy CI`, `Policy documentation build`, and, when runtime behavior changes, `Policy runtime distribution` results for the current head as separate remote evidence. Do not substitute a generated-policy `check` for the toolchain's own implementation and documentation test suites.

_Source: `repository-policy/maintainer-validation.md` in this repository; rule ID: `policy-repo.run-maintainer-validation`; severity: `mandatory`._


## Keep policy documentation build-only

The `policy` branch may validate and build its documentation but must not upload a GitHub Pages artifact, request Pages write authority, or deploy the site. Repository-site assembly and deployment belong to the unrelated `site` branch. Keep policy documentation workflows read-only except for permissions independently required by a reviewed maintenance task.

_Source: `repository-policy/documentation-boundary.md` in this repository; rule ID: `policy-repo.preserve-documentation-deployment-boundary`; severity: `mandatory`._


## Maintainer merge routing

This is the short discovery route for agents maintaining the `policy`
authority of `TakashiSasaki/templates`. It is not a product-repository
adoption instruction and it does not duplicate the landing rules.

Read the maintenance rule and its execution procedure from the same immutable
source snapshot before changing a maintenance PR:

- repository: `TakashiSasaki/templates`;
- revision: `04bf86977675bfc8f1082b8b8d6c70817f4eb9c2`;
- rule: `repository-policy/stacked-pr-landing.md`, blob
  `9761cdbcd21b0e8ba2f3eb2ffb306725a82f5eef`;
- landing Skill: `repository-skills/land-templates-stack/SKILL.md`, blob
  `06efa38681e374636bcabcbcb984be5ec43b47ee`;
- review scope planner: `repository-skills/land-templates-stack/scripts/plan_review_scope.py`, blob
  `16c0907a19e3f8d339fe81e29f7b204e791fc781`.

The Policy authority also exposes the thin local entry at
`.agents/skills/land-templates-stack/SKILL.md`; validate its adjacent
`source.json` before loading this procedure.

The Policy authority also exposes the thin local entry at
`.agents/skills/pr-merge-gate/SKILL.md`; validate its separate adjacent
`source.json` before loading the shared acceptance gate.

Resolve both paths with the declared revision and verify their blob identities;
do not read a same-named file from the consumer worktree, `policy` branch, or
an unverified local copy. If an object, path, SHA, or blob does not match,
stop as blocked.

The shared individual-PR acceptance gate is a separate immutable source,
even when stored in the same candidate commit:
`TakashiSasaki/templates@94eb84397d913f2ebb0e2c79d0b841ae580fbc31`,
`skills/pr-merge-gate/SKILL.md`, blob
`2ef890673600f0f4c30b53cef7c19a78d34cf5bc`. The Policy generation toolchain
pin remains separate at
`TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7`.

The route applies to a single PR and to a same-authority stack. Use the
canonical landing Skill to order members and invoke the shared gate; do not
merge, auto-merge, publish, deploy, or treat review and CI as interchangeable
evidence without the required human authorization boundary.

_Source: `repository-policy/maintainer-merge-routing.md` in this repository; rule ID: `policy-repo.maintainer-merge-routing`; severity: `mandatory`._




