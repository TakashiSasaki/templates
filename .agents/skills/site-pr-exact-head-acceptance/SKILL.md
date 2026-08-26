---
name: site-pr-exact-head-acceptance
description: Establish Site-specific exact-head scope, CI, browser/publication, and base-drift acceptance before handing final merge authorization to the repository merge gate.
---

# Site PR Exact-Head Acceptance

## Purpose

Provide a repeatable Site-specific acceptance workflow so scope, Site CI, browser/publication checks, and target-branch freshness always refer to the current PR head and current Site base.

This skill does not authorize merge. After Site-specific acceptance is ready, hand final review and merge authorization to `.agents/skills/pr-merge-gate/SKILL.md`. Current code, tests, workflows, repository settings, and task-specific skills remain authoritative for what the PR is supposed to do.

## Use when

Use this skill when:

- a Site PR exists or is about to be opened and must establish Site-specific acceptance evidence;
- the PR head may change in response to tests or repairs;
- the `site` base may advance while work is in progress;
- prior successful Site CI evidence exists and must be checked for staleness.

For provider publication changes, run `site-publication-cutover` first and use this skill for Site-specific PR acceptance. After it succeeds, use `pr-merge-gate` for the independent review and merge boundary.

## Do not use when

Do not use this skill as a substitute for:

- deciding provider publication mappings;
- diagnosing a specific browser/runtime failure in depth;
- authoring canonical Composition or Policy semantics;
- final independent-review evaluation or merge authorization;
- declaring success merely because some historical run was green.

## Canonical authorities

Consult as needed:

- current PR metadata, diff, and commit-associated checks;
- current `site` branch head;
- `.github/workflows/` for present-day Site workflow topology and gates;
- current tests for semantic acceptance contracts;
- `MAINTENANCE.md` and `PUBLISHING.md` for Site responsibility and deployment boundaries;
- a task-specific repository skill when one matches the feature;
- `.agents/skills/pr-merge-gate/SKILL.md` for the separate final review/merge boundary.

Historical PR descriptions are evidence, not current authority.

## Inputs

Record at the start of an acceptance pass:

1. PR number and title;
2. current PR base branch and base SHA;
3. current PR exact head SHA;
4. current `site` head SHA;
5. intended semantic scope and expected changed-file set;
6. current commit-associated Site check runs and scope-specific required checks.

Repeat this snapshot whenever the PR head changes.

## Workflow

### 1. Audit scope before trusting CI

- Compare the PR against its base and list changed files.
- Confirm every changed file is intentional and every intended change is present.
- Remove accidental mode-only, generated-output, debug, or unrelated edits.
- Confirm the PR body still describes the actual scope, base, head, and Site acceptance evidence.
- Prefer one coherent semantic commit when that is the established task boundary; do not manufacture commit churn solely for appearance.

### 2. Discover current Site acceptance gates

Use current workflow definitions and commit-associated runs. Do not hard-code a historical workflow/check list if the repository has changed.

For a normal Site change, determine whether the current head is covered by the applicable build/unit/assembly, generated-site validation, provider-coexistence, publication-freshness, and browser/PWA checks. Scope-specific tests may add gates.

A successful run attached to an older head is historical evidence only.

### 3. Use pending time for non-conflicting self-audit

While checks are pending, continue work that does not invalidate the head unnecessarily:

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

After any repair changes the PR head, discard prior Site acceptance status and start a new exact-head pass.

### 5. Handle Site base drift explicitly

Before declaring Site acceptance ready for handoff, compare current `site` head with the PR base.

If `site` has advanced:

1. inspect the intervening base diff;
2. classify overlap with the PR by files and semantic responsibility;
3. determine whether the PR must be rebuilt, rebased, or otherwise synchronized with the current Site head;
4. preserve already-tested feature content only when it remains semantically valid on the new base;
5. re-run Site tests and exact-head CI after a new head is created.

A conflict-free Git mergeability result does not by itself prove that a stale base is semantically current.

### 6. Record Site acceptance and hand off

Refresh the Site-specific evidence and require:

- PR exact head SHA is known and unchanged since the Site evidence was collected;
- current Site base/drift has been evaluated;
- effective diff contains only intended changes;
- all current Site checks applicable to that exact head are successful or explicitly and justifiably non-applicable;
- PR body does not claim stale Site SHAs, run IDs, measurements, or validation status.

If these conditions hold, report `SITE_ACCEPTANCE_READY_FOR_MERGE_GATE`; do not report `MERGE_ALLOWED` or merge-ready. Load `.agents/skills/pr-merge-gate/SKILL.md` and perform its independent exact-head review, review-thread, final live-state, mergeability, and `expected_head_sha` checks.

If the merge gate or a review repair changes the PR head, return here when the change can affect Site-specific acceptance and reacquire the necessary exact-head Site evidence before attempting the merge gate again.

### 7. Verify Site-specific state after merge when relevant

After `pr-merge-gate` confirms the merge result, resume Site-specific follow-up only when the task requires it:

- for publication/deployment changes, inspect the relevant post-merge/deploy evidence rather than assuming merge equals publication success;
- verify public provenance or other Site-owned deployment state when it is an acceptance requirement;
- report remaining follow-up separately from the merge result.

## Exact-head rules

- Green CI on SHA A is not acceptance of SHA B.
- A rerun of a job must still be associated with the intended exact commit and artifact.
- Never cite a branch name where an immutable SHA is required for Site acceptance evidence.
- Do not hide a failure by deleting or weakening a regression test unless the current canonical contract independently proves that test invalid.
- Site acceptance never substitutes for the independent-review requirements of `pr-merge-gate`.
- Keep acceptance evidence compact: use current checks and direct artifacts instead of reconstructing the entire historical PR timeline.

## Failure classification

Before repairing, classify a blocker as one of:

- **Semantic regression** — implementation violates the intended current contract.
- **Regression-test mismatch** — test still encodes a moved/retired responsibility while behavior is correct; update the test at the new authority boundary and preserve the invariant.
- **Base drift** — current Site changed underneath the PR; reconcile before trusting old evidence.
- **Workflow/environment failure** — runner, dependency, artifact transport, or external service problem; prove it is unrelated before treating it as non-semantic.
- **PR metadata staleness** — body/evidence points to old SHAs or runs; correct metadata without pretending it changes code acceptance.
- **Merge-gate blocker** — independent review, review threads, final live state, or mergeability is not satisfied; return to `pr-merge-gate` rather than weakening Site acceptance.

## Stop conditions

Do not report `SITE_ACCEPTANCE_READY_FOR_MERGE_GATE` if:

- any required current-head Site check is missing, pending, failed, or known stale without an explicit current-policy reason;
- current Site base drift has not been evaluated;
- intended scope and effective diff disagree;
- the final Site-tested head differs from the current head;
- the PR body materially misstates the exact revision or Site evidence being accepted.

Never report final merge readiness from this skill. `pr-merge-gate` owns that decision and must itself remain blocked when independent exact-head review is missing, pending, or stale.

## Evidence to report

Report:

- PR number;
- current Site base/head relationship;
- exact Site-accepted PR head SHA;
- intended changed files/semantic scope;
- current-head Site CI/check summary;
- base-drift decision;
- `SITE_ACCEPTANCE_READY_FOR_MERGE_GATE` or the specific Site blocker;
- after handoff, refer to the merge gate's separate review/merge evidence rather than duplicating or weakening it;
- post-merge publication/deployment status when relevant.
