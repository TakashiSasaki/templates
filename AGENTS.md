# Repository agent instructions

This file is a routing index for repository-local Agent Skills. It does not replace the current code, tests, workflows, or canonical maintenance documentation.

When working on the `site` authority, load the smallest matching skill from `.agents/skills/` before reconstructing a workflow from repository history.

## Skill routing

- Provider publication update after a reviewed `composition` or `policy` merge: `.agents/skills/site-publication-cutover/SKILL.md`
- Site-specific pull-request scope, exact-head CI, browser/publication acceptance, and base-drift preparation: `.agents/skills/site-pr-exact-head-acceptance/SKILL.md`
- Final merge authorization for every Site pull request: `.agents/skills/pr-merge-gate/SKILL.md`
- Site browser/PWA/mobile/search regression failure triage: `.agents/skills/site-browser-regression-triage/SKILL.md`

If more than one skill applies, use only the minimal set needed and follow them in dependency order. A normal Site PR completion path is task-specific work -> `site-pr-exact-head-acceptance` -> `pr-merge-gate`. A publication cutover normally uses `site-publication-cutover` first, then Site acceptance, then the merge gate. A browser failure encountered during Site acceptance may temporarily use `site-browser-regression-triage`, then return to Site acceptance after the repair creates a new head.

`site-pr-exact-head-acceptance` establishes Site-specific acceptance evidence but never authorizes merge. Before declaring a Site PR merge-ready, merging it, or completing a task whose final action is a merge, load `pr-merge-gate`. Green CI and `reviews = 0` must never be interpreted as a clean review state.

## Loading discipline

1. Read the matching `SKILL.md` first.
2. Follow only the canonical references needed for the current task; do not bulk-read historical pull requests as a substitute for current repository state.
3. Prefer current code, tests, workflow definitions, `MAINTENANCE.md`, and `PUBLISHING.md` over historical PR descriptions.
4. Use repository history only when current sources leave a material ambiguity unresolved.
5. If a skill conflicts with current canonical documentation or executable contracts, follow the canonical source and update the stale skill.
6. If the PR head changes, discard final acceptance for the previous head. Re-run Site acceptance as needed, then run the merge gate for the new exact head.

## Authority boundary

The active canonical authorities are `site`, `composition`, and `policy`. The external provider set published by Site is exactly `composition` and `policy`. Skill and Webapp remain reader/artifact concepts under Composition; they are not independent provider branches.

Site owns integration, reader-facing information architecture, exact provider locks, publication assembly, validation, provenance, PWA integration, and Pages deployment. Repository-local Agent Skills orchestrate maintenance and merge acceptance; they do not become a second semantic authority. Do not move provider-owned Composition or Policy semantics into Site merely to complete an integration task.
