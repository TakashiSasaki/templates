# Repository agent instructions

This file is a routing index for repository-local Agent Skills. It does not replace the current code, tests, workflows, or canonical maintenance documentation.

When working on the `site` authority, load the smallest matching skill from `.agents/skills/` before reconstructing a workflow from repository history.

## Skill routing

- Provider publication update after a reviewed `composition` or `policy` merge: `.agents/skills/site-publication-cutover/SKILL.md`
- Site pull-request completion, exact-head CI/review acceptance, base-drift handling, and merge readiness: `.agents/skills/site-pr-exact-head-acceptance/SKILL.md`
- Site browser/PWA/mobile/search regression failure triage: `.agents/skills/site-browser-regression-triage/SKILL.md`

If more than one skill applies, use only the minimal set needed and follow them in dependency order. A publication cutover normally uses `site-publication-cutover` first and hands final PR acceptance to `site-pr-exact-head-acceptance`. A browser failure encountered during PR acceptance may temporarily use `site-browser-regression-triage`, then return to exact-head acceptance after the repair creates a new head.

## Loading discipline

1. Read the matching `SKILL.md` first.
2. Follow only the canonical references needed for the current task; do not bulk-read historical pull requests as a substitute for current repository state.
3. Prefer current code, tests, workflow definitions, `MAINTENANCE.md`, and `PUBLISHING.md` over historical PR descriptions.
4. Use repository history only when current sources leave a material ambiguity unresolved.
5. If a skill conflicts with current canonical documentation or executable contracts, follow the canonical source and update the stale skill.

## Authority boundary

The active canonical authorities are `site`, `composition`, and `policy`. The external provider set published by Site is exactly `composition` and `policy`. Skill and Webapp remain reader/artifact concepts under Composition; they are not independent provider branches.

Site owns integration, reader-facing information architecture, exact provider locks, publication assembly, validation, provenance, PWA integration, and Pages deployment. Do not move provider-owned Composition or Policy semantics into Site merely to complete an integration task.
