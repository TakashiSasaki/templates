<!--
agent-policy-generated: true
configuration: .agent-policy.yml
DO NOT EDIT DIRECTLY
-->

# Repository agent instructions

These instructions were generated from shared policy profiles and repository-specific policy files.

## Policy system

- Semantic configuration: `.agent-policy.yml`
- Pinned shared toolchain: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb`
- Repository policy inputs:
  - `repository-policy/authority-boundary.md`
  - `repository-policy/history-boundary.md`
  - `repository-policy/architecture-decisions.md`
  - `repository-policy/release-trust.md`
  - `repository-policy/toolchain-safety.md`
  - `repository-policy/maintainer-validation.md`
  - `repository-policy/documentation-boundary.md`
- Generated operational skills:
  - `.agents/skills/pr-review/SKILL.md`
  - `.agents/skills/orchestrate-repository-change/SKILL.md`

Do not edit this generated file directly. Change `.agent-policy.yml` or its repository policy inputs, then regenerate with the pinned toolchain. Before editing repository files, inspect any repository-local skill catalog that exists and read the relevant generated or handwritten skills.


## Define the change contract before editing

Before editing, identify the requested outcome, the allowed change surface, the existing behavior and invariants that must be preserved, explicit non-goals, and the evidence required for acceptance. Treat unspecified behavior as preserved unless the requested change necessarily alters it; do not silently broaden the contract to resolve ambiguity or implementation difficulty.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/core/change-contract.md`; rule ID: `changes.define-contract`; severity: `mandatory`._


## Preserve the agreed acceptance baseline

Once implementation or audit begins against an agreed change contract, do not retroactively expand its scope, non-goals, completion criteria, required evidence, or stop condition. Rebaseline only with explicit authorization, and record the impact on completed work and prior evidence.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/core/acceptance-baseline.md`; rule ID: `changes.preserve-acceptance-baseline`; severity: `mandatory`._


## Keep changes within the requested scope

Do not modify files, behavior, dependencies, formatting, or architecture that are unrelated to the requested change. Inspect the final diff and remove incidental changes before reporting completion.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/core/change-scope.md`; rule ID: `changes.minimize-scope`; severity: `mandatory`._


## Escalate material semantic ambiguity

When an unresolved choice would materially affect observable behavior, data meaning, compatibility, architecture, risk, or scope, do not guess. Present the viable options, trade-offs, impact, and a recommendation, and obtain an explicit decision before making the dependent change.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/core/semantic-decision-gates.md`; rule ID: `decisions.escalate-semantic-ambiguity`; severity: `mandatory`._


## Do not weaken existing tests

Do not delete, skip, narrow, or relax an existing test merely to make a change pass. For a bug fix, add a regression test that fails before the fix and passes afterward whenever the failure can be reproduced deterministically.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/core/regression-safety.md`; rule ID: `regression.no-weaken-tests`; severity: `mandatory`._


## Run the repository's required verification

Use the verification command declared by the repository and add focused checks needed for the changed behavior or failure mode. Confirm that the executed checks cover the changed surface and the current revision; a check that is pending, skipped, not triggered, stale, blocked, or merely inspected is not a passing result. Report every required check that was not run or did not pass.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/core/testing.md`; rule ID: `testing.run-required-checks`; severity: `mandatory`._


## Keep verification evidence bound to its layer

Bind every verification result to the exact revision or artifact and to its evidence layer. Report repository-local checks, environment-dependent checks, remote CI, and independent audit separately; success in one layer does not prove success in another.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/core/evidence-layers.md`; rule ID: `verification.separate-evidence-layers`; severity: `mandatory`._


## Keep derived artifacts synchronized

When a change affects generated, mirrored, compiled, or otherwise derived artifacts, update them from their declared source of truth using the repository's documented process and verify that no stale or missing output remains. Do not hand-edit generated artifacts unless the repository explicitly designates that operation as authoritative.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/core/generated-artifacts.md`; rule ID: `consistency.synchronize-derived-artifacts`; severity: `mandatory`._


## Preserve externally observable contracts

Do not break public APIs, serialized data, configuration formats, command-line interfaces, or migration paths unless the requested change explicitly authorizes the incompatibility and documents its consequences.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/core/compatibility.md`; rule ID: `compatibility.preserve-contracts`; severity: `mandatory`._


## Revalidate destructive actions against current state

Immediately before deleting, overwriting, migrating, deploying, publishing, force-updating, or otherwise making an irreversible or externally visible change, re-read the target's current state and revalidate its identity, scope, version or revision, protections, and conflicting uses. Prefer dry-run, least-scope, and idempotent operations; do not authorize the action solely from stale observations made earlier in the task.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/core/destructive-actions.md`; rule ID: `safety.revalidate-destructive-actions`; severity: `mandatory`._


## Bind validated state to the effective operation

When correctness or safety depends on a validated or authorized target identity, scope, or other mutable precondition, ensure that the same effective target and required preconditions remain bound to the operation through use. Account for normalization, indirection, aliases, redirects, rebinding, and concurrent mutation; use stable identity or protected state, an atomic, transactional, or serialized mechanism, or revalidation at a protected commit or use boundary as appropriate. Fail closed if the operation can proceed against a different effective target or after the condition that authorized or validated it has become stale.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/core/validation-operation-binding.md`; rule ID: `safety.bind-validated-state-to-operation`; severity: `mandatory`._


## Limit rollback to changes owned by the operation

For a multi-step mutation, complete preflight before the first write, revalidate the live state at the commit boundary, and track which paths the current operation created or changed. On failure, roll back only those owned changes; never delete or overwrite pre-existing or concurrently created state as cleanup unless explicitly authorized.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/core/transaction-ownership.md`; rule ID: `safety.limit-rollback-to-owned-changes`; severity: `mandatory`._


## Report actual state and residual uncertainty

Distinguish implemented, generated, executed, verified, and merely inferred results. State unresolved failures and unverified assumptions explicitly.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/core/truthful-reporting.md`; rule ID: `reporting.truthful-status`; severity: `mandatory`._


## Separate task completion from review and merge authorization

Repository-change work must distinguish implementation task completion, validation completion, independent review, review completion, merge authorization, and the merged result. Completing implementation or validation does not establish that review was requested, review was completed, or merge authorization exists. Progression controls construction ordering; completion controls the agent's stopping boundary. A progression strategy must not by itself force review acquisition or merge completion.

A repository-change task may declare human-handoff as its completion boundary. Human handoff is valid completion when the agent has completed the authorized implementation and validation work, reports the independent-review state truthfully, reports merge authorization as not established, and leaves every pull request open and unmerged. When no applicable pre-existing review evidence establishes another state, report independent review as not requested or outstanding. When applicable pre-existing review evidence already establishes completed review, preserve and report that REVIEW_COMPLETE state rather than downgrading it merely because human-handoff was selected. When human-handoff is selected, the agent must not initiate a new review request through reviewer assignment, provider invocation, requested-reviewer state, or any other review-request mechanism. Existing review evidence may be observed, inspected, and reported, but handoff does not acquire new review evidence.

Human handoff is not a review waiver, does not remove acceptance requirements for a later review or merge, and does not authorize a merge. Reports must not label a handoff review complete unless applicable pre-existing review evidence establishes that state, and must not label the handoff merge ready or merged. Use explicit state labels such as IMPLEMENTATION_COMPLETE, VALIDATION_COMPLETE, REVIEW_NOT_REQUESTED, REVIEW_PENDING, REVIEW_COMPLETE, HANDOFF_READY, MERGE_READY, and MERGED only when the corresponding state is established.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/core/repository-change-completion.md`; rule ID: `changes.separate-task-review-merge-state`; severity: `mandatory`._


## Do not expose or commit secrets

Do not print, persist, or commit credentials, private keys, access tokens, session material, or unredacted sensitive configuration. Use established secret-management mechanisms.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/security/secrets.md`; rule ID: `security.no-secrets`; severity: `mandatory`._


## Validate data at trust boundaries

Validate untrusted input before it reaches privileged operations, persistence, command execution, or external requests. Preserve existing authentication and authorization checks.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/security/input-validation.md`; rule ID: `security.validate-boundaries`; severity: `mandatory`._


## Bind cumulative review evidence to an ordered pull-request stack

When a completed review is claimed to cover multiple members of a stacked pull-request topology, acceptance evidence must bind to the integration base exact SHA and tree, the ordered stack membership, each member exact head SHA, the stack tip exact SHA, the cumulative reviewed scope, the review contract, reviewer independence, the review completion state, and material limitations.

A review event, approval state, or tip-only review must not infer lower stack coverage or establish acceptance coverage for lower stack members by inference. Each covered member must be identifiable from explicit cumulative coverage evidence. Missing, ambiguous, or provider-only coverage is incomplete evidence and keeps merge authorization fail-closed.

Evaluate applicability again when a member exact head changes, stack ordering changes, integration base changes, cumulative scope changes, or the review contract changes. Reuse unchanged evidence only when its bindings and remaining stack applicability are established; if applicability is unknown, fail closed. A lower member merge may move a later member's base without mechanically invalidating all evidence, but the changed bindings and remaining coverage must be evaluated before relying on it.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/pull-request/stacked-review-coverage.md`; rule ID: `pull-request.require-explicit-stacked-review-coverage`; severity: `mandatory`._


## Evaluate merge readiness against the current target branch HEAD

Before declaring a pull request merge-ready, establish the current target branch full commit SHA and evaluate the proposed change against that exact target state. If the proposed head is not based on the current target head, inspect the intervening target change and determine whether it affects scope, validation applicability, review conclusions, mergeability, or another acceptance condition.

Synchronize or rebuild the proposed head only when that impact evaluation or current repository policy requires it. Do not require proposed-head synchronization solely because the target branch moved when the intervening change is established not to invalidate the applicable acceptance evidence.

Target-branch movement invalidates the freshness decision itself, but it does not by itself invalidate unrelated exact-head CI or review evidence. Do not claim target-branch freshness from cached, historical, or inferred branch metadata.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/pull-request/target-branch-head-freshness.md`; rule ID: `pull-request.verify-target-branch-head-freshness`; severity: `mandatory`._


## Require an independent exact-head review before merge

Before merging a pull request, require at least one completed review from an independent reviewer or review system for the exact proposed head commit. A review request, pending review, absence of review findings, or zero completed reviews is not review evidence and must block merge. The agent or actor that implemented the proposed change must not count its own self-review as the required independent review.

A submitted or provider-recorded review object is not by itself evidence that the review's required analysis completed. The relied-upon evidence must establish, under the applicable review procedure or review contract, that the required analysis completed for the exact proposed head. A review that reports itself as incomplete, partial, failed, or materially limited such that required analysis was not completed must not satisfy the independent-review requirement, even when a provider records that review as submitted or completed. If current evidence cannot establish whether the required analysis completed, keep merge authorization fail-closed rather than inferring completion from a provider event, review state, or the absence of blocking findings.

The relied-upon review evidence must identify the reviewed exact head through review metadata or an unambiguous completed review result. If the proposed head changes after that review, treat the review as stale and obtain a new completed review for the new exact head before merge.

If the required reviewer is unavailable or does not complete the review, report the pull request as blocked rather than waiving the requirement. Only an explicit repository policy may define an exception; an implementing agent must not invent or self-authorize one.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/pull-request/independent-exact-head-review.md`; rule ID: `pull-request.require-independent-exact-head-review`; severity: `mandatory`._


## Close review threads before merge

Before merging a pull request, inspect the current review threads and submitted reviews for the exact proposed head. Resolve each actionable thread through a code or documentation change, or record an explicit disposition when no change is warranted. Do not merge while unresolved review threads remain unless an explicit repository policy defines a documented exception.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/pull-request/review-thread-closure.md`; rule ID: `pull-request.close-review-threads-before-merge`; severity: `mandatory`._


## Require exact-head CI evidence before merge

Before declaring a pull request merge-ready or merging it, identify the checks that are applicable to the current proposed head from the current repository workflow and validation definitions. Rely only on CI or validation evidence that applies to that exact head commit. A successful result for an older head is historical evidence and must not satisfy the current merge gate.

Do not treat an expected but not yet observable check as successful, non-applicable, or absent merely because one live query returns no result. Until applicable exact-head checks have been positively identified or their non-applicability is established by current repository policy, keep merge authorization fail-closed.

If a newer applicable exact-head run supersedes an older cancelled or stale run, evaluate the newest applicable evidence rather than treating the superseded run by itself as the current result.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/pull-request/exact-head-ci-evidence.md`; rule ID: `pull-request.require-exact-head-ci-evidence`; severity: `mandatory`._


## Fail closed while expected CI evidence is unresolved

When current repository definitions make an exact-head check expected but live evidence for that check is not yet observable, treat the situation as unresolved discovery rather than as success, failure, or confirmed absence. Continue read-only discovery while the proposed head and applicability conditions remain unchanged.

Do not classify an expected check as absent from a single empty query, repeated queries against only one live index, or elapsed time alone. A confirmed-absence decision requires corroborating current evidence sufficient to distinguish delayed indexing or execution from a check that did not materialize.

Once applicable exact-head checks have been positively identified and acceptable evidence has been recorded, do not re-enter discovery merely for conservatism while the proposed head and the conditions that determine check applicability remain unchanged. Re-enter discovery only when a concrete invalidation signal makes the prior discovery conclusion inapplicable or uncertain.

Do not mutate the pull request or proposed head solely to manufacture new CI evidence while discovery remains unresolved. If uncertainty remains, keep merge authorization blocked rather than inferring success or non-applicability.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/pull-request/ci-discovery-fail-closed.md`; rule ID: `pull-request.fail-closed-on-unresolved-ci-discovery`; severity: `mandatory`._


## Reuse valid pull-request evidence until an applicable binding changes

Once scope, validation, review, or other acceptance evidence has been accepted for a defined proposed-head identity and applicability context, reuse that evidence while the facts that bind it remain unchanged.

Do not make repeated observations, extra review cycles, waiting periods, or redundant evidence collection mandatory solely because they are more conservative. Additional diagnostic work may be performed when concrete uncertainty exists, but it must not silently enlarge the acceptance baseline or become a new merge requirement unless current repository policy requires it.

Reacquire only the evidence affected by a concrete invalidation signal. A changed proposed head invalidates evidence bound to the former head. Target-branch movement requires impact evaluation, but it does not by itself invalidate unrelated exact-head evidence whose applicability and semantic basis remain unchanged. Changes to scope, validation definitions, review state, or another evidence-binding condition invalidate the corresponding evidence. Elapsed time alone does not invalidate exact-head evidence unless current repository policy defines an explicit freshness limit.

If the continued validity of relied-upon evidence cannot be established, fail closed and reacquire the affected evidence rather than inventing a broader gate.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/pull-request/reuse-valid-evidence.md`; rule ID: `pull-request.reuse-valid-exact-head-evidence`; severity: `mandatory`._


## Require current mergeability before merge

Immediately before merge authorization, verify from current repository state that the pull request can be merged. Historical mergeability, conflict-free status observed for an older head, or an earlier successful dry run must not substitute for the current state.

If mergeability is unknown, false, or changes before the merge operation completes, keep or return merge authorization to a blocked state and refresh the relevant current evidence before attempting merge again.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/pull-request/current-mergeability.md`; rule ID: `pull-request.require-current-mergeability`; severity: `mandatory`._


## Refresh mutable live state and validate evidence bindings before merge

Immediately before authorizing or executing a pull-request merge, refresh the mutable repository state that can invalidate the accepted snapshot, including the current proposed head, current target-branch head, current review state, unresolved review-thread state, and current mergeability. Validate that relied-upon scope, exact-head validation, and completed review evidence are still bound to the resulting current state.

Do not unconditionally reacquire exact-head validation, completed review, or scope evidence whose binding facts remain unchanged and whose continued validity is established by current policy. Re-evaluate only the acceptance evidence affected by a changed head, target branch, scope, validation definition, review state, thread state, mergeability state, or other concrete invalidation signal.

If a required current value is missing, stale, materially different, or cannot be reconciled to the accepted evidence, leave merge authorization blocked and reacquire the affected evidence.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/pull-request/final-live-state-refresh.md`; rule ID: `pull-request.refresh-live-state-before-merge`; severity: `mandatory`._


## Guard merge against proposed-head movement

When executing a pull-request merge, bind the operation to the exact proposed head commit whose current acceptance evidence was approved, using the strongest supported immutable-head precondition available on the execution surface. The merge must not silently apply to a different head that appeared after final acceptance.

If the merge surface cannot enforce an immutable proposed-head precondition, treat that limitation as part of the final acceptance risk: refresh current state immediately before execution and verify the result afterward rather than assuming the earlier accepted snapshot is still current.

If the merge operation reports that the proposed head or repository state changed, do not retry blindly. Refresh current state and re-run the affected acceptance gates for the resulting proposed head before attempting merge again.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/pull-request/immutable-head-guard.md`; rule ID: `pull-request.guard-merge-against-head-movement`; severity: `mandatory`._


## Verify the merge result after execution

After executing a pull-request merge, verify from current repository state that the pull request is actually merged, record the resulting merge identity, and confirm that the target branch contains the intended merged result or a later intentional successor.

Do not report merge completion solely because the merge operation returned without a transport error. If the observed repository state does not establish that the intended result was merged, report the merge outcome as unresolved or failed and investigate before claiming completion.

Treat any release, publication, deployment, or other post-merge readiness requirement as a separate acceptance boundary; successful merge verification does not by itself establish those later states.

_Source: `TakashiSasaki/templates@65a11ecac55c95edf20c1c445fd0c0092b4668cb:policy/pull-request/post-merge-verification.md`; rule ID: `pull-request.verify-merge-result`; severity: `mandatory`._


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




