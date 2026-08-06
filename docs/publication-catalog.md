# Publication catalog

The `webapp` template-development source declares the human-readable material
and machine-readable reference assets that may be published through the
repository documentation portal in `docs/publication-catalog.json`.

The unrelated `site` branch consumes this catalog together with the `skill`
and `policy` catalogs. Only `site` assembles GitHub Pages. Pages deployment is
suspended while the source and copyable-template boundaries are being changed;
`site` will be updated to the final reviewed `webapp` full commit SHA before a
separate change restores deployment.

## Source and distribution publication

The catalog deliberately publishes from two ownership roots:

- downstream material is published from `template/`, the directory whose
  contents may be copied directly to a new product repository root;
- source-maintainer architecture, audits, clean-room conformance explanation,
  and this publication contract remain outside `template/`.

The distinction is based on artifact ownership, not on whether a document is
public. Publishing a source-maintainer document does not place it in the
copyable distribution. Conversely, publishing a document from `template/`
does not transfer its canonical ownership to `site`.

Stable document IDs and generated destinations are preserved when a canonical
source moves below `template/`. For example, `webapp:overview` now resolves
from `template/README.md`, while its integrated destination remains the Web
application publication home. The contract and schema assets resolve from
`template/contracts` and `template/schemas`, but retain `contracts` and
`schemas` as their destinations within the `webapp` publication namespace.

## Ownership boundary

`webapp` owns:

- stable document IDs within the `webapp` publication namespace;
- canonical source paths across the source and distribution roots;
- source optionality;
- the publication landing document;
- explicit non-Markdown asset roots needed by the published documents; and
- the distinction between source-maintainer and distributed material.

`site` owns:

- the portal home page;
- navigation labels, hierarchy, and generated destinations;
- the reviewed full-SHA source lock;
- integrated assembly and strict static-site generation; and
- the only workflow that may receive Pages deployment authority.

The effective document identity is `webapp:<document-id>`. The catalog field
`home: true` selects the landing page for the Web application section, not the
global site home.

## Schema contract

Schema version `1` declares only Markdown documents. Schema version `2` retains
the same document contract and adds explicit non-Markdown asset roots.

Each document contains exactly `id`, `source`, `optional`, and `home`. A
required document source must identify an existing regular Markdown file. An
optional document source may be absent, but when present it must also be a
regular Markdown file. Exactly one non-optional document is the publication
landing page.

Each version 2 asset contains exactly `source`, `destination`, and `optional`.
A required asset source must exist. An optional asset source may be absent.
Asset destinations are relative to the `webapp` namespace in the generated
site.

## Machine-readable references

The Web application documentation links to normative JSON contracts and JSON
Schemas. The site copies the declared `template/contracts` and
`template/schemas` roots into the `webapp` namespace while preserving the
contents below their declared destinations.

Markdown is not allowed inside an asset root. Every published Markdown page
must appear explicitly in `documents`, which keeps the public page set
reviewable and prevents fixtures, source tools, tests, or internal notes from
becoming pages implicitly.

All source and destination values are portable relative POSIX paths. They may
not be absolute, contain empty, `.` or `..` components, use backslashes or
colons, enter a `.git` subtree in any letter case, traverse symbolic links, or
escape the declared source root. Existing asset trees must not contain nested
`.git` subtrees in any letter case, symbolic links, or Markdown files.

## Validation

Run both provider-local entry points from the template-development source root:

```sh
python scripts/validate_publication_catalog.py
python -m scripts.validate_publication_catalog
```

The validator rejects duplicate JSON members, unsupported fields, unsafe paths,
symbolic-link traversal, duplicate IDs or destinations, invalid home
declarations, and missing required documents or assets.

The separate distribution validator proves that the copyable tree is closed and
that mirrored contract, schema, validator, migration, dependency, and guidance
bytes match their source-owned counterparts:

```sh
python scripts/validate_distribution.py
python -m scripts.validate_distribution
```

Changes to the publication set require a coordinated `site` pull request. The
site source lock must be updated to the reviewed full commit SHA containing the
catalog change before the integrated Pages change is merged.
