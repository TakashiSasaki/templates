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
  - `policy/repository/artifact-boundary.md`
  - `policy/repository/distribution-integrity.md`
  - `policy/repository/profile-model.md`
  - `policy/repository/reading-scope.md`
  - `policy/repository/validation.md`
  - `policy/repository/publication-boundary.md`

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


## Preserve source, distribution, and concrete-Skill boundaries

This branch is the source repository for a reusable Agent Skill template product. The repository root is not an installable Skill directory.

Treat these as distinct artifacts:

1. the complete source checkout;
2. the copyable `template/` distribution; and
3. a concrete Skill developed from that distribution.

The user-facing artifact is `template/`, whose contents are copied directly to a new Skill root. Consumer-facing Skill contracts, profile documentation, operational resource placeholders, and concrete-Skill instructions belong under `template/`; do not recreate them at the branch root as alternate authorities.

Source-only fixtures, negative cases, publication integration, source-maintainer review material, migration audits, and canonical adoption tests remain outside `template/`. Do not add source-only files to the distribution merely to make the trees look similar.

_Source: `policy/repository/artifact-boundary.md` in this repository; rule ID: `skill-source.preserve-artifact-boundaries`; severity: `mandatory`._


## Preserve the exact copyable distribution

`distribution-manifest.json` is authoritative for the copyable inventory.

Validator implementations projected from `.github/scripts/` into `template/.github/scripts/` must retain identical bytes and Git-significant modes. For a projected validator, change the source implementation and its distributed copy together, then run both source distribution validation and copied-Skill validation.

Keep `template/` closed and independently usable after copying. Reject undeclared copied files, missing declared files, projection byte or mode drift, prohibited symbolic links or Git links, path traversal or `.git` path components, maintainer-only leakage, automatic content transformation, and runtime or validation dependence on the source checkout.

Do not pre-enroll the copyable Skill in the shared policy toolchain merely because the source repository consumes it. Source-maintainer `.agent-policy.yml`, `.agent-policy.lock`, `.agent-policy/` state, `policy/` inputs, and `check-agent-policy` workflow authority remain outside `template/`. The distributed `AGENTS.md` is a Skill artifact-development contract, not an inherited projection of source-maintainer policy. A concrete Skill repository may adopt shared policy explicitly after copying as a separate repository-maintenance decision.

_Source: `policy/repository/distribution-integrity.md` in this repository; rule ID: `skill-source.preserve-distribution-integrity`; severity: `mandatory`._


## Preserve the profile-aware Skill scaffold

The distribution is one profile-aware scaffold, not one directory per profile.

`template-scaffold` is reserved for the uncustomized template. `instruction-only` is the sole exclusive profile. `knowledge-augmented`, `asset-driven`, `script-assisted`, `packaged-cli`, `mcp-enabled`, `browser-interface`, and `headless-service` are selectively composable, and a combination retains the union of its required contracts.

Do not impose a runtime, CLI, MCP, browser, service, or deployment layer on a Skill that does not need it.

Changes to profile semantics must keep the applicable template contracts, validators, positive and negative fixtures, combined fixtures, consumer documentation, distribution manifest, and publication material synchronized.

_Source: `policy/repository/profile-model.md` in this repository; rule ID: `skill-source.preserve-profile-model`; severity: `mandatory`._


## Use repository-specific reading scope

Always read `README.md`, `docs/architecture/distribution-boundary.md`, `docs/architecture/distribution-classification.json`, and files directly named by the task in addition to the generated repository instructions.

Read distribution inventory, profile contracts, runtime/interface contracts, publication metadata, site compatibility material, and adoption tests only when the task touches those boundaries. Do not load advanced MCP, browser, or service material for unrelated changes.

_Source: `policy/repository/reading-scope.md` in this repository; rule ID: `skill-source.use-task-scoped-reading`; severity: `mandatory`._


## Run the Skill source and distribution validation baseline

For changes that can affect the source/distribution boundary, run at least:

```sh
ruby .github/scripts/test-distribution-boundary.rb
ruby .github/scripts/test-skill-distribution.rb
ruby .github/scripts/validate-skill-distribution.rb
python .github/scripts/validate_skill_repository.py template
python template/.github/scripts/test_template_baseline.py
ruby .github/scripts/test-copyable-template-consumption.rb
```

The Python validation host requires Python 3.12 or newer, PyYAML 6.0.3, and Git. Run additional profile-specific regression tests when the affected profile requires them. Networked or executable profile changes require real fixture and negative-path evidence, not only Markdown checks.

_Source: `policy/repository/validation.md` in this repository; rule ID: `skill-source.run-distribution-validation`; severity: `mandatory`._


## Preserve publication and unrelated-history boundaries

`skill`, `site`, `policy`, and `webapp` have unrelated histories. Do not merge, rebase, or cherry-pick across them.

The `skill` branch owns its publication catalog and stable document IDs. Public consumer documents resolve below `template/`. The `site` branch consumes reviewed full commit SHAs and owns navigation, assembly, provenance, repository-tree rendering, and deployment.

Keep Pages compatibility build-only from provider branches. GitHub Pages deployment remains suspended from `skill`; restoration belongs to a separate reviewed `site` pull request.

_Source: `policy/repository/publication-boundary.md` in this repository; rule ID: `skill-source.preserve-publication-branch-boundaries`; severity: `mandatory`._




