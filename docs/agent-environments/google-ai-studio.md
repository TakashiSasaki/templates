---
description: Standard operation for editing and verifying a repository in Google AI Studio Build mode and exporting changes to GitHub.
---

# Google AI Studio Build mode operation

This page defines the standard operating model for editing an existing repository in Google AI Studio Build mode, verifying it in the workspace, and exporting changes to GitHub.

It is non-normative guidance for the Google AI Studio execution environment. Product-repository-specific branches, databases, deployment, security, and verification commands are defined by each repository's instructions and project policy.

## Responsibility boundary

Google AI Studio can import a project from GitHub, edit multiple files, show a live preview, and export changes to a GitHub repository. The workspace state observable during the task and the GitHub repository state after export are separate evidence layers.

The standard responsibility split is:

| Actor | Responsibility |
|---|---|
| Google AI Studio | inspect and edit the workspace, run repository-local commands, use live preview, perform repository-local verification, request GitHub export |
| External repository observer | identify the exported revision, compare it with the previous baseline, inspect remote CI, permission/dependency/metadata changes, and determine final acceptance |

Do not infer a commit SHA, remote branch state, GitHub Actions result, or external audit result that AI Studio cannot observe directly. Report unavailable evidence as `NOT_OBSERVABLE`, unexecuted checks as `NOT_RUN`, and incomplete verification as `UNVERIFIED`.

## Baseline sentinel at task start

When the Git revision cannot be inspected directly, check the workspace capabilities on which the next task depends and use them as baseline sentinels.

- required files exist;
- required symbols, routes, commands, and configuration exist;
- important user-visible behavior established by earlier work exists; and
- the repository-defined central verification command exists.

A baseline sentinel is not a substitute for commit identity. Do not stop work because of excessive sentinels such as display wording, file ordering, or minor style differences that the next task does not depend on.

Report a material baseline mismatch and stop dependent work. Work that is independent and safe may continue despite a minor mismatch.

## Task prompt structure

A task prompt for AI Studio should be a delta instruction that assumes the repository's `AGENTS.md`, project policy, and applicable skills. Do not restate permanent policy or detailed history on every task.

Use this standard structure:

```text
Goal
Baseline sentinel
Primary outcomes
Hard boundaries
Implementation scope
Verification
Export condition
Final report
```

Classify constraints into three categories:

| Category | Meaning |
|---|---|
| Hard boundary | Safety, data, or authorization boundary that requires stopping if compliance would otherwise be violated |
| Preserved invariant | Existing behavior, compatibility, or data meaning that must remain true after the change |
| Planning boundary | Expected change scope; deviations must be explained but are not automatically failures when they have no material impact |

Keep only task-specific outcomes, boundaries, scope, and verification in the prompt. Omit background prose, previous work details, detailed external-audit procedure, and general rules already present in repository instructions.

## Implementation units

Split a large restoration or integration into usable thin vertical slices. Prefer each unit, even a small one, to connect input through to a user-visible result.

When an external service is not yet available, complete boundaries such as:

- runtime-neutral model;
- provider or adapter interface;
- explicit unconfigured state;
- development-only fixture or stub;
- distinct loading, success, negative-result, and error states; and
- cancellation and stale-result protection.

`unconfigured` is different from a negative result returned by a service query. Do not display a domain result such as `not found` when no query was performed.

## Verification

Separate verification evidence into layers:

| Layer | Examples |
|---|---|
| Repository-local | typecheck, build, unit tests, schema validators, repository central verification |
| Preview-dependent | browser navigation, reload, UI interaction, AI Studio preview behavior |
| Hardware-dependent | camera, microphone, NFC, Bluetooth, USB, serial |
| Remote | GitHub Actions, deployment, external services |
| Independent audit | exported-revision diff, regression inspection, external hard-boundary confirmation |

Do not use a PASS in one layer as evidence that another layer passed. For example, a successful build does not prove browser reload behavior, hardware APIs, or remote CI.

When central verification fails, fix the cause and rerun it. Do not make the number of corrective iterations an artificial completion criterion; prioritize the working outcome, safety boundaries, and verification results.

## GitHub export

Request GitHub export when repository-local verification passes, the primary outcome is achieved, and there is no hard-boundary violation.

Before export, confirm that:

- temporary downloads, archives, extraction trees, and patch scripts are absent;
- dependency, permission, and platform-capability additions are intentional;
- no secrets or credentials were written into source;
- generated files were not edited directly; and
- the repository-specified export destination agrees with the current integration target.

Do not assume AI Studio can export to an arbitrary branch. If branch control is required and the UI cannot select the target, use ZIP export or hand off to a complete Git environment.

## External audit after export

External audit should focus on the difference between the previously accepted revision and the exported revision.

1. Identify the exported revision.
2. Obtain the diff and changed files against the previously accepted revision.
3. Classify changes as `intended`, `derived`, `incidental but harmless`, or `unexplained and material`.
4. Confirm the primary outcome and preserved invariants.
5. Inspect hard boundaries, dependencies, permissions, metadata, and temporary artifacts.
6. Confirm that remote CI applies to the current revision.
7. Decide acceptance, follow-up, or an explicit rebaseline.

An unexpected documentation or metadata file is not an automatic failure. Evaluate its effect on runtime, security, data boundaries, dependencies, and future agent behavior.

## `metadata.json` and platform-generated changes

For web applications created or edited in Google AI Studio, `metadata.json` can declare camera, microphone, geolocation, Bluetooth, and similar permission requests in `requestFramePermissions`. After export, inspect at least:

- `requestFramePermissions`;
- capability declarations;
- metadata related to secrets or server-side features;
- dependencies and scripts; and
- root-level temporary files.

Permission or capability additions require a necessity review. The fact that a permission was added, or that AI Studio generated it, is not by itself a justification.

## External artifacts

When historical source, archives, reference bundles, or similar artifacts are supplied to AI Studio, apply the `external-artifact-intake` profile.

- prefer URLs containing immutable revisions over mutable branch URLs;
- for corrected artifacts, use a new artifact name or revision rather than replacing the same path;
- separate digest verification, archive integrity, and repository-authoritative validation;
- separate artifact-dependent from artifact-independent work; and
- do not implicitly install or activate reference-only material.

## Completion report

Keep the completion report short and include only facts needed by the external audit.

```text
Outcome
Files changed
Repository-local verification
Preview or hardware verification
Hard boundaries
GitHub export action
Unobservable evidence
Remaining work
```

Use these standard status terms:

```text
PASS
FAIL
PARTIAL
SKIP
NOT_RUN
NOT_OBSERVABLE
UNVERIFIED
```

Distinguish implemented, executed, verified, and inferred states. Do not report unobservable remote state as successful.

## References

- [Build apps in Google AI Studio](https://ai.google.dev/gemini-api/docs/aistudio-build-mode)
- [Develop Full-Stack Apps in Google AI Studio](https://ai.google.dev/gemini-api/docs/aistudio-fullstack)
