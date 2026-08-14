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

## Canonical language and translations

English is the canonical language for maintained repository documentation.
Every `source` listed in `docs/publication-catalog.json` therefore identifies an
English canonical document. A translation is a non-authoritative derivative
and must not define independent requirements or override the English source.

Translations mirror the canonical path below `translations/<language>/`. For
example, the Japanese translation of `docs/overview.md` is
`translations/ja/docs/overview.md`. `translations/manifest.json` records each
canonical/translation relationship and the Git blob identity of the canonical
bytes against which the translation was reviewed. Changing canonical bytes
therefore makes the translation record stale until the translation is reviewed
and the synchronization record is deliberately updated.

Translations are not currently entries in the publication catalog and are not
published as independent Pages documents. A future publication layer may expose
translated routes only if it preserves the one-way authority relationship,
keeps the English document canonical, and presents the translation as
non-authoritative to readers.

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
Markdown page must be named explicitly in `documents`. Asset roots must not
contain a nested `.git` subtree in any letter case.

All source and destination values are portable relative POSIX paths. They may
not be absolute, contain empty, `.` or `..` components, use backslashes or
colons, enter a `.git` subtree in any letter case, traverse symbolic links, or
escape the declared source root.

## Validation

Run the validators from the repository root:

```sh
python scripts/validate_publication_catalog.py
python -m scripts.validate_publication_catalog
python scripts/validate_translations.py
```

The publication validator rejects duplicate JSON members, unsupported fields,
unsafe or symbolic-link paths, duplicate IDs and destinations, invalid home
declarations, missing required sources, and undeclared schema versions.

The translation validator rejects unsafe or unmirrored translation paths,
translations of non-published canonical documents, missing non-authoritative
notices for Japanese translations, duplicate translation declarations, and
translation records whose recorded canonical Git blob no longer matches the
current English source.

A publication-set change is complete only after both the `policy` pull request
and the dependent `site` pull request pass. The site source lock must record the
reviewed full commit SHA that contains the catalog change.
