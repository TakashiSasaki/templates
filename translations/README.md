# Site-owned translations

This directory contains non-authoritative translations of canonical documents owned by the `site` authority.

The canonical English documents remain under their normal repository paths and remain authoritative. Translation paths mirror canonical paths under `translations/<language>/`, and `translations/manifest.json` is the explicit synchronization contract.

The Site uses the same schema-v2 translation contract as external publications:

- `canonical` identifies the Site-owned canonical source path;
- `translation` identifies the mirrored translated source path;
- `canonical_blob_sha` records the exact Git blob reviewed when the translation was synchronized;
- `surfaces` declares where the translation may be used.

Current Site-owned translations use the `reader` surface. Site itself is not added to the provider-owned guided-navigation graph merely because it owns reader translations.

A stale translation is omitted from the localized reader surface while its canonical English page remains publishable. Malformed metadata, unsafe paths, missing declared files, duplicate mappings, and other structural errors remain hard failures.

Provider-owned translations remain in their provider histories. Do not copy Policy or Composition translations into this directory.

## Cross-publication links

The translation publisher rewrites relative links only when their canonical target belongs to the same publication. A Site-owned reader index can also link to documents whose canonical source is owned by another publication, such as Composition capability or lifecycle documents. Those cross-publication links are deliberately written as root-relative canonical Site destinations in the Site-owned translation.

This is a conservative availability rule: the link always reaches the valid English canonical destination even when the provider translation is missing or stale. It does mean that a Site-owned Japanese page does not currently switch such a link to a provider-owned `/ja/` destination when that provider translation happens to be available. Availability-aware cross-publication localized link selection requires an explicit cross-publication destination mapping and is outside the current Site-owned translation contract; it must not be approximated by hard-coding `/ja/` links that can become unavailable when a provider translation goes stale.
