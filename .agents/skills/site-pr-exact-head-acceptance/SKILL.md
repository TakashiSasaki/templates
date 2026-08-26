---
name: site-pr-exact-head-acceptance
description: Drive a Site pull request from implementation through exact-head CI, review, base-drift handling, and merge readiness. Use when a Site PR must be completed safely, especially when checks or review take time and stale successful results must not be mistaken for acceptance of the current head.
---

# Site PR Exact-Head Acceptance

## Purpose

Provide a repeatable merge-readiness workflow for `site` pull requests so acceptance evidence always refers to the current PR head and current Site base.

This skill does not define feature semantics. Current code, tests, workflows, repository settings, and task-specific skills remain authoritative for what the PR is supposed to do.

## Use when

Use this skill when:

- a Site PR exists or is about to be opened and must be carried through CI/review to merge readiness;
- the PR head may change in response to tests or review;
- the `site` base may advance while work is in progress;
- prior successful CI/review evidence exists and must be checked for staleness.

For provider publication changes, run `site-publication-cutover` first and use this skill for the final PR lifecycle.

## Do not use when

Do not use this skill as a substitute for:

- deciding provider publication mappings;
- diagnosing a specific browser/runtime failure in depth;
- authoring canonical Composition or Policy semantics;
- declaring success merely because some historical run was green.

## Canonical authorities

Consult as needed:

- current PR metadata, diff, reviews, review threads, and commit-associated checks;
- current `site` branch head;
- `.github/workflows/` for present-day workflow topology and gates;
- current tests for semantic acceptance contracts;
- `MAINTENANCE.md` and `PUBLISHING.md` for Site responsibility and deployment boundaries;
- a task-specific repository skill when one matches the feature.

Historical PR descriptions are evidence, not current authority.

## Inputs

Record at the start of an acceptance pass:

1. PR number and title;
2. current PR base branch and base SHA;
3. current PR exact head SHA;
4. current `site` head SHA;
5. intended semantic scope and expected changed-file set;
6. current reviews, unresolved threads, and commit-associated check runs.

Repeat this snapshot whenever the PR head changes.

## Workflow

### 1. Audit scope before trusting CI

- Compare the PR against its base and list changed files.
- Confirm every changed file is intentional and every intended change is present.
- Remove accidental mode-only, generated-output, debug, or unrelated edits.
- Confirm the PR body still describes the actual scope, base, head, and acceptance evidence.
- Prefer one coherent semantic commit when that is the established task boundary; do not manufacture commit churn solely for appearance.

### 2. Discover current acceptance gates

Use current workflow definitions and commit-associated runs. Do not hard-code a historical workflow/check list if the repository has changed.

For a normal Site change, determine whether the current head is covered by the applicable build/unit/assembly, generated-site validation, provider-coexistence, publication-freshness, and browser/PWA checks. Scope-specific tests may add gates.

A successful run attached to an older head is historical evidence only.

### 3. Use pending time for non-conflicting self-audit

While checks or review are pending, continue work that does not invalidate the head unnecessarily:

- inspect the exact diff for ownership and regression gaps;
- verify focused tests actually bind the intended contract rather than implementation trivia;
- check current Site base for drift;
- prepare PR-body corrections that reflect already-committed behavior;
- inspect likely failure surfaces and current workflow boundaries;
- verify no stale SHA/check references remain in the PR description;
- identify follow-up improvements that should remain separate from the current semantic change.

Do not create unrelated code changes merely to stay busy while CI runs.

### 4. Triage failures before changing code

For every failed check, first establish:

- the exact SHA tested;
- failing job and step;
- whether the failure reproduces the changed semantic surface;
- whether it is a test-contract mismatch, product regression, base drift, fixture/environment problem, or unrelated infrastructure failure.

Do not weaken tests or safety boundaries until evidence shows the contract itself is wrong.

After any repair changes the PR head, discard prior final-acceptance status and start a new exact-head pass.

### 5. Evaluate review against the exact head

- Read submitted reviews and inline review threads.
- Resolve findings by evidence or code changes, not by summary assertion.
- Confirm there are no unresolved material threads.
- Record which head SHA was actually reviewed.

If the PR head changes after the relied-upon review, treat that review as evidence about the older revision. Re-run the required review/acceptance process for the new head according to the current project policy.

### 6. Handle base drift explicitly

Immediately before final acceptance, compare current `site` head with the PR base.

If `site` has advanced:

1. inspect the intervening base diff;
2. classify overlap with the PR by files and semantic responsibility;
3. determine whether the PR must be rebased or re-squashed onto the current Site head;
4. preserve already-reviewed feature content only when it remains semantically valid on the new base;
5. re-run tests, exact-head CI, and review after the new head is created.

A conflict-free Git mergeability result does not by itself prove that a stale base is semantically current.

### 7. Apply the final merge gate

Immediately before merge, refresh all state and require:

- PR exact head SHA is known and unchanged since the final evidence was collected;
- current Site base/drift has been evaluated;
- effective diff contains only intended changes;
- all current required checks applicable to that exact head are successful or explicitly and justifiably non-applicable;
- no material review finding or inline thread remains unresolved;
- relied-upon review applies to the exact head required by project policy;
- PR is mergeable under current repository settings;
- PR body does not claim stale SHAs, run IDs, measurements, or validation status.

If any item changes, the gate is open again.

### 8. Verify after merge

After merge:

- confirm the PR is actually merged and record the merge commit;
- confirm `site` points to the expected merged result or a later intentional commit;
- when the task affects publication/deployment, inspect the relevant post-merge/deploy evidence rather than assuming merge equals publication success;
- report any remaining follow-up separately.

## Exact-head rules

- Green CI on SHA A is not acceptance of SHA B.
- Review of SHA A is not automatically review of changed SHA B.
- A rerun of a job must still be associated with the intended exact commit and artifact.
- Never cite a branch name where an immutable SHA is required for acceptance evidence.
- Do not merge while a known material review thread is merely waiting to be answered.
- Do not hide a failure by deleting or weakening a regression test unless the current canonical contract independently proves that test invalid.
- Keep acceptance evidence compact: use current checks and direct artifacts instead of reconstructing the entire historical PR timeline.

## Failure classification

Before repairing, classify a blocker as one of:

- **Semantic regression** — implementation violates the intended current contract.
- **Regression-test mismatch** — test still encodes a moved/retired responsibility while behavior is correct; update the test at the new authority boundary and preserve the invariant.
- **Base drift** — current Site changed underneath the PR; reconcile before trusting old evidence.
- **Review finding** — code or evidence is incomplete; address and revalidate the resulting head.
- **Workflow/environment failure** — runner, dependency, artifact transport, or external service problem; prove it is unrelated before treating it as non-semantic.
- **PR metadata staleness** — body/evidence points to old SHAs or runs; correct metadata without pretending it changes code acceptance.

## Stop conditions

Do not report merge readiness if:

- any required current-head check is missing, pending, failed, or known stale without an explicit current-policy reason;
- current base drift has not been evaluated;
- intended scope and effective diff disagree;
- a material review finding is unresolved;
- the final reviewed/tested head differs from the current head;
- mergeability or repository gate state is unknown;
- the PR body materially misstates the exact revision being accepted.

## Evidence to report

Report:

- PR number;
- current Site base/head relationship;
- exact accepted PR head SHA;
- intended changed files/semantic scope;
- current-head CI/check summary;
- review and unresolved-thread status;
- base-drift decision;
- mergeability and merge result;
- post-merge publication/deployment status when relevant.
