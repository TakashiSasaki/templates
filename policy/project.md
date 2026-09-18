---
id: project.site-maintenance
severity: mandatory
overridable: false
order: 1000
---

# Site maintenance authority

This repository is not production-critical; backward compatibility is not required. Preserve authority ownership, safe material management, and immutable provenance.

Composition governs the installed Website product; Policy governs repository maintenance. Their consumer configuration, locks, toolchains, and operations remain independent of publication selection. Site selects one exact reviewed Integration release in `integration-source.json`. Integration alone selects provider publication revisions and produces the authenticated Publication Bundle. Site renders that Bundle without provider checkouts, catalog parsing, translation-manifest parsing, or provider freshness derivation.

## Maintainer entry point

The consumer-facing documentation and this repository's maintainer path are
different. Start a `templates` maintenance task at
`docs/maintainer-onboarding.md`, then select the owner and branch before loading
the smallest branch-local skill. Read `MAINTENANCE.md`, `PUBLISHING.md`, and
`docs/publication-automation.md` for Site-owned validation and publication
boundaries. These links route to existing authority documents; they do not create
a second normative authority or enable automation.

When a reference belongs to another authority branch, use its explicit repository,
branch/SHA, and path or a separate checkout. Do not describe a cross-branch file
as a relative local path. Use a branch name for discovery and an immutable full
SHA for evidence. The current capability, selected `integration-source.json`
input, and deployed Pages artifact are separate states; unknown external
variables, credentials, protections, runs, and deployments remain unknown.

# Site-local procedural routing

The following routes select consumer-owned procedural Skills. Canonical norms remain in the selected Policy profiles and this project policy.

When working on the `site` authority, load the smallest matching skill from `.agents/skills/` before reconstructing a workflow from repository history. For review routing, load the immutable landing Skill's declared planner with the exact Site head/base, selected Bundle, changed invariants, prior coverage, and request state; the planner chooses scope but never proves Site semantics or authorizes merge.

## Skill routing

- Provider publication or cross-authority staging change: work in the independent Integration authority. It does not authorize Site adoption.
- Explicit adoption of a reviewed Integration release: `.agents/skills/site-publication-cutover/SKILL.md`
- Site-specific pull-request scope, exact-head CI, browser/publication acceptance, and base-drift preparation: `.agents/skills/site-pr-exact-head-acceptance/SKILL.md`
- Repository-maintainer single-PR or stacked-PR landing: `.agents/skills/land-templates-stack/SKILL.md` (verify its immutable `source.json` before loading the canonical procedure)
- Final merge authorization for every Site pull request: `.agents/skills/pr-merge-gate/SKILL.md`
- Site browser/PWA/mobile/search regression failure triage: `.agents/skills/site-browser-regression-triage/SKILL.md`

If more than one skill applies, use only the minimal set needed and follow them in dependency order. A normal Site PR completion path is task-specific work -> `site-pr-exact-head-acceptance` -> `pr-merge-gate`. A normal publication cutover uses `site-publication-cutover` first, then Site acceptance, then the merge gate. Provider candidate compatibility and publication staging terminate in Integration. Site adoption requires a separate explicit instruction. A browser failure encountered during Site acceptance may temporarily use `site-browser-regression-triage`, then return to Site acceptance after the repair creates a new head.

`site-pr-exact-head-acceptance` establishes Site-specific acceptance evidence but never authorizes merge. Before declaring a Site PR merge-ready, merging it, or completing a task whose final action is a merge, load `pr-merge-gate`. Green CI and `reviews = 0` must never be interpreted as a clean review state.

The repository-maintainer landing procedure is pinned to
`TakashiSasaki/templates@9c4884646f5db14bc7d700f1395843a89b05a539`,
`repository-skills/land-templates-stack/SKILL.md`, blob
`06efa38681e374636bcabcbcb984be5ec43b47ee`; its rule and review-scope planner
are resolved
`repository-policy/stacked-pr-landing.md` from that same immutable snapshot,
not from the Site worktree or a mutable branch. Keep this route separate from
Site adoption and Pages deployment; it does not authorize merge or auto-merge.

## Loading discipline

1. Read the matching `SKILL.md` first.
2. Follow only the canonical references needed for the current task; do not bulk-read historical pull requests as a substitute for current repository state.
3. Prefer current code, tests, workflow definitions, `MAINTENANCE.md`, and `PUBLISHING.md` over historical PR descriptions.
4. Use repository history only when current sources leave a material ambiguity unresolved.
5. If a skill conflicts with current canonical documentation or executable contracts, follow the canonical source and update the stale skill.
6. If the PR head changes, invalidate evidence bound to the previous head and reacquire only the affected Site-acceptance and merge-gate evidence. Do not discard unaffected evidence or restart unrelated gates solely because the head changed.

This routing discipline is not an additional acceptance checklist. Optional diagnostic reads or a locally stricter procedure do not become mandatory gates unless current repository authority requires them or a concrete unresolved uncertainty invalidates relied-upon evidence.

## Authority boundary

The active canonical authorities are `modeling`, `composition`, `policy`, `integration`, and `site`, with independent histories. Modeling owns bounded information-model records and discovery documentation; Composition and Policy own their provider semantics, documentation, translations, and synchronization metadata. Integration owns exact reviewed provider selection, publication staging, IA, read models, translation availability, Bundle production, and qualification. Site owns presentation, browser runtime, accessibility, PWA, Pages artifact packaging, and explicit deployment. Site is not a parent or super-authority.

Site consumes only the versioned Integration output contract for provider publication. Site may release a runtime fix against unchanged Integration; Integration may advance without Site adoption or deployment. Site must not recalculate provider translation freshness. Provider-owned synchronization metadata must never be silently updated. Repository-local Agent Skills orchestrate Site maintenance and merge acceptance; they do not create another semantic authority.

## Adaptive Site review scope

The first inexpensive checks are the canonical source-ready preflight,
workflow/local inventory, renderer and contract tests, and HTML/link/provenance
inspection. A fixed Bundle plus a bounded presentation change can stay within
the affected Site delta, while Bundle-reader semantics, renderer meaning,
browser/PWA/cache lifecycle, sanitization, trust boundaries, Integration
adoption, or final-artifact/deployment bindings expand to the related Site
scope and explicitly affected Integration inputs. A CSS change is not exempt
when focus, authentication display, CSP, or navigation semantics change.
Independent review remains required; reusable evidence must name the exact
candidate, purpose, scope, and coverage. Site adoption of maintenance Policy
is separate from `integration-source.json` and Pages deployment.
