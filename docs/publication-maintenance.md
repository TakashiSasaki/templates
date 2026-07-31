# Documentation publication maintenance

The canonical public-document set is declared on `main` in
`docs/publication-catalog.json`. The unrelated `site` branch must consume that
catalog when assembling the GitHub Pages site.

## Responsibility boundary

`main` owns:

- the stable document ID;
- the canonical repository-relative Markdown source path;
- whether the source may be absent in a reduced source tree;
- the single document that serves as the site home page.

`site` owns:

- navigation hierarchy and ordering;
- reader-facing navigation titles;
- generated destination paths;
- theme, assembly, build, and deployment behavior.

Do not define a second independent public source list on `site`. Site-specific
configuration may arrange catalog documents, but it must not silently add,
omit, or reinterpret catalog entries.

## Catalog schema

The catalog is a JSON object with:

- `schema_version`: currently the integer `1`;
- `documents`: a non-empty array of document objects.

Every document object has exactly these fields:

- `id`: a unique lowercase kebab-case identifier that remains stable when a
  source file is renamed;
- `source`: a unique safe relative POSIX path to an existing regular Markdown
  file under the repository root;
- `optional`: a boolean indicating whether an assembler may skip the document
  when the source is absent from a reduced source tree;
- `home`: a boolean; exactly one non-optional document must be the home page.

Catalog paths may not be absolute, traverse `.` or `..`, contain backslashes,
or traverse symlinks.

## Change process

When a public canonical document is added, removed, or moved:

1. update the canonical Markdown and `docs/publication-catalog.json` in the same
   `main` pull request;
2. preserve an existing document ID across source renames;
3. update the unrelated `site` branch so its navigation resolves the same
   catalog IDs and optionality;
4. require the `main` catalog validation and the `site` strict documentation
   build to pass before considering the publication change complete.

Because `main` and `site` are unrelated branches, their pull requests remain
separate. Record the dependency and merge order in both pull-request bodies
when a publication-set change spans the branches.

## Validation

Run:

```sh
ruby .github/scripts/test-publication-catalog.rb
ruby .github/scripts/validate-publication-catalog.rb
```

The first command locks the catalog parser and failure behavior. The second
validates the current repository catalog and all declared source files.
