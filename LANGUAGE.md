# Language and translation ownership

English is canonical for Composition, Policy, Integration and Site. The authority
that owns a canonical document owns its translations and synchronization metadata.
Site does not keep independent copies of provider translations.

Integration derives provider `current`, `stale` and `missing` availability from
provider manifests and immutable canonical source identities. Site consumes those
states without inspecting provider manifests, Git objects or synchronization hashes.

Current translations remain non-authoritative reference translations. Structurally
valid stale translations remain available and show an accessible warning: English
changed after review, so the translation may be outdated. The current authoritative
English page is linked. Missing translations have no fabricated localized route.
Malformed manifests, unsafe paths, missing declared files, symlinks, duplicate
mappings and inconsistent declarations remain failures, not availability states.

Site's own translations (for example `translations/ja/README.md`) remain owned here.
Their compiler accepts only Site source and derives their status locally. English
changes may leave Japanese stale. Never silently advance reviewed synchronization
hashes or change translation prose as part of an architectural migration.

Static warnings survive cached/offline delivery. Translation freshness is independent
of the Service Worker's deployed-document freshness and runtime convergence checks.
