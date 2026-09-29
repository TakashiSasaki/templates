# Repository translations

English is the canonical language of maintained repository documentation. Files under `translations/<language>/` are non-authoritative translations of canonical English sources and must not define independent requirements, navigation structure, or authority.

## Authority

For every translated document:

- the canonical path remains the normal repository path, such as `docs/overview.md`;
- the translation mirrors that path under `translations/<language>/`, such as `translations/ja/docs/overview.md`;
- the English canonical document controls whenever wording or meaning differs;
- a translation must identify itself visibly as non-authoritative; and
- changing a canonical document invalidates the translation synchronization record until the translation is reviewed against the new canonical content.

`translations/manifest.json` records the relationship between canonical documents and translations. `canonical_blob_sha` is the Git blob SHA-1 of the canonical file bytes against which that translation was reviewed. The translation validator recomputes the blob identity from the current canonical bytes and reports stale records. Normal source CI accepts stale translations.

## Translation surfaces

Manifest schema version 2 declares the presentation surfaces on which each translation may be used:

- `reader` allows a translation of a canonical document selected by `docs/publication-catalog.json` to be exposed as a non-authoritative reader route;
- `guided` allows a translation of an `index.md` document to provide localized labels and explanatory prose for index-guided navigation.

A translation may declare both surfaces. A `reader` translation must correspond to a canonical document in the publication catalog. A `guided` translation may be outside the publication catalog, but its canonical source must be an `index.md` document.

The `guided` surface does not create a second navigation authority. Link targets, reachability, ordering, and graph structure remain defined only by canonical English `index.md` files. A site integration may use the translated `index.md` text only as a locale overlay on that canonical graph and must fall back to canonical English when an overlay is unavailable.

Translations remain separate from `docs/publication-catalog.json`; the publication catalog continues to expose only canonical English documents. A publication layer may add translated routes or localized guided views only after it preserves this one-way authority relationship and makes the non-authoritative status explicit to readers.

## Independent translation maintenance

Canonical edits do not require translation updates. Review translations later, on
the owning authority branch. `canonical_blob_sha` identifies the English bytes
actually reviewed; never advance it merely to clear a stale report. Translation
status is derived from content, and stale Japanese pages display a warning and a
link to current English. Use `python scripts/check_translation_status.py` for the
current backlog; the default-branch **Review translations** workflow offers the
same report on manual dispatch. Missing Japanese pages simply use English.

For translation-specific review, run `python scripts/validate_translations.py
--allow-stale`. This structural review is separate from canonical source CI;
`--allow-stale` allows a partial translation update without clearing the backlog.
