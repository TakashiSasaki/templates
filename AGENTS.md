<!--
agent-policy-generated: true
configuration: .agent-policy.yml
DO NOT EDIT DIRECTLY
-->

# Repository agent instructions

These instructions were generated from shared policy profiles and repository-specific policy files.

## Policy system

- Semantic configuration: `.agent-policy.yml`
- Pinned shared toolchain: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87`
- Repository policy inputs:
  - `repository-policy/authority-boundary.md`
  - `repository-policy/history-boundary.md`
  - `repository-policy/architecture-decisions.md`
  - `repository-policy/release-trust.md`
  - `repository-policy/toolchain-safety.md`
  - `repository-policy/maintainer-validation.md`
  - `repository-policy/documentation-boundary.md`

Do not edit this generated file directly. Change `.agent-policy.yml` or its repository policy inputs, then regenerate with the pinned toolchain. Before editing repository files, inspect any repository-local skill catalog that exists and read the relevant generated or handwritten skills.


## Define the change contract before editing

Before editing, identify the requested outcome, the allowed change surface, the existing behavior and invariants that must be preserved, explicit non-goals, and the evidence required for acceptance. Treat unspecified behavior as preserved unless the requested change necessarily alters it; do not silently broaden the contract to resolve ambiguity or implementation difficulty.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/core/change-contract.md`; rule ID: `changes.define-contract`; severity: `mandatory`._


## Preserve the agreed acceptance baseline

Once implementation or audit begins against an agreed change contract, do not retroactively expand its scope, non-goals, completion criteria, required evidence, or stop condition. Rebaseline only with explicit authorization, and record the impact on completed work and prior evidence.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/core/acceptance-baseline.md`; rule ID: `changes.preserve-acceptance-baseline`; severity: `mandatory`._


## Keep changes within the requested scope

Do not modify files, behavior, dependencies, formatting, or architecture that are unrelated to the requested change. Inspect the final diff and remove incidental changes before reporting completion.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/core/change-scope.md`; rule ID: `changes.minimize-scope`; severity: `mandatory`._


## Escalate material semantic ambiguity

When an unresolved choice would materially affect observable behavior, data meaning, compatibility, architecture, risk, or scope, do not guess. Present the viable options, trade-offs, impact, and a recommendation, and obtain an explicit decision before making the dependent change.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/core/semantic-decision-gates.md`; rule ID: `decisions.escalate-semantic-ambiguity`; severity: `mandatory`._


## Do not weaken existing tests

Do not delete, skip, narrow, or relax an existing test merely to make a change pass. For a bug fix, add a regression test that fails before the fix and passes afterward whenever the failure can be reproduced deterministically.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/core/regression-safety.md`; rule ID: `regression.no-weaken-tests`; severity: `mandatory`._


## Run the repository's required verification

Use the verification command declared by the repository and add focused checks needed for the changed behavior or failure mode. Confirm that the executed checks cover the changed surface and the current revision; a check that is pending, skipped, not triggered, stale, blocked, or merely inspected is not a passing result. Report every required check that was not run or did not pass.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/core/testing.md`; rule ID: `testing.run-required-checks`; severity: `mandatory`._


## Keep verification evidence bound to its layer

Bind every verification result to the exact revision or artifact and to its evidence layer. Report repository-local checks, environment-dependent checks, remote CI, and independent audit separately; success in one layer does not prove success in another.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/core/evidence-layers.md`; rule ID: `verification.separate-evidence-layers`; severity: `mandatory`._


## Keep derived artifacts synchronized

When a change affects generated, mirrored, compiled, or otherwise derived artifacts, update them from their declared source of truth using the repository's documented process and verify that no stale or missing output remains. Do not hand-edit generated artifacts unless the repository explicitly designates that operation as authoritative.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/core/generated-artifacts.md`; rule ID: `consistency.synchronize-derived-artifacts`; severity: `mandatory`._


## Preserve externally observable contracts

Do not break public APIs, serialized data, configuration formats, command-line interfaces, or migration paths unless the requested change explicitly authorizes the incompatibility and documents its consequences.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/core/compatibility.md`; rule ID: `compatibility.preserve-contracts`; severity: `mandatory`._


## Revalidate destructive actions against current state

Immediately before deleting, overwriting, migrating, deploying, publishing, force-updating, or otherwise making an irreversible or externally visible change, re-read the target's current state and revalidate its identity, scope, version or revision, protections, and conflicting uses. Prefer dry-run, least-scope, and idempotent operations; do not authorize the action solely from stale observations made earlier in the task.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/core/destructive-actions.md`; rule ID: `safety.revalidate-destructive-actions`; severity: `mandatory`._


## Limit rollback to changes owned by the operation

For a multi-step mutation, complete preflight before the first write, revalidate the live state at the commit boundary, and track which paths the current operation created or changed. On failure, roll back only those owned changes; never delete or overwrite pre-existing or concurrently created state as cleanup unless explicitly authorized.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/core/transaction-ownership.md`; rule ID: `safety.limit-rollback-to-owned-changes`; severity: `mandatory`._


## Report actual state and residual uncertainty

Distinguish implemented, generated, executed, verified, and merely inferred results. State unresolved failures and unverified assumptions explicitly.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/core/truthful-reporting.md`; rule ID: `reporting.truthful-status`; severity: `mandatory`._


## Do not expose or commit secrets

Do not print, persist, or commit credentials, private keys, access tokens, session material, or unredacted sensitive configuration. Use established secret-management mechanisms.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/security/secrets.md`; rule ID: `security.no-secrets`; severity: `mandatory`._


## Validate data at trust boundaries

Validate untrusted input before it reaches privileged operations, persistence, command execution, or external requests. Preserve existing authentication and authorization checks.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/security/input-validation.md`; rule ID: `security.validate-boundaries`; severity: `mandatory`._


## Verify merge readiness against the current target branch HEAD

Before declaring a pull request merge-ready, fetch the current target branch full commit SHA and confirm that the proposed head is based on, or has been explicitly synchronized with, that target branch HEAD. If the target branch moves after validation or review evidence was collected, treat prior merge-readiness evidence as stale until the impact is re-evaluated. Do not claim target-branch freshness from cached, historical, or inferred branch metadata.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/pull-request/target-branch-head-freshness.md`; rule ID: `pull-request.verify-target-branch-head-freshness`; severity: `mandatory`._


## Require an independent exact-head review before merge

Before merging a pull request, require at least one completed review from an independent reviewer or review system for the exact proposed head commit. A review request, pending review, absence of review findings, or zero completed reviews is not review evidence and must block merge. The agent or actor that implemented the proposed change must not count its own self-review as the required independent review.

The relied-upon review evidence must identify the reviewed exact head through review metadata or an unambiguous completed review result. If the proposed head changes after that review, treat the review as stale and obtain a new completed review for the new exact head before merge.

If the required reviewer is unavailable or does not complete the review, report the pull request as blocked rather than waiving the requirement. Only an explicit repository policy may define an exception; an implementing agent must not invent or self-authorize one.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/pull-request/independent-exact-head-review.md`; rule ID: `pull-request.require-independent-exact-head-review`; severity: `mandatory`._


## Close review threads before merge

Before merging a pull request, inspect the current review threads and submitted reviews for the exact proposed head. Resolve each actionable thread through a code or documentation change, or record an explicit disposition when no change is warranted. Do not merge while unresolved review threads remain unless an explicit repository policy defines a documented exception.

_Source: `TakashiSasaki/templates@b12b190cff4a9f5fa9f9ba76cc3425c479b67b87:policy/pull-request/review-thread-closure.md`; rule ID: `pull-request.close-review-threads-before-merge`; severity: `mandatory`._


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




