<!--
agent-policy-generated: true
configuration: .agent-policy.yml
DO NOT EDIT DIRECTLY
-->

# Repository agent instructions

These instructions were generated from shared policy profiles and repository-specific policy files.

## Policy system

- Semantic configuration: `.agent-policy.yml`
- Pinned shared toolchain: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41`
- Repository policy inputs:
  - `policy/repository/authority-boundary.md`
  - `policy/repository/history-boundary.md`
  - `policy/repository/reading-scope.md`
  - `policy/repository/maintainer-validation.md`

Do not edit this generated file directly. Change `.agent-policy.yml` or its repository policy inputs, then regenerate with the pinned toolchain. Before editing repository files, inspect any repository-local skill catalog that exists and read the relevant generated or handwritten skills.


## Define the change contract before editing

Before editing, identify the requested outcome, the allowed change surface, the existing behavior and invariants that must be preserved, explicit non-goals, and the evidence required for acceptance. Treat unspecified behavior as preserved unless the requested change necessarily alters it; do not silently broaden the contract to resolve ambiguity or implementation difficulty.

_Source: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41:policy/core/change-contract.md`; rule ID: `changes.define-contract`; severity: `mandatory`._


## Preserve the agreed acceptance baseline

Once implementation or audit begins against an agreed change contract, do not retroactively expand its scope, non-goals, completion criteria, required evidence, or stop condition. Rebaseline only with explicit authorization, and record the impact on completed work and prior evidence.

_Source: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41:policy/core/acceptance-baseline.md`; rule ID: `changes.preserve-acceptance-baseline`; severity: `mandatory`._


## Keep changes within the requested scope

Do not modify files, behavior, dependencies, formatting, or architecture that are unrelated to the requested change. Inspect the final diff and remove incidental changes before reporting completion.

_Source: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41:policy/core/change-scope.md`; rule ID: `changes.minimize-scope`; severity: `mandatory`._


## Escalate material semantic ambiguity

When an unresolved choice would materially affect observable behavior, data meaning, compatibility, architecture, risk, or scope, do not guess. Present the viable options, trade-offs, impact, and a recommendation, and obtain an explicit decision before making the dependent change.

_Source: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41:policy/core/semantic-decision-gates.md`; rule ID: `decisions.escalate-semantic-ambiguity`; severity: `mandatory`._


## Do not weaken existing tests

Do not delete, skip, narrow, or relax an existing test merely to make a change pass. For a bug fix, add a regression test that fails before the fix and passes afterward whenever the failure can be reproduced deterministically.

_Source: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41:policy/core/regression-safety.md`; rule ID: `regression.no-weaken-tests`; severity: `mandatory`._


## Run the repository's required verification

Use the verification command declared by the repository and add focused checks needed for the changed behavior or failure mode. Confirm that the executed checks cover the changed surface and the current revision; a check that is pending, skipped, not triggered, stale, blocked, or merely inspected is not a passing result. Report every required check that was not run or did not pass.

_Source: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41:policy/core/testing.md`; rule ID: `testing.run-required-checks`; severity: `mandatory`._


## Keep verification evidence bound to its layer

Bind every verification result to the exact revision or artifact and to its evidence layer. Report repository-local checks, environment-dependent checks, remote CI, and independent audit separately; success in one layer does not prove success in another.

_Source: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41:policy/core/evidence-layers.md`; rule ID: `verification.separate-evidence-layers`; severity: `mandatory`._


## Keep derived artifacts synchronized

When a change affects generated, mirrored, compiled, or otherwise derived artifacts, update them from their declared source of truth using the repository's documented process and verify that no stale or missing output remains. Do not hand-edit generated artifacts unless the repository explicitly designates that operation as authoritative.

_Source: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41:policy/core/generated-artifacts.md`; rule ID: `consistency.synchronize-derived-artifacts`; severity: `mandatory`._


## Preserve externally observable contracts

Do not break public APIs, serialized data, configuration formats, command-line interfaces, or migration paths unless the requested change explicitly authorizes the incompatibility and documents its consequences.

_Source: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41:policy/core/compatibility.md`; rule ID: `compatibility.preserve-contracts`; severity: `mandatory`._


## Revalidate destructive actions against current state

Immediately before deleting, overwriting, migrating, deploying, publishing, force-updating, or otherwise making an irreversible or externally visible change, re-read the target's current state and revalidate its identity, scope, version or revision, protections, and conflicting uses. Prefer dry-run, least-scope, and idempotent operations; do not authorize the action solely from stale observations made earlier in the task.

_Source: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41:policy/core/destructive-actions.md`; rule ID: `safety.revalidate-destructive-actions`; severity: `mandatory`._


## Limit rollback to changes owned by the operation

For a multi-step mutation, complete preflight before the first write, revalidate the live state at the commit boundary, and track which paths the current operation created or changed. On failure, roll back only those owned changes; never delete or overwrite pre-existing or concurrently created state as cleanup unless explicitly authorized.

_Source: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41:policy/core/transaction-ownership.md`; rule ID: `safety.limit-rollback-to-owned-changes`; severity: `mandatory`._


## Report actual state and residual uncertainty

Distinguish implemented, generated, executed, verified, and merely inferred results. State unresolved failures and unverified assumptions explicitly.

_Source: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41:policy/core/truthful-reporting.md`; rule ID: `reporting.truthful-status`; severity: `mandatory`._


## Do not expose or commit secrets

Do not print, persist, or commit credentials, private keys, access tokens, session material, or unredacted sensitive configuration. Use established secret-management mechanisms.

_Source: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41:policy/security/secrets.md`; rule ID: `security.no-secrets`; severity: `mandatory`._


## Validate data at trust boundaries

Validate untrusted input before it reaches privileged operations, persistence, command execution, or external requests. Preserve existing authentication and authorization checks.

_Source: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41:policy/security/input-validation.md`; rule ID: `security.validate-boundaries`; severity: `mandatory`._


## Verify merge readiness against the current target branch HEAD

Before declaring a pull request merge-ready, fetch the current target branch full commit SHA and confirm that the proposed head is based on, or has been explicitly synchronized with, that target branch HEAD. If the target branch moves after validation or review evidence was collected, treat prior merge-readiness evidence as stale until the impact is re-evaluated. Do not claim target-branch freshness from cached, historical, or inferred branch metadata.

_Source: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41:policy/pull-request/target-branch-head-freshness.md`; rule ID: `pull-request.verify-target-branch-head-freshness`; severity: `mandatory`._


## Close review threads before merge

Before merging a pull request, inspect the current review threads and submitted reviews for the exact proposed head. Resolve each actionable thread through a code or documentation change, or record an explicit disposition when no change is warranted. Do not merge while unresolved review threads remain unless an explicit repository policy defines a documented exception.

_Source: `TakashiSasaki/templates@5de32547e68fa15e24ff3b8affadf12e9d730a41:policy/pull-request/review-thread-closure.md`; rule ID: `pull-request.close-review-threads-before-merge`; severity: `mandatory`._


## Keep Webapp artifact contracts outside shared policy

The `webapp` branch owns framework-neutral Web-application artifact contracts. `template/contracts/manifest.json`, the registered contract documents and schemas below `template/`, migration history, implementation-evidence contract, release-evidence contract, release-bundle contract, and their canonical validators under `template/scripts/` remain authoritative for the Webapp artifact.

Shared agent policy governs maintainer working behavior only. Do not copy Webapp artifact semantics into repository policy modules, and do not make policy rule IDs, profiles, generated policy artifacts, or the policy toolchain prerequisites for validating or using the Webapp contracts.

Keep policy configuration and generated maintainer instructions outside the copyable Webapp artifact boundary unless a separately reviewed artifact-contract change explicitly establishes such ownership.

_Source: `policy/repository/authority-boundary.md` in this repository; rule ID: `webapp-source.preserve-artifact-contract-authority`; severity: `mandatory`._


## Preserve the webapp branch history boundary

Template-development changes must be based on `webapp`. The `webapp`, `skill`, `site`, and `policy` histories are unrelated.

Do not merge, rebase, or cherry-pick another major branch into `webapp` merely to share files or policy. Cross-branch reuse must occur through reviewed immutable references or independent reimplementation at the appropriate ownership boundary.

_Source: `policy/repository/history-boundary.md` in this repository; rule ID: `webapp-source.preserve-unrelated-history`; severity: `mandatory`._


## Read authoritative Webapp contracts for affected domains

Always read `README.md`, `template/TEMPLATE.md`, `template/docs/architecture/responsibility-boundaries.md`, and files directly named by the task.

For a contract-family change, read `template/contracts/manifest.json` and the corresponding architecture, schema, validator, migration, test, and evidence documents below `template/` for that family. Treat those artifact documents as the normative authority for Webapp semantics; repository policy may reference them but must not silently replace them.

Read source-only topology, publication, distribution-boundary, and maintainer-policy documents outside `template/` when the task affects template maintenance or publication rather than the copied Webapp artifact itself.

_Source: `policy/repository/reading-scope.md` in this repository; rule ID: `webapp-source.read-authoritative-webapp-contracts`; severity: `mandatory`._


## Run the Webapp template maintainer validation baseline

Use the isolated Python and pip bootstrap procedure documented in `README.md` before executing repository validators.

For changes that can affect the distribution boundary, run both source-only distribution validator entry points from the branch root. For changes that can affect Webapp contracts or validation, run both supported entry points for each applicable canonical validator from `template/`, then run the source-maintainer standard-library test suite. The complete retained baseline includes:

```sh
python scripts/validate_distribution.py
python -m scripts.validate_distribution
(cd template && ../.venv/bin/python scripts/validate_contracts.py)
(cd template && ../.venv/bin/python -m scripts.validate_contracts)
(cd template && ../.venv/bin/python scripts/validate_contract_evolution.py)
(cd template && ../.venv/bin/python -m scripts.validate_contract_evolution)
(cd template && ../.venv/bin/python scripts/validate_implementation_evidence.py)
(cd template && ../.venv/bin/python -m scripts.validate_implementation_evidence)
(cd template && ../.venv/bin/python scripts/validate_release_evidence.py)
(cd template && ../.venv/bin/python -m scripts.validate_release_evidence)
(cd template && ../.venv/bin/python scripts/validate_release_bundle.py)
(cd template && ../.venv/bin/python -m scripts.validate_release_bundle)
.venv/bin/python -m unittest discover -s tests -v
```

When validating product-mode release evidence or bundles, supply the exact immutable candidate revision required by the artifact contract. Do not substitute policy-toolchain validation for these repository-owned validators.

_Source: `policy/repository/maintainer-validation.md` in this repository; rule ID: `webapp-source.run-maintainer-validation`; severity: `mandatory`._




