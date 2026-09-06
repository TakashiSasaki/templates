<!--
agent-policy-generated: true
configuration: .agent-policy.yml
DO NOT EDIT DIRECTLY
-->

# Repository agent instructions

These instructions were generated from shared policy profiles and repository-specific policy files.

## Policy system

- Semantic configuration: `.agent-policy.yml`
- Pinned shared toolchain: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7`
- Repository policy inputs:
  - `policy/project.md`

Do not edit this generated file directly. Change `.agent-policy.yml` or its repository policy inputs, then regenerate with the pinned toolchain. Before editing repository files, inspect any repository-local skill catalog that exists and read the relevant generated or handwritten skills.


## Define the change contract before editing

Before editing, identify the requested outcome, the allowed change surface, the existing behavior and invariants that must be preserved, explicit non-goals, and the evidence required for acceptance. Treat unspecified behavior as preserved unless the requested change necessarily alters it; do not silently broaden the contract to resolve ambiguity or implementation difficulty.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/core/change-contract.md`; rule ID: `changes.define-contract`; severity: `mandatory`._


## Preserve the agreed acceptance baseline

Once implementation or audit begins against an agreed change contract, do not retroactively expand its scope, non-goals, completion criteria, required evidence, or stop condition. Rebaseline only with explicit authorization, and record the impact on completed work and prior evidence.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/core/acceptance-baseline.md`; rule ID: `changes.preserve-acceptance-baseline`; severity: `mandatory`._


## Keep changes within the requested scope

Do not modify files, behavior, dependencies, formatting, or architecture that are unrelated to the requested change. Inspect the final diff and remove incidental changes before reporting completion.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/core/change-scope.md`; rule ID: `changes.minimize-scope`; severity: `mandatory`._


## Escalate material semantic ambiguity

When an unresolved choice would materially affect observable behavior, data meaning, compatibility, architecture, risk, or scope, do not guess. Present the viable options, trade-offs, impact, and a recommendation, and obtain an explicit decision before making the dependent change.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/core/semantic-decision-gates.md`; rule ID: `decisions.escalate-semantic-ambiguity`; severity: `mandatory`._


## Do not weaken existing tests

Do not delete, skip, narrow, or relax an existing test merely to make a change pass. For a bug fix, add a regression test that fails before the fix and passes afterward whenever the failure can be reproduced deterministically.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/core/regression-safety.md`; rule ID: `regression.no-weaken-tests`; severity: `mandatory`._


## Run the repository's required verification

Use the verification command declared by the repository and add focused checks needed for the changed behavior or failure mode. Confirm that the executed checks cover the changed surface and the current revision; a check that is pending, skipped, not triggered, stale, blocked, or merely inspected is not a passing result. Report every required check that was not run or did not pass.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/core/testing.md`; rule ID: `testing.run-required-checks`; severity: `mandatory`._


## Test material invariants beyond the nominal path

When a change relies on a structured contract, mutable lifecycle, asynchronous completion, relation set, identity mapping, generated projection, resource boundary, or effective containment boundary, identify the material invariants that make the changed behavior correct and add focused adversarial coverage for the applicable negative, transition, stale-state, malformed-input, converse/completeness, or boundary cases.

Derive the cases from the changed invariant rather than from a fixed universal matrix. Do not require unrelated combinations, speculative stress cases, or exhaustive permutations when they do not exercise a material failure mode. A focused test may be unit-, integration-, system-, or workflow-level as long as it reaches the layer where the invariant can actually fail.

When a defect or review finding proves that one dimension of an invariant was previously unguarded, inspect the bounded sibling dimensions that share the same root cause before declaring the repair complete. Examples include success versus failure completion, current versus stale context, listed relation versus required converse, missing versus extra structured fields, and nominal outer bound versus effective inner containment boundary. Add regression evidence for sibling cases that are materially reachable; do not broaden the change into unrelated cleanup.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/core/adversarial-invariant-testing.md`; rule ID: `testing.require-adversarial-invariant-coverage`; severity: `mandatory`._


## Keep verification evidence bound to its layer

Bind every verification result to the exact revision or artifact and to its evidence layer. Report repository-local checks, environment-dependent checks, remote CI, and independent audit separately; success in one layer does not prove success in another.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/core/evidence-layers.md`; rule ID: `verification.separate-evidence-layers`; severity: `mandatory`._


## Keep derived artifacts synchronized

When a change affects generated, mirrored, compiled, or otherwise derived artifacts, update them from their declared source of truth using the repository's documented process and verify that no stale or missing output remains. Do not hand-edit generated artifacts unless the repository explicitly designates that operation as authoritative.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/core/generated-artifacts.md`; rule ID: `consistency.synchronize-derived-artifacts`; severity: `mandatory`._


## Preserve externally observable contracts

Do not break public APIs, serialized data, configuration formats, command-line interfaces, or migration paths unless the requested change explicitly authorizes the incompatibility and documents its consequences.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/core/compatibility.md`; rule ID: `compatibility.preserve-contracts`; severity: `mandatory`._


## Revalidate destructive actions against current state

Immediately before deleting, overwriting, migrating, deploying, publishing, force-updating, or otherwise making an irreversible or externally visible change, re-read the target's current state and revalidate its identity, scope, version or revision, protections, and conflicting uses. Prefer dry-run, least-scope, and idempotent operations; do not authorize the action solely from stale observations made earlier in the task.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/core/destructive-actions.md`; rule ID: `safety.revalidate-destructive-actions`; severity: `mandatory`._


## Bind validated state to the effective operation

When correctness or safety depends on a validated or authorized target identity, scope, or other mutable precondition, ensure that the same effective target and required preconditions remain bound to the operation through use. Account for normalization, indirection, aliases, redirects, rebinding, and concurrent mutation; use stable identity or protected state, an atomic, transactional, or serialized mechanism, or revalidation at a protected commit or use boundary as appropriate. Fail closed if the operation can proceed against a different effective target or after the condition that authorized or validated it has become stale.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/core/validation-operation-binding.md`; rule ID: `safety.bind-validated-state-to-operation`; severity: `mandatory`._


## Limit rollback to changes owned by the operation

For a multi-step mutation, complete preflight before the first write, revalidate the live state at the commit boundary, and track which paths the current operation created or changed. On failure, roll back only those owned changes; never delete or overwrite pre-existing or concurrently created state as cleanup unless explicitly authorized.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/core/transaction-ownership.md`; rule ID: `safety.limit-rollback-to-owned-changes`; severity: `mandatory`._


## Report actual state and residual uncertainty

Distinguish implemented, generated, executed, verified, and merely inferred results. State unresolved failures and unverified assumptions explicitly.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/core/truthful-reporting.md`; rule ID: `reporting.truthful-status`; severity: `mandatory`._


## Separate task completion from review and merge authorization

Repository-change work must distinguish implementation task completion, validation completion, independent review, review completion, merge authorization, and the merged result. Completing implementation or validation does not establish that review was requested, review was completed, or merge authorization exists. Progression controls construction ordering; completion controls the agent's stopping boundary. A progression strategy must not by itself force review acquisition or merge completion.

A repository-change task may declare human-handoff as its completion boundary. Human handoff is valid completion when the agent has completed the authorized implementation and validation work, reports the independent-review state truthfully, reports merge authorization as not established, and leaves every pull request open and unmerged. When no applicable pre-existing review evidence establishes another state, report independent review as not requested or outstanding. When applicable pre-existing review evidence already establishes completed review, preserve and report that REVIEW_COMPLETE state rather than downgrading it merely because human-handoff was selected. When human-handoff is selected, the agent must not initiate a new merge-acceptance review request through reviewer assignment, provider invocation, requested-reviewer state, or any other review-request mechanism by default. An explicit task instruction may authorize one final whole-stack architecture/dependency/completeness audit after the stack is stable enough for handoff. That audit is diagnostic, is not ordinary per-member merge-acceptance evidence, does not authorize merge, does not waive future exact-head review requirements, must not create a review-retry loop, and need not complete before handoff unless explicitly required. Existing review evidence may be observed, inspected, and reported, but handoff does not acquire new acceptance evidence.

Human handoff is not a review waiver, does not remove acceptance requirements for a later review or merge, and does not authorize a merge. Reports must not label a handoff review complete unless applicable pre-existing review evidence establishes that state, and must not label the handoff merge ready or merged. Use explicit state labels such as IMPLEMENTATION_COMPLETE, VALIDATION_COMPLETE, REVIEW_NOT_REQUESTED, REVIEW_PENDING, REVIEW_COMPLETE, HANDOFF_READY, MERGE_READY, and MERGED only when the corresponding state is established.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/core/repository-change-completion.md`; rule ID: `changes.separate-task-review-merge-state`; severity: `mandatory`._


## Do not expose or commit secrets

Do not print, persist, or commit credentials, private keys, access tokens, session material, or unredacted sensitive configuration. Use established secret-management mechanisms.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/security/secrets.md`; rule ID: `security.no-secrets`; severity: `mandatory`._


## Validate data at trust boundaries

Validate untrusted input before it reaches privileged operations, persistence, command execution, or external requests. Preserve existing authentication and authorization checks.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/security/input-validation.md`; rule ID: `security.validate-boundaries`; severity: `mandatory`._


## Bind cumulative review evidence to an ordered pull-request stack

The ordinary merge-acceptance path for a stacked pull-request member is a completed independent review bound to that member's exact current head. A whole-stack architecture, dependency, or completeness audit is useful diagnostic evidence but is not merge-acceptance evidence for lower members unless it also satisfies every cumulative binding below. Cumulative multi-member acceptance review is optional; stacked progression does not require it.

When a completed review is claimed to cover multiple members of a stacked pull-request topology, acceptance evidence must bind to the integration base exact SHA and tree, the ordered stack membership, each member exact head SHA, the stack tip exact SHA, the cumulative reviewed scope, the review contract, reviewer independence, the review completion state, and material limitations.

A review event, approval state, or tip-only review must not infer lower stack coverage or establish acceptance coverage for lower stack members by inference. Each covered member must be identifiable from explicit cumulative coverage evidence. Missing, ambiguous, or provider-only coverage is incomplete evidence and keeps merge authorization fail-closed.

If a provider cannot clearly attest one or more lower-member cumulative bindings, stop treating that review as cumulative merge evidence. Preserve any valid whole-stack audit findings, then use the ordinary individual exact-head review path for uncovered members when acceptance review is authorized. Do not repeatedly request cumulative clarification or reacquire cumulative review merely to recover an optimization that is not required for stacked progression.

Evaluate applicability again when a member exact head changes, stack ordering changes, integration base changes, cumulative scope changes, or the review contract changes. Reuse unchanged evidence only when its bindings and remaining stack applicability are established; if applicability is unknown, fail closed. A lower member merge may move a later member's base without mechanically invalidating all evidence or requiring an upper-head rewrite solely for base movement, but the changed bindings and remaining coverage must be evaluated before relying on it.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/pull-request/stacked-review-coverage.md`; rule ID: `pull-request.require-explicit-stacked-review-coverage`; severity: `mandatory`._


## Defer revision-bound qualification until an authority boundary requires it

A pull-request head or stacked-member commit that exists during dependency-safe construction is a **construction head**: an exact Git identity for the current work state, not automatically a final qualification identity. A **provisional candidate** is a construction state that may continue to change because authorized implementation, upstream dependency work, finding disposition, or other justified mutation is still in progress. A **qualification head** is an intended candidate revision deliberately frozen so required acceptance evidence can bind to that exact revision. A **publication identity** is an immutable revision, digest, artifact, or equivalent identity made authoritative for provenance, release, publication, distribution, or another external consumer boundary.

Until an applicable repository authority or explicit task boundary requires revision-bound acceptance, independent review, provenance, release, publication, merge, or another immutable binding, do not intentionally freeze a provisional candidate solely to acquire final revision-bound evidence or materialize a downstream immutable identity that is expected to follow still-mutable prerequisites. The mere existence of a commit SHA, branch head, or pull request does not by itself establish that the candidate has entered final qualification.

Continue authorized implementation, focused diagnostic validation, pull-request creation, dependency-safe downstream work, and naturally triggered CI while a candidate remains provisional. Do not treat those activities, or an observed successful run on a provisional head, as proof that final qualification has been completed. Do not use this rule to suppress repository-required automatic checks or to substitute focused diagnostics for qualification once an applicable boundary requires it.

When a revision-bound boundary is reached, stabilize the actual prerequisite identities, freeze the intended candidate revision or ordered candidate revisions, and acquire every exact-revision evidence item required by the applicable authority. When provenance, publication, release, generated projection, signed material, or another downstream artifact embeds an upstream exact revision or digest as part of its authoritative meaning, perform that final immutable materialization only after the prerequisite identity is stable enough to bind. If a later justified mutation changes an evidence binding, invalidate and reacquire only the affected revision-bound evidence as required by the applicable evidence rules.

This deferral is an execution-efficiency discipline, not an acceptance waiver. It must not delay an urgent security, operational, data-integrity, or publication-integrity repair, and it must not weaken exact-head CI, independent exact-head review, immutable-head merge protection, release trust, provenance, publication, or other authority-defined completion requirements.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/pull-request/defer-revision-bound-qualification.md`; rule ID: `pull-request.defer-revision-bound-qualification-until-required`; severity: `mandatory`._


## Evaluate merge readiness against the current target branch HEAD

Before declaring a pull request merge-ready, establish the current target branch full commit SHA and evaluate the proposed change against that exact target state. If the proposed head is not based on the current target head, inspect the intervening target change and determine whether it affects scope, validation applicability, review conclusions, mergeability, or another acceptance condition.

Synchronize or rebuild the proposed head only when that impact evaluation or current repository policy requires it. Do not require proposed-head synchronization solely because the target branch moved when the intervening change is established not to invalidate the applicable acceptance evidence.

Target-branch movement invalidates the freshness decision itself, but it does not by itself invalidate unrelated exact-head CI or review evidence. Do not claim target-branch freshness from cached, historical, or inferred branch metadata.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/pull-request/target-branch-head-freshness.md`; rule ID: `pull-request.verify-target-branch-head-freshness`; severity: `mandatory`._


## Preflight revision-bound review acquisition

Before intentionally requesting an independent review that is expected to cover a named pull-request head, commit, branch ref, or stacked set of revisions, refresh the live identity facts needed to construct that request and verify that every revision binding the request depends on is currently resolvable.

For a single pull request, verify that the intended reviewed commit is the current proposed head and that any branch or ref supplied to the review provider still resolves to that commit. For cumulative or whole-stack review, also verify the ordered stack membership and every explicitly bound integration-base, member-head, and tip identity needed by the review contract. If a required identity is missing, stale, moved, ambiguous, or no longer matches the intended candidate, do not invoke the reviewer with that binding; refresh the affected state and construct a corrected request first.

This preflight protects review acquisition from avoidable transport and identity failures. It is not completed-review evidence, does not establish merge readiness, does not weaken exact-head review requirements, and must not become a fixed waiting period or an excuse to re-read unrelated state. Naturally delayed provider execution can still fail after a correct preflight; report such provider failure separately from substantive review completion.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/pull-request/review-acquisition-preflight.md`; rule ID: `pull-request.preflight-review-acquisition`; severity: `mandatory`._


## Disposition known findings before review reacquisition

Before intentionally starting a new merge-acceptance review acquisition cycle for a proposed candidate, account for every material actionable finding already known from submitted review evidence and applicable to that candidate. For each such finding, establish either a repair validated for the current proposed head or an evidence-backed no-change disposition validated against the current proposed head and applicable authority, and record enough finding-level closure evidence on an auditable review or pull-request surface to distinguish that finding from unresolved or deferred material findings. Do not intentionally request another merge-acceptance review merely to accumulate more findings while a known material actionable finding lacks either the required current-head validated outcome or the required closure evidence.

Apply this requirement independently of provider representation. A finding in a resolvable thread, a top-level review body, a summary, or another non-resolvable review surface remains subject to the same disposition and closure-evidence requirement when it is independently actionable. Provider thread resolution is bookkeeping and does not itself establish semantic closure. Closure evidence records the validated disposition for auditability; the provider surface or resolved UI state does not redefine the semantic outcome.

Treat reviewer text as a defect hypothesis rather than authority. A finding first reported against an older head may be re-evaluated against the current proposed head; if current evidence falsifies it, record the decisive no-change disposition and the required closure evidence instead of making an appeasement edit. Do not force an unrelated suggestion into the current pull-request scope solely to clear the reacquisition gate.

This rule governs intentional acquisition of a new merge-acceptance review cycle. It does not require delaying an urgent operational, security, or data-integrity repair in order to batch review work; does not prohibit naturally triggered CI or review-provider behavior; and does not require waiting for hypothetical future findings. When an explicit human-handoff procedure authorizes one final diagnostic whole-stack audit, perform it only after known material findings have received the validated dispositions and recorded closure evidence required above. Such a diagnostic audit remains distinct from merge-acceptance evidence and does not satisfy or waive the independent exact-head review requirements for later merge authorization.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/pull-request/review-reacquisition-after-disposition.md`; rule ID: `pull-request.disposition-known-findings-before-review-reacquisition`; severity: `mandatory`._


## Require an independent exact-head review before merge

Before merging a pull request, require at least one completed review from an independent reviewer or review system for the exact proposed head commit. A review request, pending review, absence of review findings, or zero completed reviews is not review evidence and must block merge. The agent or actor that implemented the proposed change must not count its own self-review as the required independent review.

A submitted or provider-recorded review object is not by itself evidence that the review's required analysis completed. The relied-upon evidence must establish, under the applicable review procedure or review contract, that the required analysis completed for the exact proposed head. A review that reports itself as incomplete, partial, failed, or materially limited such that required analysis was not completed must not satisfy the independent-review requirement, even when a provider records that review as submitted or completed. If current evidence cannot establish whether the required analysis completed, keep merge authorization fail-closed rather than inferring completion from a provider event, review state, or the absence of blocking findings.

The relied-upon review evidence must identify the reviewed exact head through review metadata or an unambiguous completed review result. If the proposed head changes after that review, treat the review as stale and obtain a new completed review for the new exact head before merge.

If the required reviewer is unavailable or does not complete the review, report the pull request as blocked rather than waiving the requirement. Only an explicit repository policy may define an exception; an implementing agent must not invent or self-authorize one.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/pull-request/independent-exact-head-review.md`; rule ID: `pull-request.require-independent-exact-head-review`; severity: `mandatory`._


## Close review findings before merge

Before merging a pull request, inspect the current submitted reviews, resolvable review threads, and actionable findings for the exact proposed head. Treat each independently actionable finding as requiring its own repair or explicit disposition and validation, whether or not the provider exposes that finding as a resolvable thread.

When a resolvable thread exists, do not mark it resolved until the required repair or evidence-backed no-change disposition has been completed and validated for the current head. A code or documentation change by itself is not proof that the finding is resolved, and a provider's resolved UI state is bookkeeping rather than semantic proof of remediation.

When an actionable finding exists only in a top-level review body or another non-resolvable review surface, the absence of a thread does not mean the finding is resolved. Inspect it, repair it or record an explicit finding-level disposition, validate that outcome, and retain enough finding-level closure evidence to distinguish it from unresolved or deferred material findings.

Do not treat an unresolved material finding as complete merely by changing provider UI state. Do not merge while any material actionable finding lacks validated remediation or an explicit validated disposition, unless an explicit repository policy defines a documented exception. After that semantic closure is established, mark the corresponding provider thread resolved when such a thread exists and provider mechanics permit it.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/pull-request/review-thread-closure.md`; rule ID: `pull-request.close-review-threads-before-merge`; severity: `mandatory`._


## Require exact-head CI evidence before merge

Before declaring a pull request merge-ready or merging it, identify the checks that are applicable to the current proposed head from the current repository workflow and validation definitions. Rely only on CI or validation evidence that applies to that exact head commit. A successful result for an older head is historical evidence and must not satisfy the current merge gate.

Do not treat an expected but not yet observable check as successful, non-applicable, or absent merely because one live query returns no result. Until applicable exact-head checks have been positively identified or their non-applicability is established by current repository policy, keep merge authorization fail-closed.

If a newer applicable exact-head run supersedes an older cancelled or stale run, evaluate the newest applicable evidence rather than treating the superseded run by itself as the current result.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/pull-request/exact-head-ci-evidence.md`; rule ID: `pull-request.require-exact-head-ci-evidence`; severity: `mandatory`._


## Fail closed while expected CI evidence is unresolved

When current repository definitions make an exact-head check expected but live evidence for that check is not yet observable, treat the situation as unresolved discovery rather than as success, failure, or confirmed absence. Continue read-only discovery while the proposed head and applicability conditions remain unchanged.

Do not classify an expected check as absent from a single empty query, repeated queries against only one live index, or elapsed time alone. A confirmed-absence decision requires corroborating current evidence sufficient to distinguish delayed indexing or execution from a check that did not materialize.

Once applicable exact-head checks have been positively identified and acceptable evidence has been recorded, do not re-enter discovery merely for conservatism while the proposed head and the conditions that determine check applicability remain unchanged. Re-enter discovery only when a concrete invalidation signal makes the prior discovery conclusion inapplicable or uncertain.

Do not mutate the pull request or proposed head solely to manufacture new CI evidence while discovery remains unresolved. If uncertainty remains, keep merge authorization blocked rather than inferring success or non-applicability.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/pull-request/ci-discovery-fail-closed.md`; rule ID: `pull-request.fail-closed-on-unresolved-ci-discovery`; severity: `mandatory`._


## Reuse valid pull-request evidence until an applicable binding changes

Once scope, validation, review, or other acceptance evidence has been accepted for a defined proposed-head identity and applicability context, reuse that evidence while the facts that bind it remain unchanged.

Do not make repeated observations, extra review cycles, waiting periods, or redundant evidence collection mandatory solely because they are more conservative. Additional diagnostic work may be performed when concrete uncertainty exists, but it must not silently enlarge the acceptance baseline or become a new merge requirement unless current repository policy requires it.

Reacquire only the evidence affected by a concrete invalidation signal. A changed proposed head invalidates evidence bound to the former head. Target-branch movement requires impact evaluation, but it does not by itself invalidate unrelated exact-head evidence whose applicability and semantic basis remain unchanged. Changes to scope, validation definitions, review state, or another evidence-binding condition invalidate the corresponding evidence. Elapsed time alone does not invalidate exact-head evidence unless current repository policy defines an explicit freshness limit.

If the continued validity of relied-upon evidence cannot be established, fail closed and reacquire the affected evidence rather than inventing a broader gate.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/pull-request/reuse-valid-evidence.md`; rule ID: `pull-request.reuse-valid-exact-head-evidence`; severity: `mandatory`._


## Require current mergeability before merge

Immediately before merge authorization, verify from current repository state that the pull request can be merged. Historical mergeability, conflict-free status observed for an older head, or an earlier successful dry run must not substitute for the current state.

If mergeability is unknown, false, or changes before the merge operation completes, keep or return merge authorization to a blocked state and refresh the relevant current evidence before attempting merge again.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/pull-request/current-mergeability.md`; rule ID: `pull-request.require-current-mergeability`; severity: `mandatory`._


## Refresh mutable live state and validate evidence bindings before merge

Immediately before authorizing or executing a pull-request merge, refresh the mutable repository state that can invalidate the accepted snapshot, including the current proposed head, current target-branch head, current review state, unresolved review-thread state, and current mergeability. Validate that relied-upon scope, exact-head validation, and completed review evidence are still bound to the resulting current state.

Do not unconditionally reacquire exact-head validation, completed review, or scope evidence whose binding facts remain unchanged and whose continued validity is established by current policy. Re-evaluate only the acceptance evidence affected by a changed head, target branch, scope, validation definition, review state, thread state, mergeability state, or other concrete invalidation signal.

If a required current value is missing, stale, materially different, or cannot be reconciled to the accepted evidence, leave merge authorization blocked and reacquire the affected evidence.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/pull-request/final-live-state-refresh.md`; rule ID: `pull-request.refresh-live-state-before-merge`; severity: `mandatory`._


## Guard merge against proposed-head movement

When executing a pull-request merge, bind the operation to the exact proposed head commit whose current acceptance evidence was approved, using the strongest supported immutable-head precondition available on the execution surface. The merge must not silently apply to a different head that appeared after final acceptance.

If the merge surface cannot enforce an immutable proposed-head precondition, treat that limitation as part of the final acceptance risk: refresh current state immediately before execution and verify the result afterward rather than assuming the earlier accepted snapshot is still current.

If the merge operation reports that the proposed head or repository state changed, do not retry blindly. Refresh current state and re-run the affected acceptance gates for the resulting proposed head before attempting merge again.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/pull-request/immutable-head-guard.md`; rule ID: `pull-request.guard-merge-against-head-movement`; severity: `mandatory`._


## Verify the merge result after execution

After executing a pull-request merge, verify from current repository state that the pull request is actually merged, record the resulting merge identity, and confirm that the target branch contains the intended merged result or a later intentional successor.

Do not report merge completion solely because the merge operation returned without a transport error. If the observed repository state does not establish that the intended result was merged, report the merge outcome as unresolved or failed and investigate before claiming completion.

Treat any release, publication, deployment, or other post-merge readiness requirement as a separate acceptance boundary; successful merge verification does not by itself establish those later states.

_Source: `TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7:policy/pull-request/post-merge-verification.md`; rule ID: `pull-request.verify-merge-result`; severity: `mandatory`._


## Site maintenance authority

This repository is not production-critical; backward compatibility is not required. Preserve authority ownership, safe material management, and immutable provenance.

Composition governs the Website product; Policy governs repository maintenance. Their consumer configuration, locks, toolchains, and operations are independent. Site publication revisions in `publication-sources.json` are independent of both consumer relationships. Neither provider may mutate the other consumer state. Site integrates public provider contracts; it must not interpret private management metadata or add a shared management plane.

# Site-local procedural routing

The following routes select consumer-owned procedural Skills. Canonical norms remain in the selected Policy profiles and this project policy.

When working on the `site` authority, load the smallest matching skill from `.agents/skills/` before reconstructing a workflow from repository history.

## Skill routing

- Coordinated cross-authority document-set change that requires a Site staging PR before a provider publication PR: `PUBLICATION_STAGING.md` for the staging protocol, then `.agents/skills/site-publication-cutover/SKILL.md` for the final Site promotion step.
- Provider publication update after a reviewed `composition` or `policy` merge: `.agents/skills/site-publication-cutover/SKILL.md`
- Site-specific pull-request scope, exact-head CI, browser/publication acceptance, and base-drift preparation: `.agents/skills/site-pr-exact-head-acceptance/SKILL.md`
- Final merge authorization for every Site pull request: `.agents/skills/pr-merge-gate/SKILL.md`
- Site browser/PWA/mobile/search regression failure triage: `.agents/skills/site-browser-regression-triage/SKILL.md`

If more than one skill applies, use only the minimal set needed and follow them in dependency order. A normal Site PR completion path is task-specific work -> `site-pr-exact-head-acceptance` -> `pr-merge-gate`. A normal publication cutover uses `site-publication-cutover` first, then Site acceptance, then the merge gate. A coordinated document-set change that cannot merge provider-first uses `PUBLICATION_STAGING.md` first, then the provider candidate compatibility build, then `site-publication-cutover` for promotion after the provider merge. A browser failure encountered during Site acceptance may temporarily use `site-browser-regression-triage`, then return to Site acceptance after the repair creates a new head.

`site-pr-exact-head-acceptance` establishes Site-specific acceptance evidence but never authorizes merge. Before declaring a Site PR merge-ready, merging it, or completing a task whose final action is a merge, load `pr-merge-gate`. Green CI and `reviews = 0` must never be interpreted as a clean review state.

## Loading discipline

1. Read the matching `SKILL.md` first.
2. Follow only the canonical references needed for the current task; do not bulk-read historical pull requests as a substitute for current repository state.
3. Prefer current code, tests, workflow definitions, `MAINTENANCE.md`, and `PUBLISHING.md` over historical PR descriptions.
4. Use repository history only when current sources leave a material ambiguity unresolved.
5. If a skill conflicts with current canonical documentation or executable contracts, follow the canonical source and update the stale skill.
6. If the PR head changes, invalidate evidence bound to the previous head and reacquire only the affected Site-acceptance and merge-gate evidence. Do not discard unaffected evidence or restart unrelated gates solely because the head changed.

This routing discipline is not an additional acceptance checklist. Optional diagnostic reads or a locally stricter procedure do not become mandatory gates unless current repository authority requires them or a concrete unresolved uncertainty invalidates relied-upon evidence.

## Authority boundary

The active canonical authorities are `site`, `composition`, and `policy`. The external provider set published by Site is exactly `composition` and `policy`. Skill and Webapp remain reader/artifact concepts under Composition; they are not independent provider branches.

Site owns integration, reader-facing information architecture, exact provider locks, publication assembly, validation, provenance, PWA integration, and Pages deployment. Repository-local Agent Skills orchestrate maintenance and merge acceptance; they do not become a second semantic authority. Do not move provider-owned Composition or Policy semantics into Site merely to complete an integration task.

_Source: `policy/project.md` in this repository; rule ID: `project.site-maintenance`; severity: `mandatory`._




