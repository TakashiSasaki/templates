# Site-owned translations

This directory contains non-authoritative translations of canonical documents owned by the `site` authority.

The canonical English documents remain under their normal repository paths and remain authoritative. Translation paths mirror canonical paths under `translations/<language>/`, and `translations/manifest.json` is the explicit synchronization contract.

The Site uses the same schema-v2 translation contract as external publications:

- `canonical` identifies the Site-owned canonical source path;
- `translation` identifies the mirrored translated source path;
- `canonical_blob_sha` records the exact Git blob reviewed when the translation was synchronized;
- `surfaces` declares where the translation may be used.

Current Site-owned translations use the `reader` surface. Site itself is not added to the provider-owned guided-navigation graph merely because it owns reader translations.

A stale translation remains available with a visible warning and a link to the current English canonical page. Missing translations fall back to English. Invalid translation inputs are omitted with diagnostics; they do not block canonical publication. Strict translation validation is a separate review operation.

Provider-owned translations remain in their provider histories. Do not copy Policy or Composition translations into this directory.

## Cross-publication links

Translation sources use canonical reader destinations for links that cross publication-authority boundaries. For example, a Site-owned Japanese index may link to a Composition-owned page with a root-relative canonical route such as `/composition/` or `/capabilities/runtime/`. Translation sources must not hard-code `/ja/` provider routes, because a provider translation can later become stale or unavailable.

After all publication manifests have been resolved at their reviewed revisions, the integrated Site translation publisher builds one availability map from the translations that are both current and actually published. Root-relative reader links in translated pages are then selected against that map across publication boundaries:

- when the target has a current translation in the same language, the generated translated page links to that localized reader route;
- when the target translation is missing or stale, the canonical root-relative route remains unchanged;
- external URLs, assets, fragments, code fences, and already-localized routes are not inferred or rewritten merely from path similarity.

This selection is derived from the assembled canonical and translated destinations. It does not create a second translation authority and does not require Site-owned copies of provider translations. Relative links whose canonical source belongs to the same publication continue to be resolved by the provider translation publisher before this cross-publication availability pass.

## Independent translation maintenance

Canonical edits do not require translation updates. Review translations later, on
the owning authority branch. `canonical_blob_sha` identifies the English bytes
actually reviewed; never advance it merely to clear a stale report. Translation
status is derived from content, and stale Japanese pages display a warning and a
link to current English. Use `python scripts/check_translation_status.py` for the
current backlog; the default-branch **Review translations** workflow offers the
same report on manual dispatch. Missing Japanese pages simply use English.
