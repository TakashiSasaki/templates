---
id: project.site-maintenance
severity: mandatory
overridable: false
order: 1000
---

# Site maintenance authority

This repository is not production-critical; backward compatibility is not required. Preserve authority ownership, safe material management, and immutable provenance.

Composition governs the Website product; Policy governs repository maintenance. Their consumer configuration, locks, toolchains, and operations are independent. Site publication revisions in `publication-sources.json` are independent of both consumer relationships. Neither provider may mutate the other consumer state. Site integrates public provider contracts; it must not interpret private management metadata or add a shared management plane.

# Site-local procedural routing

The following routes select consumer-owned procedural Skills. Canonical norms remain in the selected Policy profiles and this project policy.

When working on the `site` authority, load the smallest matching skill from `.agents/skills/` before reconstructing a workflow from repository history.

## Skill routing

- Coordinated cross-authority document-set change that requires a Site staging PR before a provider publication PR: `PUBLICATION_STAGING.md` for the staging protocol, then `.agents/skills/site-publication-cutover/SKILL.md` for the final Site promotion step.
- Provider publication update after a reviewed `composition` or `policy` merge: `.agents/skills/site-publication-cutover/SKILL.md`
- Site-specific pull-request scope, exact-head CI, browser/publication acceptance, and base-drift preparation: `.agents/skills/site-pr-exact-head-acceptance/SKILL.md`
- Final merge authorization for every Site pull request: `.agents/skills/pr-merge-gate/SKILL.md`
- Site browser/PWA/mobile/search regression failure triage: `.agents/skills/site-browser-regression-triage/SKILL.md`

If more than one skill applies, use only the minimal set needed and follow them in dependency order. A normal Site PR completion path is task-specific work -> `site-pr-exact-head-acceptance` -> `pr-merge-gate`. A normal publication cutover uses `site-publication-cutover` first, then Site acceptance, then the merge gate. A coordinated document-set change that cannot merge provider-first uses `PUBLICATION_STAGING.md` first, then the provider candidate compatibility build, then `site-publication-cutover` for promotion after the provider merge. A browser failure encountered during Site acceptance may temporarily use `site-browser-regression-triage`, then return to Site acceptance after the repair creates a new head.

`site-pr-exact-head-acceptance` establishes Site-specific acceptance evidence but never authorizes merge. Before declaring a Site PR merge-ready, merging it, or completing a task whose final action is a merge, load `pr-merge-gate`. Green CI and `reviews = 0` must never be interpreted as a clean review state.

## Loading discipline

1. Read the matching `SKILL.md` first.
2. Follow only the canonical references needed for the current task; do not bulk-read historical pull requests as a substitute for current repository state.
3. Prefer current code, tests, workflow definitions, `MAINTENANCE.md`, and `PUBLISHING.md` over historical PR descriptions.
4. Use repository history only when current sources leave a material ambiguity unresolved.
5. If a skill conflicts with current canonical documentation or executable contracts, follow the canonical source and update the stale skill.
6. If the PR head changes, invalidate evidence bound to the previous head and reacquire only the affected Site-acceptance and merge-gate evidence. Do not discard unaffected evidence or restart unrelated gates solely because the head changed.

This routing discipline is not an additional acceptance checklist. Optional diagnostic reads or a locally stricter procedure do not become mandatory gates unless current repository authority requires them or a concrete unresolved uncertainty invalidates relied-upon evidence.

## Authority boundary

The active canonical authorities are `site`, `composition`, and `policy`. The external provider set published by Site is exactly `composition` and `policy`. Skill and Webapp remain reader/artifact concepts under Composition; they are not independent provider branches.

Site owns integration, reader-facing information architecture, exact provider locks, publication assembly, validation, provenance, PWA integration, and Pages deployment. Repository-local Agent Skills orchestrate maintenance and merge acceptance; they do not become a second semantic authority. Do not move provider-owned Composition or Policy semantics into Site merely to complete an integration task.