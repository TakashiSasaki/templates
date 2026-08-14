# Integrated documentation site

The `site` branch is the only GitHub Pages build and deployment implementation
for `TakashiSasaki/templates`. It assembles one reader-oriented documentation
portal from branch-owned publication catalogs in the unrelated `skill`,
`policy`, and `webapp` histories.

The public portal is `https://templates.moukaeritai.work/`. The custom domain is
served from the domain root rather than from the former `/templates/` project
path.

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
- the bounded static repository browser for immutable source inspection;
- the deterministic index-navigation graph and `/guided/` projection of
  provider-owned `index.md` navigation at the same locked revisions;
- integrated assembly, strict site generation, link validation, provenance,
  and Pages deployment.

A document is identified by the pair `publication:document`, such as
`skill:overview`, `policy:overview`, or `webapp:overview`.

## Reader-facing portal

The generated site exposes stable top-level entry points for all major
publications:

- `/skill/` for reusable skill and caller-interface contracts;
- `/policy/` for application-neutral agent policy and operation;
- `/webapp/` for Web application templates, evidence, release, and migration
  guidance.

Three complementary discovery surfaces are available:

- `/guided/` follows provider-owned `index.md` navigation from the exact locked
  Skill, Policy, and Webapp revisions;
- `/repository-trees/` presents complete tracked-path inventories for the three
  provider revisions;
- `/files/` provides the bounded static browser for immutable source snapshots.

Cataloged Markdown files link to their Pages documentation. Eligible regular
UTF-8 text files up to 256 KiB can be opened in a sandboxed inline frame, while
every file retains an immutable GitHub source link at the exact rendered full
commit SHA. Binary, oversized, symlink, gitlink, invalid-UTF-8, and
control-character inputs remain GitHub-only.

Primary navigation prioritizes explanatory Markdown. Explicitly published
contracts, schemas, and other machine-readable assets remain supporting material
reachable from their explanatory pages. The `/guided/` surface does not replace
that reader-oriented navigation; it lets humans retrace the provider-owned
progressive-disclosure path that agents can follow.

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
- `scripts/generate_repository_browser.py`: generates the standalone immutable
  `/files/` browser after the strict site build;
- `scripts/generate_index_navigation.py`: parses provider-owned `index.md`
  files from immutable Git blobs into a deterministic navigation graph;
- `scripts/generate_index_navigation_viewer.py`: renders that graph as the
  static `/guided/` human navigation surface without reparsing Markdown;
- `scripts/check_mobile_layout.py`: measures rendered phone-width geometry with
  headless Chrome and writes screenshot and metric evidence;
- `assets/javascripts/repository-tree-viewer.js`: updates and focuses the shared
  viewer without rendering repository content in the parent document;
- `assets/javascripts/repository-browser.js`: progressive-enhancement controller
  for narrow-viewport Files/Content switching in the static repository browser;
- `scripts/assemble_publications.py`: catalog validation and multi-source
  assembly;
- `scripts/finalize_site_metadata.py`: normalizes canonical and PWA metadata in
  generated HTML, including the post-generated `/guided/` tree;
- `.github/workflows/build-pages.yml`: build-only reusable workflow;
- `.github/workflows/mobile-visual-regression.yml`: same-repository pull-request
  check that consumes the built Pages artifact and validates mobile layout;
- `.github/workflows/deploy-pages.yml`: deployment route restricted to pushes
  to `site`.

## Local validation

Check out the four unrelated branches into separate directories, with provider
commits matching `publication-sources.json`, then run the same material stages as
the Pages build:

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
python site/scripts/generate_skill_template_tree.py \
  --repository TakashiSasaki/templates \
  --site-root site-publication \
  --output-root build \
  --skill-root sources/skill
python site/scripts/generate_webapp_template_tree.py \
  --repository TakashiSasaki/templates \
  --site-root site-publication \
  --output-root build \
  --webapp-root sources/webapp
python site/scripts/generate_repository_file_previews.py \
  --repository TakashiSasaki/templates \
  --site-root site-publication \
  --output-root build \
  --publication skill=sources/skill \
  --publication policy=sources/policy \
  --publication webapp=sources/webapp
zensical build --config-file build/zensical.toml --clean --strict
python site/scripts/finalize_site_metadata.py \
  --site-root build/site \
  --canonical-url https://templates.moukaeritai.work/
python site/scripts/generate_repository_browser.py \
  --repository TakashiSasaki/templates \
  --output-root build/site \
  --branch site=site \
  --branch skill=sources/skill \
  --branch policy=sources/policy \
  --branch webapp=sources/webapp
python site/scripts/generate_index_navigation.py \
  --repository TakashiSasaki/templates \
  --output build/index-navigation.json \
  --provider skill=sources/skill \
  --provider policy=sources/policy \
  --provider webapp=sources/webapp
python site/scripts/generate_index_navigation_viewer.py \
  --repository TakashiSasaki/templates \
  --graph build/index-navigation.json \
  --site-root site-publication \
  --output-root build/site \
  --provider skill=sources/skill \
  --provider policy=sources/policy \
  --provider webapp=sources/webapp
python site/scripts/finalize_site_metadata.py \
  --site-root build/site/guided \
  --canonical-url https://templates.moukaeritai.work/
python site/scripts/write_publication_provenance.py \
  --output build/site/build-provenance.json \
  --repository TakashiSasaki/templates \
  --site-commit "$(git -C site rev-parse HEAD)" \
  --publication-commit "skill=$(git -C sources/skill rev-parse HEAD)" \
  --publication-commit "policy=$(git -C sources/policy rev-parse HEAD)" \
  --publication-commit "webapp=$(git -C sources/webapp rev-parse HEAD)"
python site/scripts/validate_site_links.py \
  --site-root build/site \
  --config-file build/zensical.toml
python site/scripts/check_mobile_layout.py \
  --site-root build/site \
  --browser "$(command -v google-chrome)" \
  --output-root build/mobile-visual
```

The mobile layout check requires a local Chrome executable and writes
390×844 screenshots plus `metrics.json` under `build/mobile-visual`; geometry is
validated at 360×800, 390×844, and 412×915. Use workflow-call revision overrides
only for deliberate compatibility testing. Normal builds use the reviewed
full-SHA lock file. Repository-tree links, preview URLs, repository-browser
snapshots, and guided navigation all use the actual checked-out commits, so
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

The Pages custom-domain setting must remain `templates.moukaeritai.work`, and
Enforce HTTPS must be enabled after GitHub has approved the certificate. The
deployment workflow verifies the configured Pages base URL, host, and empty base
path before invoking `actions/deploy-pages`.

A provider publication change requires a provider PR and a coordinated site PR.
Merge the provider PR with a merge commit, update the site source lock to that
merge commit's full SHA, verify the integrated build, and only then merge the
site PR.
