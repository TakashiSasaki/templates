# Repository translations

English is the canonical language of maintained repository documentation. Files under `translations/<language>/` are non-authoritative translations of canonical English sources and must not define independent requirements.

## Authority

For every translated document:

- the canonical path remains the normal repository path, such as `docs/overview.md`;
- the translation mirrors that path under `translations/<language>/`, such as `translations/ja/docs/overview.md`;
- the English canonical document controls whenever wording or meaning differs;
- a translation must identify itself visibly as non-authoritative; and
- changing a canonical document invalidates the translation synchronization record until the translation is reviewed against the new canonical content.

`translations/manifest.json` records the relationship between canonical documents and translations. `canonical_blob_sha` is the Git blob SHA-1 of the canonical file bytes against which that translation was reviewed. The translation validator recomputes the blob identity from the current canonical bytes and rejects stale records.

Translations are not currently part of `docs/publication-catalog.json`; the publication catalog continues to expose only canonical English documents. A publication layer may add translated routes only after it preserves this one-way authority relationship and makes the non-authoritative status explicit to readers.
