# Publication catalog

The `policy` branch publishes a branch-owned allowlist of human-readable
documentation through `docs/publication-catalog.json`. The unrelated `site`
branch consumes this catalog together with the `skill` and `webapp` catalogs
and assembles the only GitHub Pages deployment for this repository.

## Ownership

`policy` owns each document's stable local ID, canonical Markdown source path,
optionality, and the publication landing document. The effective cross-branch
identity is `policy:<document-id>`.

`site` owns the portal home page, navigation labels and ordering, generated
destinations, the reviewed source-revision lock, the Zensical build, and Pages
deployment. `policy` continues to run only its branch-local MkDocs build and
must not gain a Pages deployment route.

The catalog field `home: true` identifies the landing document for the
`policy` section. It does not select the global portal home.

## Schema versions

Schema version `1` declares Markdown documents. Schema version `2` retains the
same document contract and adds explicit non-Markdown asset roots:

```json
{
  "schema_version": 2,
  "documents": [
    {
      "id": "overview",
      "source": "docs/index.md",
      "optional": false,
      "home": true
    }
  ],
  "assets": [
    {
      "source": "docs/assets",
      "destination": "assets",
      "optional": false
    }
  ]
}
```

Each document contains exactly `id`, `source`, `optional`, and `home`.
A required document source must identify an existing regular Markdown file.
An optional document source may be absent, but when present it must also be a
regular Markdown file. Exactly one non-optional document is the publication
landing page.

Each version 2 asset contains exactly `source`, `destination`, and `optional`.
Asset destinations are relative to the `policy` namespace in the generated
site. Markdown files are forbidden inside asset roots because every published
Markdown page must be named explicitly in `documents`.

All source and destination values are portable relative POSIX paths. They may
not be absolute, contain empty, `.` or `..` components, use backslashes or
colons, enter a `.git` subtree in any letter case, traverse symbolic links, or
escape the declared source root.

## Validation

Run the validator from the repository root:

```sh
python scripts/validate_publication_catalog.py
python -m scripts.validate_publication_catalog
```

The validator rejects duplicate JSON members, unsupported fields, unsafe or
symbolic-link paths, duplicate IDs and destinations, invalid home declarations,
missing required sources, and undeclared schema versions.

A publication-set change is complete only after both the `policy` pull request
and the dependent `site` pull request pass. The site source lock must record the
reviewed full commit SHA that contains the catalog change.
