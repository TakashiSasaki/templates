---
name: site-publication-cutover
description: Publish a reviewed Composition or Policy provider revision through the site branch. Use when advancing publication-sources.json after a provider merge, deciding whether Site IA, translation, or glossary changes are required, and validating exact provider provenance before Site PR acceptance.
---

# Site Publication Cutover

## Purpose

Advance the Site publication from one reviewed immutable provider revision to another without copying provider-owned semantics into Site or publishing uncataloged material.

The external provider set is exactly `composition` and `policy`. Skill and Webapp remain reader/artifact concepts under Composition, not provider identities.

This skill is an orchestration guide. Canonical behavior remains defined by the current repository code, tests, `MAINTENANCE.md`, `PUBLISHING.md`, provider publication catalogs, and Site manifests.

## Use when

Use this skill when all of the following are true:

- a reviewed `composition` or `policy` change has been merged or an exact reviewed provider commit has otherwise been selected;
- Site needs to publish that exact provider revision;
- the task may require more than a blind SHA substitution because the provider public interface could have changed.

## Do not use when

Do not use this skill to:

- author or repair canonical Composition artifact/capability/lifecycle semantics;
- author or repair canonical Policy/toolchain semantics;
- publish a mutable branch tip instead of an exact reviewed full commit SHA;
- treat legacy Skill or Webapp branches as current external providers;
- perform only generic Site PR acceptance/merge work with no provider publication change; use `site-pr-exact-head-acceptance` and `pr-merge-gate` for that.

If the provider revision itself is invalid, incomplete, or not reviewed to the required standard, stop the Site cutover and return the correction to the owning provider.

## Canonical authorities

Read only the parts needed for the current change:

- `MAINTENANCE.md` — Site change process and current responsibility boundaries;
- `PUBLISHING.md` — publication allowlist, source-lock, provenance, reader-entry, and deployment contracts;
- `publication-sources.json` — sole committed authority for the current exact external provider publication revisions;
- `site-manifest.json` — Site-owned reader IA and generated destinations;
- provider `docs/publication-catalog.json` — exact public document/asset/glossary boundary;
- provider translation manifest and glossary sources when declared by the provider catalog;
- current tests and `.github/workflows/` — executable acceptance contracts.

Do not copy these documents into this skill. If their current contract differs from this skill, they win.

## Inputs

Establish before editing:

1. current `site` head SHA;
2. provider being advanced: exactly `composition` or `policy`;
3. current locked provider SHA from `publication-sources.json`;
4. target reviewed full 40-character lowercase provider SHA;
5. provider diff from the current lock to the target;
6. current Site PR/base state if a cutover PR already exists.

Do not infer the target SHA from a branch name when a merged/reviewed commit identity is available.

## Procedure

1. Confirm the Site base is current enough for the work and record its exact SHA.
2. Read the current lock and compare the locked provider revision with the target provider revision.
3. Inspect the provider diff before editing Site. Focus first on public-interface inputs rather than all implementation details:
   - `docs/publication-catalog.json`;
   - cataloged document IDs and source paths;
   - declared assets;
   - declared glossary source;
   - translation manifest or translated reader material;
   - provider `docs/index.md` when guided navigation semantics changed;
   - canonical walkthrough/entry documents whose reader routing may matter.
4. Classify the cutover using the decision points below.
5. Update `publication-sources.json` to the exact reviewed target SHA.
6. Make only the Site-owned synchronization changes justified by the classification.
7. Update focused regression expectations only when they intentionally bind the changed publication identity or reader route. Do not mechanically replace old SHAs in unrelated historical evidence.
8. Run the current Site validation path against the exact locks.
9. Inspect generated provenance and representative assembled outputs to prove the target revision, not a mutable or fallback revision, was consumed.
10. Hand Site-specific PR acceptance to `.agents/skills/site-pr-exact-head-acceptance/SKILL.md`, then final review/merge authorization to `.agents/skills/pr-merge-gate/SKILL.md`.

## Decision points

### Pin-only cutover

Use a pin-only change when the provider's public document IDs, declared assets, glossary boundary, translation publication, and Site reader routing requirements are unchanged.

A source-path-only internal provider change does not automatically require a Site IA change if stable publication document identities and generated destinations remain valid.

### Public document-set change

If provider catalog documents are added, removed, or renamed by stable ID:

- reconcile `site-manifest.json` so every intended catalog document is mapped according to the current Site publication contract;
- preserve Site ownership of reader titles, grouping, ordering, and destinations;
- do not expose uncataloged provider files merely because they exist in the branch.

### Reader-routing change

If a newly published or changed canonical document should become a Site task entry point, update Site-owned routing deliberately and add focused regression coverage for the intended reader path.

Do not transfer provider operational semantics into Site copy just to shorten the route.

### Translation change

If the provider's declared translation surface changes, inspect the current translation manifest and Site translation publication pipeline. Update Site-owned navigation labels or selection mappings only when the changed reader surface requires them.

Do not treat Site chrome localization and provider-owned canonical translation as the same authority.

### Glossary change

If a provider catalog adds, removes, or changes its glossary source, validate through the actual Site integration loader and integrated glossary contracts. Cross-provider related-term references must still resolve at the exact locked revisions.

## Validation

Use the current executable contracts rather than a historical fixed command list. At minimum, verify the scopes applicable to the exact head include:

- Site unit/integration and assembly tests;
- strict documentation artifact build;
- generated public-URL, link, fragment, canonical, and entry-point validation;
- provider coexistence against the exact locked revisions;
- publication freshness/candidate-build validation;
- translation and integrated glossary validation when their inputs changed;
- browser/PWA regressions when the current workflow applies to the Site PR;
- `/build-provenance.json` or equivalent current provenance output identifies the exact Site, Composition, and Policy inputs.

Never weaken a failing publication or link contract merely to make the target revision publishable.

## Failure classification

Classify failures before editing again:

- **Provider contract failure** — target provider catalog/content is invalid. Fix on the provider authority, not Site.
- **Site mapping failure** — Site manifest/routing no longer maps a valid provider public interface. Fix Site-owned mapping.
- **Translation/glossary integration failure** — determine whether the changed input is provider-owned or Site-owned before changing files.
- **Provenance/source-lock failure** — fail closed; do not accept branch fallback or ambiguous revision resolution.
- **Browser/PWA regression** — diagnose the generated artifact and runtime; do not assume a publication pin is innocent or guilty without evidence.
- **Unrelated infrastructure failure** — preserve evidence and distinguish it from a semantic regression; do not alter product contracts to mask it.

## Stop conditions

Do not declare the cutover complete while any of these remain true:

- target provider identity is mutable, abbreviated, or not the reviewed revision intended for publication;
- provider diff has not been classified for public-interface effects;
- Site publishes a catalog document without a deliberate mapping or misses a required new reader document;
- generated provenance does not resolve to the exact intended provider revisions;
- required exact-head CI or review is unresolved;
- completing the change would require Site to own semantics that belong to Composition or Policy.

## Evidence to report

Report compactly:

- Site base SHA and final PR head SHA;
- provider, old locked SHA, and new locked SHA;
- cutover classification and why it was sufficient;
- intended changed-file set;
- exact-head validation/check results;
- generated provenance identities;
- review/base-drift status;
- any provider-side follow-up that was intentionally kept out of Site.
