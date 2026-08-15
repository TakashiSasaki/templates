# Integrated documentation site

The `site` branch is the only GitHub Pages build and deployment implementation
for `TakashiSasaki/templates`. It assembles one reader-oriented documentation
portal from branch-owned publication catalogs in the unrelated `skill`,
`policy`, and `webapp` histories.

The public portal is `https://templates.moukaeritai.work/`. The custom domain is
served from the domain root rather than from the former `/templates/` project
path.

The normative cross-branch publication rules are documented in
[`PUBLISHING.md`](PUBLISHING.md). Canonical terminology ownership, glossary
schema rules, localized lexical labels, and glossary integration are documented
in [`GLOSSARY.md`](GLOSSARY.md). Build identity, per-document revision metadata,
PWA freshness-state vocabulary, and cache/fallback invariants are documented in
[`FRESHNESS.md`](FRESHNESS.md).

## Ownership model

Each provider branch owns its public source boundary in
`docs/publication-catalog.json`:

- stable document IDs within its publication namespace;
- canonical Markdown source paths;
- required versus optional documents;
- its section landing document;
- explicit non-Markdown asset roots under catalog schema version 3;
- an optional canonical `docs/glossary.yml` source under catalog schema version 3.

All live publication catalogs use schema version 3. Older catalog schemas are
retired and are rejected by the Site publication assembler.

The catalog is an explicit allowlist for rendered documentation, provider
assets, and declared canonical glossary input. Individual glossary terms are
not catalog entries; adding a term to a declared glossary does not require a
catalog change. Repository inventory previews are a separate bounded surface:
they do not add files to the documentation catalog and are generated only from
eligible immutable Git blobs under the constraints in `PUBLISHING.md`.

The `site` branch owns:

- the global portal home;
- cross-publication navigation, titles, ordering, and generated destinations;
- full-commit source locking in `publication-sources.json`;
- deterministic integration of declared provider glossaries into
  `/glossary/index.json`, with provider/path/full-SHA provenance;
- generated repository-tree inventories and sandboxed text previews for the
  exact checked-out revisions;
- the bounded static repository browser for immutable source inspection;
- the deterministic index-navigation graph and `/guided/` projection of
  provider-owned `index.md` navigation at the same locked revisions;
- integrated assembly, strict site generation, link validation, provenance,
  freshness identity, and Pages deployment.

A document is identified by the pair `publication:document`, such as
`skill:overview`, `policy:overview`, or `webapp:overview`. A glossary concept is
identified independently by its stable glossary term ID.

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

The machine-readable integrated terminology registry is published at
`/glossary/index.json`. The Site also renders a static human-readable projection
of that same validated model at `/glossary/`; the viewer does not create a
second terminology authority or imply that search is part of glossary schema
version 1.

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

- `docs/publication-catalog.json`: the canonical site portal publication and
  optional glossary-source declaration;
- `docs/glossary.yml`: Site-owned canonical glossary entries;
- `GLOSSARY.md`: normative glossary schema, authority, ownership, and
  localization contract;
- `FRESHNESS.md`: normative build identity, per-document revision metadata,
  runtime freshness-state, cache namespace, and stale-fallback contract;
- `docs/repository-trees/*.md`: reviewed templates for generated tree pages;
- `site-manifest.json`: canonical integrated navigation before generated
  inventory augmentation;
- `publication-sources.json`: reviewed full-SHA provider inputs;
- `PUBLISHING.md`: normative public-boundary and deployment policy;
- `scripts/prepare_repository_tree_publication.py`: creates a temporary site
  publication with validated tree-page catalog and navigation entries;
- `scripts/assemble_publications.py`: canonical schema-v3 publication assembly
  engine and Python API. Direct imports and CLI execution both reject retired
  and unknown publication-catalog schemas;
- `scripts/assemble_publications_v3.py`: stable schema-v3 CLI alias used by the
  existing workflow and translation tooling; it re-exports the canonical
  assembler without a second loader or runtime monkey-patch;
- `scripts/glossary.py`: strict glossary parsing, schema validation, and
  cross-provider integration logic;
- `scripts/generate_glossary.py`: emits deterministic `/glossary/index.json`
  source data with exact provider provenance and, in its CLI publication path,
  renders the sibling `/glossary/index.html` viewer;
- `scripts/generate_glossary_viewer.py`: validates the integrated glossary JSON
  again at the rendering boundary and produces the static `/glossary/` human
  projection;
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
- `scripts/generate_freshness_metadata.py`: projects the exact build revisions
  into `/site-version.json`, annotates eligible generated HTML with the Site
  revision, and verifies both outputs before artifact upload;
- `scripts/check_mobile_layout.py`: measures rendered phone-width geometry with
  Playwright-managed Chromium and writes screenshot and metric evidence;
- `scripts/check_pwa_freshness.py`: exercises document revalidation, static-shell
  refresh, service-worker update propagation, freshness capability messaging,
  and offline fallbacks in Chromium;
- `requirements-visual.txt`: pins the visual-regression browser controller;
- `assets/javascripts/repository-tree-viewer.js`: updates and focuses the shared
  viewer without rendering repository content in the parent document;
- `assets/javascripts/repository-browser.js`: progressive-enhancement controller
  for narrow-viewport Files/Content switching in the static repository browser;
- `scripts/finalize_site_metadata.py`: normalizes canonical and PWA metadata in
  generated HTML, including the post-generated `/guided/` tree;
- `.github/workflows/build-pages.yml`: build-only reusable workflow;
- `.github/workflows/mobile-visual-regression.yml`: same-repository pull-request
  check that consumes the built Pages artifact and validates mobile layout plus
  the browser-level PWA freshness lifecycle;
- `.github/workflows/deploy-pages.yml`: deployment route restricted to pushes
  to `site`.

## Local validation

Check out the four unrelated branches into separate directories, with provider
commits matching `publication-sources.json`, then run the same material stages as
the Pages build. All publication catalogs must use schema version 3. The stable
`assemble_publications_v3.py` path used below delegates to the same canonical
schema-v3 engine exposed by `assemble_publications.py`:

```sh
python -m unittest discover --start-directory site/tests --verbose
python site/scripts/prepare_repository_tree_publication.py \
  --site-root site \
  --output-root site-publication
python site/scripts/assemble_publications_v3.py \
  --publication site=site-publication \
  --publication skill=sources/skill \
  --publication policy=sources/policy \
  --publication webapp=sources/webapp \
  --site-root site-publication \
  --output-root build
python site/scripts/publish_provider_translations.py \
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
python site/scripts/generate_glossary.py \
  --repository TakashiSasaki/templates \
  --output build/site/glossary/index.json \
  --publication site=site-publication \
  --revision "site=$(git -C site rev-parse HEAD)" \
  --publication skill=sources/skill \
  --revision "skill=$(git -C sources/skill rev-parse HEAD)" \
  --publication policy=sources/policy \
  --revision "policy=$(git -C sources/policy rev-parse HEAD)" \
  --publication webapp=sources/webapp \
  --revision "webapp=$(git -C sources/webapp rev-parse HEAD)"
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
python -m pip install -r site/requirements-visual.txt
python -m playwright install --with-deps chromium
python site/scripts/check_mobile_layout.py \
  --site-root build/site \
  --output-root build/mobile-visual
python site/scripts/check_pwa_freshness.py \
  --site-root build/site \
  --output build/mobile-visual/pwa-freshness.json
```

The mobile layout check uses the Chromium build matched to the pinned Playwright
controller and writes 390×844 screenshots plus `metrics.json` under
`build/mobile-visual`; geometry is validated at 360×800, 390×844, and 412×915.
The PWA freshness check uses the same browser installation and writes
`pwa-freshness.json` while validating HTTP-cache revalidation, static-shell
convergence, worker update propagation, the live freshness-capability message
contract, and explicit offline 503 fallbacks. The provenance command above also
writes and verifies `/site-version.json` plus the per-page
`templates-site-revision` metadata described in `FRESHNESS.md`.
Use workflow-call revision overrides only for deliberate compatibility testing.
Normal builds use the reviewed full-SHA lock file. Repository-tree links,
preview URLs, repository-browser snapshots, guided navigation, and glossary
provenance all use the actual checked-out commits, so override builds remain
internally consistent.

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
