---
name: site-pr-exact-head-acceptance
description: Establish reusable Site-specific exact-head scope, CI, browser/publication, and base-drift acceptance before handing final merge authorization to the repository merge gate.
---

# Site PR Exact-Head Acceptance

## Purpose

Provide a repeatable Site-specific acceptance workflow so scope, Site CI, browser/publication checks, and target-branch freshness refer to a defined PR head and Site target state, and so accepted evidence can be handed to the final merge gate without being collected again when its binding facts have not changed.

This skill does not authorize merge. After Site-specific acceptance is ready, hand final review and merge authorization to `.agents/skills/pr-merge-gate/SKILL.md`. Current code, tests, workflows, repository settings, and task-specific skills remain authoritative for what the PR is supposed to do.

## Use when

Use this skill when:

- a Site PR exists or is about to be opened and must establish Site-specific acceptance evidence;
- the PR head may change in response to tests or repairs;
- the `site` target may advance while work is in progress;
- prior successful Site CI evidence exists and its continued applicability must be established.

For provider publication changes, run `site-publication-cutover` first and use this skill for Site-specific PR acceptance. After it succeeds, use `pr-merge-gate` for the independent review and merge boundary.

## Do not use when

Do not use this skill as a substitute for:

- deciding provider publication mappings;
- diagnosing a specific browser/runtime failure in depth;
- authoring canonical Composition or Policy semantics;
- final independent-review evaluation or merge authorization;
- declaring success merely because some historical run was green;
- inventing extra polling, waiting, review, or validation requirements that current authority does not require.

Additional diagnostic work is allowed when concrete uncertainty exists, but diagnostic conservatism does not become a new Site acceptance requirement.

## Canonical authorities

Consult as needed:

- current PR metadata, diff, and commit-associated checks;
- current `site` branch head;
- `.github/workflows/` for present-day Site workflow topology and gates;
- current tests for semantic acceptance contracts;
- `MAINTENANCE.md` and `PUBLISHING.md` for Site responsibility and deployment boundaries;
- a task-specific repository skill when one matches the feature;
- `.agents/skills/pr-merge-gate/SKILL.md` for the separate final review/merge boundary and its canonical evidence-reuse rules.

Historical PR descriptions are evidence, not current authority.

## Inputs

Build one Site acceptance snapshot containing:

1. PR number and title;
2. PR base branch and base SHA used for scope evaluation;
3. exact PR head SHA accepted by Site checks;
4. observed current `site` head SHA and the base-drift decision;
5. intended semantic scope and effective changed-file set;
6. applicable Site checks and accepted exact-head CI evidence;
7. any scope-specific browser, publication, provider-lock, or deployment evidence;
8. the binding facts whose change would invalidate each evidence item.

A proposed-head change invalidates exact-head Site CI and head-bound scope evidence. A target-branch change invalidates the base-drift decision and requires impact evaluation, but does not automatically invalidate unrelated evidence. Do not discard the entire snapshot when only one binding changes.

## Workflow

### 1. Audit scope before trusting CI

Compare the PR against its evaluated base and list changed files. Confirm every changed file is intentional and every intended change is present. Remove accidental mode-only, generated-output, debug, or unrelated edits. Confirm the PR body describes the actual semantic scope.

Record the accepted base/head/effective-scope tuple. Recompute the effective diff only when a head change, target-branch movement, or another concrete scope signal can change that result. Prefer one coherent semantic commit when that is the established task boundary; do not manufacture commit churn solely for appearance.

### 2. Discover current Site acceptance gates

Use current workflow definitions and changed scope to determine the applicable Site checks for the accepted head. Do not hard-code a historical workflow/check list if the repository has changed.

For a normal Site change, determine whether the head is covered by the applicable build/unit/assembly, generated-site validation, provider-coexistence, publication-freshness, and browser/PWA checks. Scope-specific tests may add gates.

A successful run attached to an older head is historical evidence only. Once applicable exact-head Site checks are identified and accepted, retain that evidence with its binding facts; do not repeat discovery merely to make a still-valid result newer.

### 3. Use pending time for non-conflicting self-audit

While checks are pending, continue work that does not invalidate the head unnecessarily:

- inspect the exact diff for ownership and regression gaps;
- verify focused tests actually bind the intended contract rather than implementation trivia;
- check the current Site target for drift and assess only actual impact;
- prepare PR-body corrections that reflect already-committed behavior;
- inspect likely failure surfaces and current workflow boundaries;
- identify follow-up improvements that should remain separate from the current semantic change.

Do not create unrelated code changes merely to stay busy while CI runs. Do not turn optional self-audit observations into additional mandatory gates without repository authority.

### 4. Triage failures before changing code

For every failed check, first establish the exact SHA tested, failing job and step, whether the failure reaches the changed semantic surface, and whether it is a test-contract mismatch, product regression, base drift, fixture/environment problem, or unrelated infrastructure failure.

Do not weaken tests or safety boundaries until evidence shows the contract itself is wrong.

After a repair changes the PR head, invalidate the Site evidence bound to the former head and reacquire the affected scope and exact-head Site CI evidence. Do not automatically rerun unrelated diagnostics whose bindings did not change.

### 5. Handle Site target drift explicitly

Before Site acceptance handoff, establish the current `site` head. If it differs from the target state already evaluated:

1. inspect the intervening target diff;
2. classify overlap with the PR by files and semantic responsibility;
3. identify which Site acceptance evidence, if any, is invalidated by that movement;
4. synchronize, rebuild, or otherwise change the proposed head only when the impact evaluation or current repository authority requires it;
5. if synchronization creates a new proposed head, reacquire the exact-head Site evidence bound to the old head.

A conflict-free Git mergeability result does not by itself prove semantic freshness, but target movement also does not by itself require a new proposed head or a full acceptance restart.

### 6. Finalize the Site handoff snapshot

Before reporting Site acceptance ready, establish that the current PR head still equals the Site-accepted exact head and that current target movement, if any, has been evaluated. Validate the binding facts of the already accepted effective scope and Site CI/check evidence.

Do not unconditionally reacquire the effective diff, workflow definitions, or successful exact-head Site checks when their binding facts remain unchanged. Elapsed time alone does not make exact-head Site evidence stale unless current repository authority defines an explicit freshness limit.

Require:

- the exact Site-accepted PR head is current;
- target-branch movement is absent or its impact is dispositioned;
- effective scope remains bound to the accepted head/base context;
- all applicable Site checks for that exact head have acceptable evidence;
- the PR body does not materially misstate the accepted head or Site acceptance state.

If these conditions hold, report `SITE_ACCEPTANCE_READY_FOR_MERGE_GATE` together with the Site handoff snapshot. This skill does not authorize merge or report `MERGE_ALLOWED`.

Load `.agents/skills/pr-merge-gate/SKILL.md`. The merge gate must reuse the Site-specific scope and CI evidence from the handoff snapshot while its binding facts remain valid; it must not unconditionally reacquire Site-specific evidence simply because control moved between skills. If generic final live state exposes a concrete invalidation signal, return here only for the affected Site evidence.

### 7. Verify Site-specific state after merge when relevant

After `pr-merge-gate` confirms the merge result, resume Site-specific follow-up only when the task requires it:

- for publication/deployment changes, inspect the relevant post-merge/deploy evidence rather than assuming merge equals publication success;
- verify public provenance or other Site-owned deployment state when it is an acceptance requirement;
- report remaining follow-up separately from the merge result.

## Exact-head rules

- Green CI on SHA A is not acceptance of SHA B.
- A rerun of a job must still be associated with the intended exact commit and artifact.
- Never cite a branch name where an immutable SHA is required for Site acceptance evidence.
- Accepted Site evidence is reusable while its binding facts remain unchanged; elapsed time alone is not an invalidation signal.
- Do not hide a failure by deleting or weakening a regression test unless the current canonical contract independently proves that test invalid.
- Site acceptance never substitutes for the independent-review requirements of `pr-merge-gate`.
- Keep acceptance evidence compact: use current accepted checks and direct artifacts instead of reconstructing the entire historical PR timeline.

## Failure classification

Before repairing, classify a blocker as one of:

- **Semantic regression** — implementation violates the intended current contract.
- **Regression-test mismatch** — test still encodes a moved/retired responsibility while behavior is correct; update the test at the new authority boundary and preserve the invariant.
- **Base drift** — current Site changed underneath the PR; evaluate impact and reconcile only affected acceptance evidence.
- **Workflow/environment failure** — runner, dependency, artifact transport, or external service problem; prove it is unrelated before treating it as non-semantic.
- **PR metadata staleness** — body/evidence points to old SHAs or runs; correct metadata without pretending it changes code acceptance.
- **Merge-gate blocker** — independent review, review threads, final live state, or mergeability is not satisfied; return to `pr-merge-gate` rather than weakening Site acceptance.

## Stop conditions

Do not report `SITE_ACCEPTANCE_READY_FOR_MERGE_GATE` if:

- any applicable current-head Site check lacks acceptable evidence;
- current Site target movement has not been evaluated;
- intended scope and effective diff disagree;
- the Site-accepted exact head differs from the current head;
- a binding needed to establish continued validity is unknown or invalid;
- the PR body materially misstates the exact revision or Site evidence being accepted.

Never report final merge readiness from this skill. `pr-merge-gate` owns that decision and must itself remain blocked when independent exact-head review is missing, pending, or stale.

Do not create additional stop conditions solely because a stricter local procedure feels safer. Diagnostic work does not become a mandatory acceptance condition without current repository authority.

## Evidence to report

Report:

- PR number;
- Site handoff snapshot identity: evaluated base/target state and exact accepted PR head;
- intended changed files/semantic scope;
- accepted exact-head Site CI/check summary and its binding facts;
- base-drift decision;
- any concrete invalidation signals and selectively reacquired Site evidence;
- `SITE_ACCEPTANCE_READY_FOR_MERGE_GATE` or the specific Site blocker;
- after handoff, refer to the merge gate's separate review/merge evidence rather than duplicating it;
- post-merge publication/deployment status when relevant.
