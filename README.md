# Integrated documentation site

The `site` branch is the only GitHub Pages build and deployment implementation
for `TakashiSasaki/templates`. It assembles one documentation portal from
branch-owned publication catalogs in the unrelated `skill`, `policy`, and
`webapp` histories.

## Ownership model

Each provider branch owns its public source boundary in
`docs/publication-catalog.json`:

- stable document IDs within its publication namespace;
- canonical Markdown source paths;
- required versus optional documents;
- its section landing document;
- explicit non-Markdown asset roots when catalog schema version 2 is used.

The `site` branch owns:

- the global portal home;
- cross-publication navigation, titles, ordering, and generated destinations;
- full-commit source locking in `publication-sources.json`;
- integrated assembly, strict site generation, link validation, provenance,
  and Pages deployment.

A document is identified by the pair `publication:document`, such as
`skill:overview`, `policy:overview`, or `webapp:overview`.

## Key files

- `docs/publication-catalog.json`: the site branch's own portal-home
  publication;
- `site-manifest.json`: schema-versioned integrated navigation;
- `publication-sources.json`: reviewed full-SHA provider inputs;
- `scripts/assemble_publications.py`: catalog validation and multi-source
  assembly;
- `.github/workflows/build-pages.yml`: build-only reusable workflow;
- `.github/workflows/deploy-pages.yml`: deployment route restricted to pushes
  to `site`.

## Local validation

Check out the four unrelated branches into separate directories, then run:

```sh
python -m unittest discover --start-directory site/tests --verbose
python site/scripts/assemble_publications.py \
  --publication site=site \
  --publication skill=sources/skill \
  --publication policy=sources/policy \
  --publication webapp=sources/webapp \
  --site-root site \
  --output-root build
zensical build --config-file build/zensical.toml --clean --strict
python site/scripts/validate_site_links.py \
  --site-root build/site \
  --config-file build/zensical.toml
```

The checked-out provider commits must match `publication-sources.json` unless a
reviewed workflow-call override is deliberately being tested.

## Deployment boundary

Only `.github/workflows/deploy-pages.yml` on the `site` branch may configure or
deploy GitHub Pages. Provider branches may validate or build their own
documentation, but they must not upload or deploy a Pages artifact.

A provider publication change requires a provider PR and a coordinated site PR.
Merge the provider PR with a merge commit, update the site source lock to that
merge commit's full SHA, verify the integrated build, and only then merge the
site PR.
