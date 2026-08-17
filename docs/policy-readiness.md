# Policy toolkit readiness and completion roadmap

This document defines how the `policy` branch reaches a defensible completion state entirely within `TakashiSasaki/templates`.

The criteria are durable. A later audit-record commit records evidence against one exact candidate commit. The candidate, any required stable-promotion commit, and the audit-record commit are different commits. Passing selected tests or having the expected files present is not, by itself, a completion declaration.

## Completion states

The work advances through five distinct states:

1. **Development baseline**: core capabilities exist, but no full cross-cutting audit has been accepted.
2. **Frozen audit candidate**: one exact candidate commit has been selected after corrective work and remains unchanged while its evidence is evaluated.
3. **Candidate verified**: the frozen candidate satisfies every readiness gate whose evaluation point is `candidate commit` and has successful candidate CI and review evidence.
4. **Release aligned**: the `release-alignment` gate has passed through either a separate later promotion commit or an explicit no-promotion decision that preserves a valid stable pin.
5. **Policy toolkit complete**: a separate later audit-record commit names the frozen candidate, records the release-alignment evidence, and has itself passed review and CI.

The frozen candidate never contains its own SHA or its later audit record.

## Policy toolkit completion

Every gate whose evaluation point is `candidate commit` must pass at the same 40-character lowercase Git commit SHA. The `release-alignment` gate is evaluated later across the completion sequence; it is not a candidate-local gate and must not be marked passed merely because the candidate contains working release machinery.

| Gate | Evaluation point | Required condition | Existing evidence anchors |
| --- | --- | --- | --- |
| `scope` | `candidate commit` | The shared toolkit remains application-type independent and excludes product architecture. | `docs/adr/0003-application-neutral-policy-scope.md`, `tests/test_application_neutral_scope.py` |
| `configuration` | `candidate commit` | `.agent-policy.yml` remains the sole semantic configuration entry point and validates deterministically. | `docs/configuration.md`, `tests/test_config.py`, `tests/test_config_driven_check.py` |
| `generation` | `candidate commit` | Fresh adoption and `render` deterministically write the documented instructions, skills, workflows, and lock for the same inputs; dry-run adoption reports the same plan without mutation. | `docs/cli.md`, `docs/adoption.md`, `tests/test_init_render_check.py`, `tests/test_generate_repository_preview.py` |
| `validation` | `candidate commit` | `validate` is read-only and deterministically reports configuration and policy errors; `check` is read-only and detects stale or modified generated artifacts without changing the repository. | `docs/cli.md`, `tests/test_config_driven_check.py`, `tests/test_init_render_check.py` |
| `adoption` | `candidate commit` | Inspection, state-derived fresh or migration preparation, preview, and explicit transactional migration finalization preserve the documented safety boundary. | `docs/adoption.md`, `docs/adr/0002-repository-adoption.md`, `tests/test_adoption_*.py` |
| `single-skill-runtime` | `candidate commit` | The installed `agent-policy` skill is the single repository-facing entry point, executes only immutable full-SHA toolchains, follows `.agent-policy.lock` for managed repositories, reuses only identity-matching validated runtime caches, and exposes no generic migration-finalization route. | `docs/bootstrap-model.md`, `docs/adr/0007-single-agent-policy-skill-runtime-cache.md`, `tests/test_agent_policy_skill.py` |
| `release-model` | `candidate commit` | The schema-validated stable descriptor, runtime-manifest synchronization/digest verifier, and separate candidate-and-promotion lifecycle remain executable, tested, and free of mutable release references. | `docs/release-lifecycle.md`, `schemas/toolchain-release.schema.json`, `tests/test_release_lifecycle.py` |
| `identity` | `candidate commit` | Executable, generated, maintained, and repository-facing skill identities consistently use `TakashiSasaki/templates` and `policy`. | `tests/test_repository_identity.py`, `tests/test_toolchain_repository_identity.py`, `tests/test_agent_policy_skill.py` |
| `ci` | `candidate commit` | Policy CI is reproducible on its fixed baseline, neutralizes external Python and pip inputs, verifies the installed distribution set, and exercises the runtime-distribution matrix when runtime behavior changes. | `.github/workflows/ci.yml`, `.github/workflows/runtime-distribution.yml`, `tests/test_ci_reproducibility.py`, `tests/test_runtime_distribution.py` |
| `documentation` | `candidate commit` | Documentation builds strictly without any Pages upload or deployment authority on `policy`. | `.github/workflows/pages.yml`, `docs/documentation-publication.md`, `tests/test_documentation_publication.py` |
| `consistency` | `candidate commit` | README, architecture, ADRs, operational guides, release metadata, generated projections, workflows, and tests in the candidate do not contradict one another. | the candidate audit evidence and the full test suite |
| `release-alignment` | `completion sequence` | The stable channel either remains on its current full SHA with an explicit no-promotion rationale, or a separate promotion commit synchronizes `release/toolchain.json` and `skills/agent-policy/runtime-manifest.json` to the frozen candidate and records the matching runtime-lock digest, while retaining the existing verifier lock when compatible or updating it when the candidate requires a different probe environment. | `docs/release-lifecycle.md`, `release/toolchain.json`, `skills/agent-policy/runtime-manifest.json`, the promotion and audit records |

The existing anchors identify where evidence is expected; they do not pre-approve a gate. The audit must inspect behavior and cross-document consistency rather than merely confirm filenames.

## Commit roles and non-self-reference

The completion sequence uses distinct immutable commit roles:

1. The **candidate commit** contains the audited toolchain implementation and must remain unchanged.
2. When `release-alignment` requires stable movement, a later **promotion commit** updates the stable descriptor and single-skill runtime manifest to the candidate SHA and records the candidate runtime-lock digest. It updates the verifier lock only when the candidate requires a different probe environment; otherwise it retains and verifies the existing compatible lock.
3. A later **audit-record commit** adds or updates `docs/policy-readiness-audit.md`. It names the candidate SHA and, when required, the promotion commit SHA.

The audit-record commit must be later than the candidate and, when promotion is required, later than the promotion commit. The record does not contain its own commit SHA and does not attempt self-reference; its identity is supplied by Git history. No policy-toolkit-complete declaration is valid before this later audit-record commit has passed its own review and CI.

## Completion audit record

The final audit must be committed as `docs/policy-readiness-audit.md`. It must contain:

- the audited candidate's 40-character lowercase Git commit SHA;
- the audit date and reviewer or reviewing agent;
- an explicit pass or fail result for every gate and its declared evaluation point;
- commands executed and their results;
- successful `Policy CI` and `Policy documentation build` run identifiers for the candidate;
- candidate review status, unresolved review-thread count, and any accepted exceptions;
- confirmation that the candidate is frozen and is not referenced through a mutable branch or tag;
- the stable promotion decision;
- when promotion is required, the later promotion commit's 40-character lowercase Git SHA;
- when promotion is required, the matching runtime-lock digest and whether the verifier lock was retained as compatible or updated because the candidate required a different probe environment;
- when promotion is not required, the explicit reason that the existing stable pin remains valid.

The audit record must not claim completion while any gate is failed, unknown, waived without an explicit accepted decision, or supported only by a mutable ref. The branch may claim completion only after the audit-record commit itself passes `Policy CI`, `Policy documentation build`, review, and an unresolved review-thread count of zero.

## Roadmap

### Phase 1: establish the completion contract

- Add this readiness definition to the maintained documentation.
- Link it from the README and documentation navigation.
- Add regression tests for toolkit completion and Pages ownership.

### Phase 2: execute the cross-cutting audit

- Evaluate every `candidate commit` gate against code, generated artifacts, workflows, and documentation.
- Examine the future `release-alignment` decision without marking that sequence gate passed.
- Record missing evidence, contradictions, and defects without treating prior work as automatically passing.
- Open focused corrective changes for each material gap.

### Phase 3: close gaps and freeze the audit candidate

- Merge corrective changes only after tests, strict documentation build, and review pass.
- Select one exact candidate full SHA and leave that commit unchanged.
- Re-run every `candidate commit` gate, candidate CI, and candidate review against that SHA.
- Prepare the audit evidence without adding a self-referential audit record to the candidate.

### Phase 4: satisfy the release-alignment gate

- Decide whether the audited candidate requires stable release movement.
- When required, update `release/toolchain.json` and `skills/agent-policy/runtime-manifest.json` in a separate later promotion commit, including the candidate's runtime-lock SHA-256.
- Update the stable verifier lock in that promotion commit only when the candidate requires a different probe environment; otherwise retain and verify the existing compatible lock.
- Verify that the candidate is a strict ancestor of the promotion commit.
- When promotion is not required, preserve the existing stable pin and record the reason.
- Mark `release-alignment` passed only after the promotion or no-promotion evidence exists.
- Do not declare policy-toolkit completion in this phase.

### Phase 5: commit the final audit record and declare toolkit completion

- Commit `docs/policy-readiness-audit.md` after the candidate and any required promotion commit.
- Record all candidate-local gate evidence, the release-alignment result, the frozen candidate SHA, and the promotion commit or no-promotion rationale.
- Run Policy CI, strict documentation build, and review on the audit-record commit.
- Declare policy-toolkit completion only after those checks pass with zero unresolved threads.

## Explicit non-goals

Completion work must not introduce application-category profiles, Web surface or route contracts, framework or deployment topology decisions, a generic arbitrary-command executor, mutable toolchain references, or a Pages deployment path on `policy`.
