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

Translation sources use canonical reader destinations for links that cross publication-authority boundaries. For example, a Site-owned Japanese index may link to a Composition-owned page with a root-relative canonical route such as `/composition/` or `/capabilities/runtime/`. Translation sources must not hard-code `/ja/` provider routes, because a provider translation can later become stale or unavailable.

After all publication manifests have been resolved at their reviewed revisions, the integrated Site translation publisher builds one availability map from the translations that are both current and actually published. Root-relative reader links in translated pages are then selected against that map across publication boundaries:

- when the target has a current translation in the same language, the generated translated page links to that localized reader route;
- when the target translation is missing or stale, the canonical root-relative route remains unchanged;
- external URLs, assets, fragments, code fences, and already-localized routes are not inferred or rewritten merely from path similarity.

This selection is derived from the assembled canonical and translated destinations. It does not create a second translation authority and does not require Site-owned copies of provider translations. Relative links whose canonical source belongs to the same publication continue to be resolved by the provider translation publisher before this cross-publication availability pass.
