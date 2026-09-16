---
name: site-publication-cutover
description: Explicitly adopt an immutable reviewed Integration release in Site.
---

# Site Integration adoption

Require an explicit Site-adoption instruction. Refresh Site and Integration heads, submitted reviews, comments, threads, and exact-head CI. Select a reviewed Integration release, not a moving branch. Record its schema, Bundle identity, and content digest in `integration-source.json`; do not select Composition or Policy revisions in Site.

Acquire the qualified Bundle through `scripts/acquire_integration_bundle.py`, preserving run/head/attempt/upload-window/archive/provenance verification. Missing durable evidence may use the pinned Integration regeneration workflow; corrupt or misbound evidence must fail closed. Never copy provider semantics or Git ancestry into Site.

Qualify Site rendering from the Bundle with provider checkouts absent. Run full Site/browser/PWA qualification at the stabilized acceptance frontier. Inspect the Site audience, navigation, translation warnings, source browser, glossary, search, accessibility, and offline behavior. Use `site-pr-exact-head-acceptance`, then `pr-merge-gate` for guarded landing.

Adoption does not authorize deployment. Deployment requires a separate explicit instruction and must use the exact qualified Site and Integration identities. A Site-only runtime release retains the existing Integration lock.

## Purpose

Make explicit Site adoption reproducible without selecting provider revisions.

## Use when

The human explicitly requests Site adoption of a reviewed Integration release.

## Do not use when

Provider construction, Integration qualification, and Integration promotion stop upstream.

## Canonical authorities

Consult `MAINTENANCE.md`, `PUBLISHING.md`, `integration-source.json`, and the selected Integration contract. The lock is the sole committed authority for Site provider-publication input. Integration owns all provider selection.

## Inputs

Record the full 40-character lowercase Integration SHA, reviewed Integration diff, Bundle schema/identity/content digest, and generated provenance. Do not infer the target SHA from a branch name. Do not expose undeclared Bundle content. Use `site-pr-exact-head-acceptance` and `pr-merge-gate` for acceptance and merge authorization.

## Stop conditions

Stop for missing authorization, corrupt or misbound artifacts, unresolved material findings, or incompatible contracts. Do not deploy without explicit deployment authorization.

## Evidence to report

Report exact Site and Integration revisions, Bundle identity, qualification and review applicability, adoption state, and deployment state separately.
