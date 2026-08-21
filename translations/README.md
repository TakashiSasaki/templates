# Repository translations

English is the canonical language of maintained Composition documentation. Files under `translations/<language>/` are non-authoritative translations of canonical English sources and must not define independent requirements, navigation structure, or authority.

## Authority

For every translated document:

- the canonical path remains the normal Composition repository path, such as `README.md` or `docs/consumer-guide.md`;
- the translation mirrors that path under `translations/<language>/`, such as `translations/ja/README.md`;
- the English canonical document controls whenever wording or meaning differs;
- a translation must identify itself visibly as non-authoritative; and
- changing a canonical document invalidates the translation synchronization record until the translation is reviewed against the new canonical content.

`translations/manifest.json` records the relationship between canonical documents and translations. `canonical_blob_sha` is the Git blob SHA-1 of the canonical file bytes against which that translation was reviewed. The translation validator recomputes the blob identity from the current canonical bytes and rejects stale records.

## Translation surfaces

Manifest schema version 2 declares the presentation surfaces on which each translation may be used:

- `reader` allows a translation of a canonical document selected by `docs/publication-catalog.json` to be exposed as a non-authoritative reader route;
- `guided` allows a translation of an `index.md` document to provide localized labels and explanatory prose for index-guided navigation.

A translation may declare both surfaces. A `reader` translation must correspond to a canonical document in the publication catalog. A `guided` translation may be outside the publication catalog, but its canonical source must be an `index.md` document.

The `guided` surface does not create a second navigation authority. Link targets, reachability, ordering, and graph structure remain defined only by canonical English `index.md` files. A Site integration may use translated `index.md` text only as a locale overlay on that canonical graph and must fall back to canonical English when an overlay is unavailable.

Translations remain separate from `docs/publication-catalog.json`; that publication catalog continues to expose only canonical English documents. Site may add translated reader routes or localized guided views only after preserving this one-way authority relationship, using the same reviewed Composition revision as the canonical publication, and making the non-authoritative status explicit to readers.
