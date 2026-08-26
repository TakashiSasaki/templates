---
name: site-browser-regression-triage
description: Triage Site browser, PWA, mobile-layout, localized-chrome, and search-history regression failures against the exact built Pages artifact. Use when a Site PR browser check fails and the agent must distinguish generated-artifact, runtime, fixture, environment, or ownership problems before changing code.
---

# Site Browser Regression Triage

## Purpose

Provide a repeatable failure-analysis workflow for Site browser checks without guessing from source files or rebuilding a different artifact and calling that a reproduction.

The primary diagnostic object is the exact Pages artifact produced for the failing Site head. Source code, generated output, and observed browser runtime are separate layers and must not be conflated.

This skill diagnoses failures. It does not define browser feature semantics, PWA contracts, Zensical behavior, or merge acceptance. Current code, tests, workflow definitions, and focused checker scripts remain authoritative.

## Use when

Use this skill when:

- a Site pull request has reached browser/PWA checks and one of them fails, hangs, or becomes flaky;
- a browser-visible regression must be localized before deciding which source or test owns the repair;
- generated HTML/JavaScript, service-worker state, Shadow DOM, navigation behavior, locale chrome, viewport geometry, or search integration may differ from what source inspection suggests;
- an apparent browser failure may actually be a build artifact, test fixture, runner, dependency, or preflight problem.

When the repair changes the PR head, return to `site-pr-exact-head-acceptance` for a new exact-head acceptance pass.

## Do not use when

Do not use this skill to:

- repair a build/assembly failure that occurs before a Pages artifact is produced;
- infer canonical Composition or Policy semantics from browser symptoms;
- replace focused feature tests with broad end-to-end assertions;
- weaken timeouts, selectors, safety checks, or service-worker expectations merely to make a flaky run green;
- assume Zensical source templates describe the final browser DOM without checking the built artifact and runtime;
- treat a successful reproduction on a separately rebuilt artifact as proof about the artifact that actually failed.

If the failure is fundamentally a provider publication or Site mapping problem, switch to `site-publication-cutover`. If no browser diagnosis remains and the question is only merge readiness, use `site-pr-exact-head-acceptance`.

## Canonical authorities

Consult only what the failure requires:

- `.github/workflows/build-pages.yml` — current build/check topology and the artifact handed from build to browser checks;
- current checker scripts under `scripts/`, especially the checker named by the failing workflow step;
- current focused unit/regression tests under `tests/`;
- `FRESHNESS.md` for current PWA freshness semantics when a freshness lifecycle is involved;
- generated files in the exact Pages artifact being tested;
- actual Chromium runtime state observed by the failing checker or a focused reproduction;
- current Site-owned runtime assets under `assets/` when the diagnosed ownership boundary points there.

Historical PRs may explain why a regression exists, but they are not current executable authority.

## Inputs

Capture before changing code:

1. PR number and exact failing head SHA;
2. workflow run, job, and failing step name;
3. whether the build job succeeded and produced the Pages artifact;
4. artifact identity used by the browser check;
5. checker script invoked by the failing step;
6. failure message, traceback, timeout location, and any uploaded browser evidence;
7. current Site base SHA and whether the failure began before or after base drift.

Do not start by editing the first source file whose name resembles the failing feature.

## Procedure

### 1. Establish the failure layer

Classify where failure first occurs:

- **pre-artifact** — unit, assembly, Zensical build, metadata, link, or artifact-upload failure; this skill is not the primary workflow;
- **artifact acquisition** — check job cannot download or extract the artifact;
- **browser environment** — Playwright/controller/browser/font setup fails;
- **focused browser checker** — the checker starts and reports a semantic or timing failure;
- **evidence upload/cleanup** — semantic checks passed but artifact/evidence transport failed.

Do not debug application JavaScript until the failure is known to reach the application/browser layer.

### 2. Preserve the same-artifact principle

The Site PR browser job currently consumes the built Pages artifact from its build dependency. Treat that exact artifact as evidence.

When reproducing or inspecting:

- prefer the downloaded artifact from the failing run;
- preserve its exact generated HTML, JavaScript, service worker, manifest, metadata, and provider revisions;
- do not rebuild a different artifact and silently substitute it for the failed one;
- if a rebuild is necessary to test a proposed repair, label it as a new experiment, not reproduction evidence for the old failure.

A source checkout at the same SHA is necessary but not sufficient to prove generated-byte equivalence.

### 3. Follow source -> generated artifact -> browser runtime

Inspect the layers in that order, but stop as soon as evidence localizes the defect.

**Source** answers what the repository intended to generate.

**Generated artifact** answers what the failing build actually shipped to the browser checker.

**Browser runtime** answers what Chromium, service workers, navigation, events, layout, and Shadow DOM actually exposed.

Never skip directly from source assumptions to a runtime repair when the generated artifact can falsify the assumption.

### 4. Route by current focused checker

Use the checker corresponding to the workflow step. Current common routes include:

- mobile geometry/layout: `scripts/check_mobile_layout.py`;
- localized Glossary chrome: `scripts/check_glossary_locale_chrome.py`;
- PWA freshness lifecycle: `scripts/check_pwa_freshness.py`;
- localized PWA freshness chrome: `scripts/check_pwa_locale_chrome.py`;
- document/commit correlation: `scripts/check_pwa_commit_regressions.py`;
- slow-network/service-worker convergence: `scripts/check_pwa_slow_convergence.py`;
- freshness capability messaging: `scripts/check_pwa_capabilities.py`;
- search history core behavior: `scripts/check_search_history.py`;
- review-derived search-history edge cases: `scripts/check_search_history_review_regressions.py`.

Read the focused checker before broad application code. Its setup, fixture behavior, browser context, service-worker mode, selectors, navigation assumptions, and evidence outputs define what the failing CI step actually proves.

If workflow topology changes, follow the current workflow instead of this list and update this skill if the list has become materially stale.

### 5. Distinguish fixture/preflight failure from product failure

For a focused checker failure, determine whether the checker successfully reached the semantic action under test.

Examples of precondition failures include:

- expected generated file absent;
- local HTTP server cannot serve the route;
- browser cannot launch;
- required input/host never attaches;
- fixture does not exercise the intended service-worker or navigation branch;
- test preflight still expects a runtime asset that has moved ownership.

A preflight mismatch should be repaired at the test/fixture ownership boundary while preserving the semantic invariant. Do not modify product behavior merely to satisfy stale setup assumptions.

### 6. Treat browser structure as runtime evidence

For Zensical and other generated UI integrations:

- inspect the built Pages artifact first;
- inspect the actual browser DOM/Shadow DOM next;
- prefer semantic selectors and stable public behavior over minified/private class names;
- verify event type, bubbling/composed behavior, focusability/visibility, and navigation state in the browser when those properties matter;
- do not assume light DOM when the runtime uses an open Shadow Root;
- do not move upstream-specific assumptions across a Site adapter boundary without evidence that the adapter contract must change.

If the defect is specifically a recurring Zensical integration-design problem rather than generic triage, keep the repair focused and consider a future dedicated Zensical skill rather than expanding this skill indefinitely.

### 7. Classify timing and service-worker failures before increasing timeouts

When a check times out, identify what condition failed to converge:

- page load/readiness;
- service-worker registration/activation/control;
- cache update or freshness metadata propagation;
- network-delayed resource arrival;
- DOM/Shadow DOM attachment;
- search-result mutation;
- navigation completion;
- expected visual/layout stabilization.

Inspect the checker condition and runtime evidence. Increase a timeout only if the current contract allows the slower bound and evidence shows eventual correct convergence. A timeout increase must not hide a state machine that never reaches the required condition.

### 8. Repair the narrowest owning layer

Choose the repair based on evidence:

- generated output wrong because Site source is wrong -> repair Site source/generator;
- generated output correct but runtime behavior wrong -> repair Site runtime integration;
- upstream runtime behavior changed -> adjust the Site adapter/integration boundary, not unrelated Site code;
- checker fixture/preflight stale -> repair the checker while retaining the semantic assertion;
- runner/dependency setup broken -> repair workflow/environment setup without weakening product assertions;
- failure is nondeterministic -> first add bounded diagnostics or deterministic fixture control, then repair the demonstrated cause.

Do not combine unrelated browser cleanup with the focused repair.

### 9. Validate from narrow to broad

After a repair:

1. run or reason against the focused regression that failed;
2. run adjacent focused tests that share the changed ownership boundary;
3. rebuild the Pages artifact from the new exact head;
4. run the current same-artifact browser suite;
5. hand the resulting head back to `site-pr-exact-head-acceptance`.

Evidence from the old failing artifact remains useful for diagnosis but cannot accept the new head.

## Failure classification

Use one primary class before editing:

- **Generated-artifact regression** — build succeeds but emitted bytes/paths/metadata are semantically wrong.
- **Site runtime regression** — artifact is correct enough to load, but Site-owned browser behavior violates its contract.
- **Upstream runtime integration drift** — Zensical or another generated/runtime surface changed and the Site integration assumption is stale.
- **Fixture/preflight mismatch** — checker setup no longer reaches the intended semantic assertion.
- **Browser-environment failure** — Playwright, Chromium, fonts, or runner setup prevents the test from reaching product behavior.
- **PWA lifecycle/convergence defect** — service-worker/freshness state machine fails its required transition or bounded convergence.
- **Timing-only observation** — required state eventually becomes correct within an acceptable contract but the checker bound is demonstrably too tight.
- **Evidence/transport failure** — semantic checks pass but artifact/evidence upload or workflow plumbing fails.
- **Base-drift regression** — current Site base changed the relevant browser/runtime surface; reconcile before attributing the failure solely to the feature PR.

## Stop conditions

Do not claim the browser regression is diagnosed if:

- the exact failing head or failing step is unknown;
- the artifact actually tested is not identified when an artifact exists;
- a separately rebuilt artifact is being treated as the original failure evidence;
- the checker has not been read and its preconditions are unknown;
- source, generated artifact, and runtime observations contradict each other without resolution;
- a timeout was increased without proving eventual valid convergence;
- a selector/test was weakened without identifying the stable behavior it still proves;
- an upstream behavior assumption was made without inspecting the current built/runtime surface;
- base drift relevant to the failure remains unevaluated.

## Evidence to report

Report compactly:

- PR and exact failing head SHA;
- workflow/job/step and focused checker;
- whether the build artifact itself succeeded;
- artifact/runtime evidence inspected;
- failure classification;
- owning layer selected for repair;
- focused repair and tests changed;
- focused regression result;
- new exact head and broad same-artifact browser result;
- any remaining uncertainty or follow-up that should stay outside the current PR.
