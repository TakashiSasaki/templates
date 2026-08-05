# Policy toolkit readiness and completion roadmap

This document defines how the `policy` branch reaches a defensible completion state without
conflating branch-local toolkit readiness with migration of the former
`TakashiSasaki/agent-policy` ecosystem.

The criteria are durable. A later audit records evidence against them at one exact candidate
commit. Passing selected tests or having the expected files present is not, by itself, a
completion declaration.

## Completion states

The work advances through four distinct states:

1. **Development baseline**: core capabilities exist, but no full cross-cutting audit has been
   accepted.
2. **Candidate ready**: one exact candidate commit satisfies every policy-toolkit readiness gate
   and has a completed audit record.
3. **Policy toolkit complete**: the candidate has passed review and CI, and any stable release
   movement has been performed through the separate candidate-and-promotion lifecycle.
4. **Ecosystem migration complete**: all active consumers use the new stable full-SHA source and
   the former repository has been deprecated, had active automation stopped, and been archived.

A policy-toolkit-complete declaration does not imply ecosystem migration completion.

## Policy toolkit completion

A candidate may be declared policy-toolkit complete only when all gates below pass at the same
40-character lowercase Git commit SHA.

| Gate | Required condition | Existing evidence anchors |
| --- | --- | --- |
| `scope` | The shared toolkit remains application-type independent and excludes product architecture. | `docs/adr/0003-application-neutral-policy-scope.md`, `tests/test_application_neutral_scope.py` |
| `configuration` | `.agent-policy.yml` remains the sole semantic configuration entry point and validates deterministically. | `docs/configuration.md`, `tests/test_config.py`, `tests/test_config_driven_check.py` |
| `generation` | `init`, `validate`, `render`, and `check` produce deterministic instructions, skills, workflows, and locks. | `docs/cli.md`, `tests/test_init_render_check.py`, `tests/test_generate_repository_preview.py` |
| `adoption` | Inspection, preparation, preview, and explicit transactional finalization preserve the documented safety boundary. | `docs/adoption.md`, `docs/adr/0002-repository-adoption.md`, `tests/test_adoption_*.py` |
| `bootstrap` | The integrated trust seed executes only the stable full SHA and exposes no adoption-finalization route. | `docs/bootstrap-model.md`, `docs/adr/0004-integrated-bootstrap-skill.md`, `tests/test_bootstrap_*.py` |
| `release` | The stable descriptor, bootstrap manifest, verifier lock, and contract versions remain synchronized through two-step promotion. | `docs/release-lifecycle.md`, `release/toolchain.json`, `tests/test_release_lifecycle.py` |
| `identity` | Executable and generated identities consistently use `TakashiSasaki/templates` and `policy`. | `tests/test_repository_identity.py`, `tests/test_toolchain_repository_identity.py` |
| `ci` | Policy CI is reproducible on its fixed baseline, neutralizes external Python and pip inputs, and verifies the installed distribution set. | `.github/workflows/ci.yml`, `tests/test_ci_reproducibility.py`, `tests/test_verify_ci_environment.py` |
| `documentation` | Documentation builds strictly without any Pages upload or deployment authority on `policy`. | `.github/workflows/pages.yml`, `docs/documentation-publication.md`, `tests/test_documentation_publication.py` |
| `consistency` | README, architecture, ADRs, operational guides, release metadata, workflows, and tests do not contradict one another. | the completed readiness audit and the full test suite |

The existing anchors identify where evidence is expected; they do not pre-approve a gate. The
audit must inspect behavior and cross-document consistency rather than merely confirm filenames.

## Completion audit record

The final audit must be committed as `docs/policy-readiness-audit.md`. It must contain:

- the audited candidate's 40-character lowercase Git commit SHA;
- the audit date and reviewer or reviewing agent;
- an explicit pass or fail result for every gate in this document;
- commands executed and their results;
- successful `Policy CI` and `Policy documentation build` run identifiers for the candidate;
- review status, unresolved review-thread count, and any accepted exceptions;
- confirmation that the candidate is not referenced through a mutable branch or tag;
- the stable promotion decision and, when promotion is required, the later promotion commit.

The audit record must not claim completion while any gate is failed, unknown, waived without an
explicit accepted decision, or supported only by a mutable ref.

## Ecosystem migration completion

Ecosystem migration is a separate track and must not block accurate reporting of branch-local
toolkit readiness. It is complete only when all of the following are true:

1. Active consumers that reference `TakashiSasaki/agent-policy` or rewritten pre-migration
   revisions have been inventoried.
2. Every active consumer has moved to the reviewed stable full SHA in
   `TakashiSasaki/templates` and regenerated all derived artifacts from that same revision.
3. The former repository contains a deprecation notice pointing to the new authority.
4. Active automation in the former repository has been disabled.
5. Existing full-SHA objects and historical links remain addressable.
6. The former repository has been archived after consumer migration is verified.

The former repository must not be deleted. Publication of selected policy documentation, when
desired, is coordinated through the unrelated `skill` and `site` branches. The `policy` workflow
remains build-only.

## Roadmap

### Phase 1: establish the completion contract

- Add this readiness definition to the maintained documentation.
- Link it from the README and documentation navigation.
- Remove contradictory migration wording.
- Add regression tests for the toolkit/ecosystem boundary and Pages ownership.

### Phase 2: execute the cross-cutting audit

- Select one candidate full SHA after Phase 1 is merged.
- Evaluate every readiness gate against code, generated artifacts, workflows, and documentation.
- Record missing evidence, contradictions, and defects without treating prior migration work as
  automatically passing.
- Open focused corrective changes for each material gap.

### Phase 3: close gaps and freeze the toolkit baseline

- Merge corrective changes only after tests, strict documentation build, and review pass.
- Re-run the complete audit on one exact candidate commit.
- Commit `docs/policy-readiness-audit.md` with all required evidence.
- Declare policy-toolkit completion only after the audit record itself is reviewed and CI passes.

### Phase 4: promote the stable executable when required

- Keep the audited candidate commit unchanged.
- In a later promotion change, update `release/toolchain.json`, the bootstrap manifest, and the
  stable verifier lock as required.
- Verify that the candidate is a strict ancestor of the promotion commit.
- Update consumers only through separate reviewed repository changes.

### Phase 5: complete ecosystem migration

- Inventory and migrate active consumers.
- Add the former-repository deprecation notice and stop its active automation.
- Verify that no active consumer remains on the former source.
- Archive, but do not delete, the former repository.

## Explicit non-goals

Completion work must not introduce application-category profiles, Web surface or route contracts,
framework or deployment topology decisions, a generic arbitrary-command executor, mutable
toolchain references, or a Pages deployment path on `policy`.
