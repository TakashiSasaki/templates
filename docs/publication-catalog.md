# Publication catalog

The `webapp` template-development source declares the human-readable material,
machine-readable reference assets, and canonical terminology source that may be
consumed by the repository documentation portal through
`docs/publication-catalog.json`.

The unrelated `site` branch consumes this catalog together with the `skill`
and `policy` catalogs. Only `site` assembles and deploys GitHub Pages. After a
reviewed `webapp` change is merged, `site` must be updated to the final full
commit SHA before newer Webapp material can enter the integrated publication.

## Source and distribution publication

The catalog deliberately publishes from two ownership roots:

- downstream material is published from `template/`, the sole canonical source
  tree whose contents may be copied directly to a new product repository root;
- source-maintainer architecture, audits, clean-room conformance explanation,
  the canonical glossary, and this publication contract remain outside
  `template/`.

The distinction is based on artifact ownership, not on whether a document is
public. Publishing a source-maintainer document does not place it in the
copyable distribution. Conversely, publishing a document from `template/`
does not transfer its canonical ownership to `site`.

Stable document IDs and generated destinations are preserved when a canonical
source lives below `template/`. For example, `webapp:overview` resolves from
`template/README.md`, while its integrated destination remains the Web
application publication home. The contract and schema assets resolve from
`template/contracts` and `template/schemas`, but retain `contracts` and
`schemas` as their destinations within the `webapp` publication namespace.

## Ownership boundary

`webapp` owns:

- stable document IDs within the `webapp` publication namespace;
- canonical source paths across the source and distribution responsibility roots;
- source optionality;
- the publication landing document;
- explicit non-Markdown asset roots needed by the published documents;
- the canonical `docs/glossary.yml` terminology source; and
- the distinction between source-maintainer and distributed material.

`site` owns:

- the portal home page;
- navigation labels, hierarchy, and generated destinations;
- the reviewed full-SHA source lock;
- integrated assembly, glossary generation, and strict static-site generation;
  and
- the only workflow that may receive Pages deployment authority.

The effective document identity is `webapp:<document-id>`. The catalog field
`home: true` selects the landing page for the Web application section, not the
global site home. Glossary terms use their own stable repository-wide term IDs.

## Schema contract

The provider validator accepts only integer publication-catalog schema version
`3`. Legacy schema versions `1` and `2` are retired and fail closed. Schema
version `3` defines the current Markdown document and explicit non-Markdown
asset contracts and additionally permits a canonical glossary declaration.

A representative version 3 catalog is:

```json
{
  "schema_version": 3,
  "documents": [
    {
      "id": "overview",
      "source": "template/README.md",
      "optional": false,
      "home": true
    }
  ],
  "assets": [
    {
      "source": "template/contracts",
      "destination": "contracts",
      "optional": false
    }
  ],
  "glossary": {
    "source": "docs/glossary.yml"
  }
}
```

Each document contains exactly `id`, `source`, `optional`, and `home`. A
required document source must identify an existing regular Markdown file. An
optional document source may be absent, but when present it must also be a
regular Markdown file. Exactly one non-optional document is the publication
landing page.

Each schema-v3 asset contains exactly `source`, `destination`, and `optional`.
A required asset source must exist. An optional asset source may be absent.
Asset destinations are relative to the `webapp` namespace in the generated
site.

The optional schema-v3 `glossary` object contains exactly `source`. When
present, it identifies an existing regular `.yml` file inside the provider
source root. The path may not traverse a symbolic link or overlap any declared
asset source. The glossary is semantic input, not a raw published asset.
Individual terms and localized lexical labels are added inside the glossary and
do not become catalog entries.

English remains canonical for glossary definitions. `localized_labels`, such
as Japanese preferred terms and aliases, are discovery metadata that resolve to
the same stable term ID; they do not create localized definitions.

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
declarations, missing required documents or assets, any publication-catalog
schema version other than integer `3`, malformed glossary declarations, and
glossary/asset source overlap.

The Site build independently validates glossary content semantics, stable term
IDs, localized labels, external authority metadata, related-term resolution,
cross-provider uniqueness, and exact provider revision provenance before it
emits the integrated machine-readable glossary.

The separate distribution validator proves that the schema-v2
`distribution_files` inventory is a closed description of the canonical
`template/` tree, rejects undeclared or missing files and maintainer-only
residue, and does not depend on a second root copy or byte-parity mirror:

```sh
python scripts/validate_distribution.py
python -m scripts.validate_distribution
```

Changes to the publication set require a coordinated `site` pull request. The
site source lock must be updated to the reviewed full commit SHA containing the
catalog change before the integrated Pages change is merged.
