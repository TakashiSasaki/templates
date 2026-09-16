# Bootstrap authority boundary

Composition owns Composition artifacts, capabilities, foundations, lifecycle, topology,
recipes, Composer, schemas/validators, consumer semantics, catalogs and translations.
Policy owns operating policy, procedures, review/profile/runtime/release semantics,
consumer tooling, catalogs, translations and Work-ledger policy.

Integration owns reviewed provider selection, compatibility/publication closure,
destinations and reader IA, semantic navigation, publication staging, provider freshness,
translation availability derivation, integrated glossary, guided graph, immutable provider
repository/source read models, provenance and deterministic Bundle qualification.
It may represent or validate provider declarations, but may not redefine their semantics.

Site owns presentation and browser runtime, including source browser/search/glossary UI,
accessibility, PWA and deployed-document freshness, artifact packaging and deployment.
Integration does not import those implementations. Site adoption of an exact reviewed
Integration release is a separate, explicit human action and is not performed in P5.

The bootstrap candidate uses the reviewed Site lock snapshot, not current provider HEADs.
Provider candidate compatibility, Integration adoption/promotion, Site adoption/release and
deployment are distinct. This P5 candidate preserves current-only translation publication;
structurally valid stale translations are recorded as stale and remain unpublished.
Malformed metadata, unsafe paths, missing declared files and identity mismatches fail.

The active Site authority has not cut over. This document describes the independent
candidate responsibility, not a claim that final four-authority runtime discovery is live.
