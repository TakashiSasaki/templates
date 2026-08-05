# Publication catalog

The `webapp` branch declares the human-readable material and machine-readable
reference assets that may be published through the repository documentation
portal in `docs/publication-catalog.json`.

The unrelated `site` branch consumes this catalog together with the `skill`
and `policy` catalogs. Only `site` assembles and deploys GitHub Pages.

## Ownership boundary

`webapp` owns:

- stable document IDs within the `webapp` publication namespace;
- canonical source paths;
- the publication landing document;
- explicit non-Markdown asset roots needed by the published documents.

`site` owns:

- the portal home page;
- navigation labels, hierarchy, and generated destinations;
- the reviewed full-SHA source lock;
- the integrated Zensical build and Pages deployment.

The effective document identity is `webapp:<document-id>`. The catalog field
`home: true` selects the landing page for the Web application section, not the
global site home.

## Machine-readable references

The Web application documentation links to normative JSON contracts and JSON
Schemas. Catalog schema version `2` therefore adds explicit `assets` entries.
The site copies those roots into the `webapp` namespace while preserving their
relative structure.

Markdown is not allowed inside an asset root. Every published Markdown page
must appear explicitly in `documents`, which keeps the public page set
reviewable and prevents fixtures or internal notes from becoming pages
implicitly.

## Validation

Run either entry point from the repository root:

```sh
python scripts/validate_publication_catalog.py
python -m scripts.validate_publication_catalog
```

The validator rejects duplicate JSON members, unsupported fields, unsafe paths,
symbolic-link traversal, duplicate IDs or destinations, invalid home
declarations, and missing required documents or assets.

Changes to the publication set require a coordinated `site` pull request. The
site source lock must be updated to the reviewed full commit SHA containing the
catalog change before the integrated Pages change is merged.
