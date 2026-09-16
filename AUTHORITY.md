# Integration authority boundary

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
Integration release is a separate, explicit human action. Site completed that cutover
in #901 and renders stale translation warnings through #902. Integration advancement
still does not advance Site selection or authorize deployment.

The historical P5 bootstrap used the reviewed Site provider snapshot, not provider
HEADs. Its provenance remains immutable historical evidence. Later P7 promotion and
P8 Bundle v2 introduced the current reviewed inputs and stale derivative publication.
Current and structurally valid stale translations remain available; missing coverage
has no fabricated derivative. Provider-owned reviewed and current source identities
remain distinct. Malformed metadata, unsafe paths, missing declared files and identity
mismatches fail. No provider translation or synchronization metadata is rewritten.

The live dependency direction is Composition + Policy → Integration → Site → Pages.
Site may remain pinned to an earlier reviewed Integration release while this authority
advances. Machine discovery describes responsibilities, not a second Site adoption lock.
The exact downstream selection belongs solely to Site's `integration-source.json`.
