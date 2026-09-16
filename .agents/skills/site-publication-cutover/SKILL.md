---
name: site-publication-cutover
description: Explicitly adopt an immutable reviewed Integration release in Site.
---

# Site Integration adoption

Require an explicit Site-adoption instruction. Refresh Site and Integration heads, submitted reviews, comments, threads, and exact-head CI. Select a reviewed Integration release, not a moving branch. Record its schema, Bundle identity, and content digest in `integration-source.json`; do not select Composition or Policy revisions in Site.

Acquire the qualified Bundle through `scripts/acquire_integration_bundle.py`, preserving run/head/attempt/upload-window/archive/provenance verification. Missing durable evidence may use the pinned Integration regeneration workflow; corrupt or misbound evidence must fail closed. Never copy provider semantics or Git ancestry into Site.

Qualify Site rendering from the Bundle with provider checkouts absent. Run full Site/browser/PWA qualification at the stabilized acceptance frontier. Inspect the Site audience, navigation, translation warnings, source browser, glossary, search, accessibility, and offline behavior. Use `site-pr-exact-head-acceptance`, then `pr-merge-gate` for guarded landing.

Adoption does not authorize deployment. Deployment requires a separate explicit instruction and must use the exact qualified Site and Integration identities. A Site-only runtime release retains the existing Integration lock.
