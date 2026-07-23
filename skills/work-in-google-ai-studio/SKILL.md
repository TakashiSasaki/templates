<!--
agent-policy-generated: true
source-skill: work-in-google-ai-studio
DO NOT EDIT DIRECTLY
-->
---
name: work-in-google-ai-studio
description: Implement and verify a bounded repository change in Google AI Studio Build mode, then hand off exported GitHub state for independent inspection.
---

# Work in Google AI Studio

Use this skill when Google AI Studio Build mode is the active coding workspace and GitHub revision, diff, or remote CI evidence must be confirmed outside that workspace.

1. Read the repository's root instructions, semantic configuration, project policy, relevant skills, and required central verification command.
2. Define one bounded user-visible outcome. Classify constraints as hard boundaries, preserved invariants, or planning boundaries before editing.
3. Establish a baseline sentinel using the files, symbols, routes, commands, configuration, and existing behavior required by the task. Do not treat the sentinel as proof of a Git revision.
4. Keep the task prompt compact. State the goal, sentinel, primary outcomes, task-specific hard boundaries, implementation scope, verification, export condition, and final report. Refer to repository instructions instead of repeating permanent policy or historical work logs.
5. Prefer a thin vertical slice. When an external integration is not authorized or configured, implement a runtime-neutral boundary, an explicit unconfigured state, and a development-only fixture or stub rather than inventing production connectivity.
6. Preserve existing behavior that the change does not intentionally replace. Do not stop solely because a harmless incidental file or minor planning-boundary deviation appears; evaluate its material effect.
7. Run focused checks while implementing, then run the repository's central verification command. Correct failures as needed without weakening tests or validators.
8. Report repository-local, preview-dependent, hardware-dependent, remote-CI, and independent-audit evidence separately. A pass in one layer is not a pass in another.
9. Inspect platform metadata, permissions, capability declarations, dependencies, scripts, secrets handling, and temporary files before export. Remove incidental transport or patch material that is not an explicit deliverable.
10. Request GitHub export only when the primary outcome works, central verification passes, and no hard boundary was crossed. Confirm the linked destination visible in the UI; do not assume arbitrary branch selection.
11. Do not guess the exported commit SHA, final branch state, GitHub Actions result, deployment state, or independent acceptance. Report unavailable facts as `NOT_OBSERVABLE`, unexecuted checks as `NOT_RUN`, and incomplete confirmation as `UNVERIFIED`.
12. Hand off the previous accepted revision, the export action, changed-file expectations, hard boundaries, and remaining environment checks to an external repository observer.

Stop dependent work when the baseline is materially incompatible, a hard boundary must be crossed, a semantic owner decision is unresolved, central verification remains failed, secrets would be exposed, or the export destination cannot be identified safely.

Use this final report structure unless the repository defines a stricter one:

- Outcome
- Files changed
- Repository-local verification
- Preview or hardware verification
- Hard boundaries
- GitHub export action
- Unobservable evidence
- Remaining work
