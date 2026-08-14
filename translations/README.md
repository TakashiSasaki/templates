# Repository translations

English is the canonical language of maintained Skill documentation. Files under `translations/<language>/` are non-authoritative translations and must not define independent requirements, navigation structure, or copyable-template content.

`translations/manifest.json` uses schema version 2. Each entry records the canonical source, translation path, reviewed canonical Git blob SHA, and allowed presentation surfaces.

- `reader` may be used only for canonical documents selected by `docs/publication-catalog.json`.
- `guided` may be used only for canonical `index.md` documents and supplies localized labels and explanatory prose for index-guided navigation.

The English canonical `index.md` files remain the sole authority for link targets, reachability, ordering, and graph structure. Guided translations are locale overlays only. If canonical English bytes change, the recorded `canonical_blob_sha` becomes stale and validation must fail until the translation is reviewed again.

Translations of files beneath `template/` live beneath `translations/<language>/template/`; they are documentation-only derivatives and are never copied into the Skill `template/` distribution.
