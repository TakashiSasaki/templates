# Integrated documentation site

The `site` branch is the only GitHub Pages build and deployment implementation
for `TakashiSasaki/templates`. It assembles one reader-oriented documentation
portal from branch-owned publication catalogs in the unrelated `skill`,
`policy`, and `webapp` histories.

The normative cross-branch publication rules are documented in
[`PUBLISHING.md`](PUBLISHING.md).

## Ownership model

Each provider branch owns its public source boundary in
`docs/publication-catalog.json`:

- stable document IDs within its publication namespace;
- canonical Markdown source paths;
- required versus optional documents;
- its section landing document;
- explicit non-Markdown asset roots when catalog schema version 2 is used.

The catalog is an explicit allowlist for rendered documentation and provider
assets. Repository inventory previews are a separate bounded surface: they do
not add files to the documentation catalog and are generated only from eligible
immutable Git blobs under the constraints in `PUBLISHING.md`.

The `site` branch owns:

- the global portal home;
- cross-publication navigation, titles, ordering, and generated destinations;
- full-commit source locking in `publication-sources.json`;
- generated repository-tree inventories and sandboxed text previews for the
  exact checked-out revisions;
- integrated assembly, strict site generation, link validation, provenance,
  and Pages deployment.

A document is identified by the pair `publication:document`, such as
`skill:overview`, `policy:overview`, or `webapp:overview`.

## Reader-facing portal

The generated site exposes stable top-level entry points for all major
publications:

- `/templates/skill/` for reusable skill and caller-interface contracts;
- `/templates/policy/` for application-neutral agent policy and operation;
- `/templates/webapp/` for Web application templates, evidence, release, and
  migration guidance.

It also provides `/templates/repository-trees/` with complete tracked-path
inventories for the three provider revisions. Cataloged Markdown files link to
their Pages documentation. Eligible regular UTF-8 text files up to 256 KiB can
be opened in a sandboxed inline frame, while every file retains an immutable
GitHub source link at the exact rendered full commit SHA. Binary, oversized,
symlink, gitlink, invalid-UTF-8, and control-character inputs remain
GitHub-only.

Primary navigation prioritizes explanatory Markdown. Explicitly published
contracts, schemas, and other machine-readable assets remain supporting material
reachable from their explanatory pages.

## Key files

- `docs/publication-catalog.json`: the canonical site portal publication;
- `docs/repository-trees/*.md`: reviewed templates for generated tree pages;
- `site-manifest.json`: canonical integrated navigation before generated
  inventory augmentation;
- `publication-sources.json`: reviewed full-SHA provider inputs;
- `PUBLISHING.md`: normative public-boundary and deployment policy;
- `scripts/prepare_repository_tree_publication.py`: creates a temporary site
  publication with validated tree-page catalog and navigation entries;
- `scripts/generate_repository_trees.py`: generates tracked-path trees and
  immutable GitHub links from `git ls-tree`;
- `scripts/generate_repository_file_previews.py`: reads exact Git blob objects,
  emits escaped static preview pages, and connects them to sandboxed iframes;
- `assets/javascripts/repository-tree-viewer.js`: updates and focuses the shared
  viewer without rendering repository content in the parent document;
- `scripts/assemble_publications.py`: catalog validation and multi-source
  assembly;
- `.github/workflows/build-pages.yml`: build-only reusable workflow;
- `.github/workflows/deploy-pages.yml`: deployment route restricted to pushes
  to `site`.

## Local validation

Check out the four unrelated branches into separate directories, then run:

```sh
python -m unittest discover --start-directory site/tests --verbose
python site/scripts/prepare_repository_tree_publication.py \
  --site-root site \
  --output-root site-publication
python site/scripts/assemble_publications.py \
  --publication site=site-publication \
  --publication skill=sources/skill \
  --publication policy=sources/policy \
  --publication webapp=sources/webapp \
  --site-root site-publication \
  --output-root build
python site/scripts/generate_repository_trees.py \
  --repository TakashiSasaki/templates \
  --site-root site-publication \
  --output-root build \
  --publication skill=sources/skill \
  --publication policy=sources/policy \
  --publication webapp=sources/webapp
python site/scripts/generate_repository_file_previews.py \
  --repository TakashiSasaki/templates \
  --site-root site-publication \
  --output-root build \
  --publication skill=sources/skill \
  --publication policy=sources/policy \
  --publication webapp=sources/webapp
zensical build --config-file build/zensical.toml --clean --strict
python site/scripts/validate_site_links.py \
  --site-root build/site \
  --config-file build/zensical.toml
```

The checked-out provider commits must match `publication-sources.json` unless a
reviewed workflow-call override is deliberately being tested. Tree links and
preview URLs are always generated from the actual checked-out commit, so
override builds remain internally consistent.

## Deployment boundary

Only `.github/workflows/deploy-pages.yml` on the `site` branch may configure or
deploy GitHub Pages. Provider branches may validate or build their own
documentation, but they must not upload or deploy a Pages artifact.

The repository's `github-pages` environment is an external release gate. Its
custom deployment branch policy must allow exactly `site`; it must not retain a
stale `main`-only rule or be broadened to every branch. Pull requests cannot
change this setting, so it must be verified separately before publication is
declared complete.

A provider publication change requires a provider PR and a coordinated site PR.
Merge the provider PR with a merge commit, update the site source lock to that
merge commit's full SHA, verify the integrated build, and only then merge the
site PR.
