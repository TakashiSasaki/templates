# Documentation publication maintenance

The `skill` branch owns the canonical public-document set declared in `docs/publication-catalog.json`. The unrelated `site` branch consumes that catalog together with the catalogs from other publication branches when assembling the GitHub Pages portal.

## Responsibility boundary

`skill` owns:

- stable document IDs within the `skill` publication namespace;
- canonical repository-relative Markdown source paths;
- whether a source may be absent in a reduced publication checkout;
- the single document that serves as the `skill` publication landing page; and
- the distinction between the complete source repository and the copyable `template/` artifact.

`site` owns:

- the combined portal home page;
- navigation hierarchy and ordering across publications;
- reader-facing navigation titles;
- generated destination paths;
- full-SHA source locking;
- publication assembly, repository-tree rendering, provenance, link validation, and deployment; and
- the dedicated copyable-template tree page.

The catalog field `home: true` identifies the landing document for the Skill publication. It does not select the home page of the combined Pages site.

Do not define a second independent Skill document source list on `site`. Site-specific configuration may arrange catalog documents but must not silently add, omit, or reinterpret catalog entries.

## Canonical source boundary

The source-product overview is root `README.md`. Consumer-facing contracts and guidance resolve below `template/`, including `template/SKILL.md`, runtime and interface contracts, profile guidance, and architecture material intended for a concrete Skill developer.

The publication catalog itself, source architecture records, maintainer documentation, fixtures, validators, and workflows are not part of the copyable template unless explicitly declared by the distribution manifest.

Stable document IDs are preserved when a canonical source path moves. For example, moving `SKILL.md` to `template/SKILL.md` changes the source path but does not change the cross-publication identity `skill:skill-contract`.

## Catalog schema

The catalog uses schema version `1`. It is a JSON object containing:

- `schema_version`: the integer `1`;
- `documents`: a non-empty array of document objects.

Each document object has exactly:

- `id`: a unique lowercase kebab-case identifier that remains stable across source renames;
- `source`: a unique safe relative POSIX path to an existing regular Markdown file under the source checkout;
- `optional`: whether an assembler may skip the document when the source is absent from a reduced publication tree;
- `home`: whether the document is the Skill publication landing page; exactly one non-optional document is the landing page.

The effective cross-publication identity is `skill:<document-id>`. Another publication may use the same local document ID without creating a collision.

Catalog paths must not be absolute, traverse `.` or `..`, contain backslashes, traverse symbolic links, or escape the reviewed source checkout.

## Change process

When a public canonical document is added, removed, or moved:

1. update the canonical Markdown and `docs/publication-catalog.json` in the same `skill` pull request;
2. preserve existing document IDs across source renames;
3. run Skill catalog validation and the build-only `site` compatibility workflow against the proposed Skill merge commit;
4. merge the reviewed Skill pull request and record its full merge commit SHA;
5. create a separate pull request on unrelated `site` history;
6. update `site/publication-sources.json` to the reviewed Skill full SHA;
7. update site navigation only when document identities or intended placement require it;
8. generate both the complete Skill source tree and the dedicated `template/` copyable tree;
9. require strict site tests, assembly, build, provenance, and link validation to pass while deployment remains suspended; and
10. restore Pages deployment only in a separate reviewed `site` pull request after integration is complete.

Because `skill` and `site` have unrelated histories, do not merge, rebase, or cherry-pick between them. Record dependency, reviewed SHA, and merge order in both pull-request bodies.

## Repository-tree publication

The integrated site must expose two distinct Skill views:

- the complete `skill` source tree, including maintainer infrastructure; and
- the copyable `template/` tree, rooted at the exact locked Skill revision.

The copyable page must identify `template/` as the copyable root, preserve source links at the locked full SHA, and exclude source-only maintainership files by selecting the tracked subtree rather than filtering a rendered complete tree.

Inline file previews belong to the complete source-tree publication unless the site explicitly defines a separate bounded preview contract for the copyable page. The copyable page must not imply that source-only fixtures or workflows are copied into a Skill.

## Deployment suspension and restoration

Pages deployment is suspended during this restructuring. The deployed site remains available, while pushes to `site` execute build-only integration without `pages: write`, `id-token: write`, `actions/configure-pages`, or `actions/deploy-pages`.

Deployment restoration requires all of the following:

- the final Skill merge commit is reviewed and available by full SHA;
- `site/publication-sources.json` locks that exact SHA;
- every Skill catalog document resolves from the locked checkout;
- the complete source tree and copyable `template/` tree are both generated and validated;
- build provenance records the final Skill SHA;
- strict static-site and generated-link validation pass; and
- a separate site-only pull request restores deployment authority only for pushes to `refs/heads/site`.

## Validation

Run on `skill`:

```sh
python .github/scripts/test_publication_catalog.py
python .github/scripts/test_publication_schema_version.py
python .github/scripts/validate_publication_catalog.py
ruby .github/scripts/test-restructure-completion.rb
```

The remaining Ruby command is part of the broader repository-validator migration tracked in `docs/ruby-to-python-migration.md`; publication-catalog validation itself requires only Python 3.12 and the standard library.

A Skill pull request that changes `README.md`, `docs/**`, `template/**`, or `.github/workflows/pages.yml` also runs the build-only site compatibility workflow. Publication work is not complete until the corresponding locked-SHA site integration passes.
