# Documentation publication maintenance

The `skill` branch owns the canonical public-document set declared in
`docs/publication-catalog.json`. The unrelated `site` branch consumes that
catalog together with the catalogs from other publication branches when it
assembles the repository's GitHub Pages portal.

## Responsibility boundary

`skill` owns:

- stable document IDs within the `skill` publication namespace;
- canonical repository-relative Markdown source paths;
- whether a source may be absent in a reduced source tree;
- the single document that serves as the `skill` publication landing page.

`site` owns:

- the GitHub Pages portal home page;
- navigation hierarchy and ordering across publications;
- reader-facing navigation titles;
- generated destination paths;
- source-revision locking, assembly, build, and deployment behavior.

The catalog field `home: true` identifies the landing document for this
publication. It does not select the home page of the combined GitHub Pages
site. The site manifest identifies that global home separately by the pair
`publication` and `document`.

Do not define a second independent `skill` source list on `site`. Site-specific
configuration may arrange catalog documents, but it must not silently add,
omit, or reinterpret catalog entries.

## Catalog schema

The current catalog uses schema version `1`. It is a JSON object with:

- `schema_version`: the integer `1`;
- `documents`: a non-empty array of document objects.

Every document object has exactly these fields:

- `id`: a unique lowercase kebab-case identifier that remains stable when a
  source file is renamed;
- `source`: a unique safe relative POSIX path to a Markdown file under the
  repository root;
- `optional`: a boolean indicating whether an assembler may skip the document
  when the source is absent from a reduced source tree;
- `home`: a boolean; exactly one non-optional document must be the publication
  landing page.

The effective cross-publication identity is the pair
`skill:<document-id>`. Another publication may therefore use the same local
document ID without creating a collision.

Catalog paths may not be absolute, traverse `.` or `..`, contain backslashes,
or traverse symbolic links.

## Change process

When a public canonical document is added, removed, or moved:

1. update the canonical Markdown and `docs/publication-catalog.json` in the same
   `skill` pull request;
2. preserve an existing document ID across source renames;
3. update the unrelated `site` branch so its navigation resolves the same
   `skill:<document-id>` entries;
4. update the site source lock to the reviewed full commit SHA;
5. require the `skill` catalog validation and the `site` strict documentation
   build to pass before considering the publication change complete.

Because `skill` and `site` have unrelated histories, their pull requests remain
separate. Record dependencies and merge order in both pull-request bodies when
a publication-set change spans the branches.

## Validation

Run:

```sh
ruby .github/scripts/test-publication-catalog.rb
ruby .github/scripts/validate-publication-catalog.rb
```

The first command locks the catalog parser and failure behavior. The second
validates the current branch-owned catalog and all declared source files.
