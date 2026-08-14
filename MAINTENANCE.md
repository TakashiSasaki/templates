# Documentation site maintenance

This file applies only to the unrelated `site` branch.

## Branch responsibilities

- `skill`, `policy`, and `webapp` own their canonical documentation, their provider-owned `index.md` navigation, and their own `docs/publication-catalog.json` files. They do not own or initiate GitHub Pages deployment.
- `site` is the repository default branch and owns the integrated portal home, cross-publication navigation, source locking, assembly, generated complete-source repository trees, generated copyable-template trees, bounded inline file previews, the bounded static repository browser, the deterministic index-navigation graph and `/guided/` projection of the exact provider inputs, explicit translation-reader publication/finalization, generated-site validation, build provenance, and the only Pages deployment workflow.
- Generated Markdown, translation publication maps, preview HTML, repository-browser HTML, guided-navigation JSON/HTML, and final site HTML are temporary build artifacts and must not be committed.

The four major branches have unrelated histories. Do not merge, rebase, or cherry-pick between them merely to publish documentation. The site build checks out each publication independently at the full commit recorded in `publication-sources.json`.

## Change process

1. Make canonical documentation, provider-owned index navigation, catalog changes, and provider-owned translation metadata on the provider branch that owns them.
2. Merge the provider pull request and record its actual merge commit SHA.
3. Branch the coordinated portal change from `site` and open a pull request whose base is `site`.
4. Update `publication-sources.json` to the reviewed provider merge commit using a lowercase full 40-character SHA.
5. Update `site-manifest.json` whenever a publication document is added or removed, or when reader-facing titles, hierarchy, ordering, or generated destinations change. Do not derive this reader-oriented manifest from provider `index.md` files. Translation routes remain a separate derivative projection and are not added to the canonical navigation manifest.
6. Require the integrated documentation build, explicit translation publication and reader finalization, complete repository-tree generation, Skill and Webapp copyable-template tree generation, inline-preview generation, static repository-browser generation, index-navigation graph generation, guided-viewer generation and metadata normalization, build provenance, and generated-link validation to succeed against the exact locked commits before merging the site pull request.

Provider catalog and site navigation coverage must be exact. A coordinated change can therefore fail intentionally between the provider merge and the corresponding site update.

## Publication catalogs

Each publication root contains `docs/publication-catalog.json`.

Catalog schema version 1 contains:

- `schema_version`, the integer `1`;
- a non-empty `documents` array.

Catalog schema version 2 additionally permits an `assets` array for explicit non-Markdown asset roots.

Each document entry contains exactly:

- `id`, a stable lowercase kebab-case identifier within that publication;
- `source`, a safe relative POSIX Markdown path;
- `optional`, a boolean;
- `home`, a boolean.

Each catalog defines exactly one non-optional home document. Document IDs and source paths are unique within the publication. Catalog paths reject absolute paths, backslashes, colon-bearing Windows or NTFS-ambiguous forms, empty or dot components, parent traversal, `.git` components in any case, and symlink traversal.

Schema version 2 asset entries contain exactly `source`, `destination`, and `optional`. Asset source and destination roots must be unique and non-overlapping. Asset trees may not contain symlinks, `.git` subtrees, or Markdown files. Schema version 1 retains the legacy top-level `assets/` convention for non-Markdown files only; Markdown under that directory is not published implicitly.

## Navigation manifest

`site-manifest.json` uses schema version 2 and contains exactly:

- `schema_version`, the integer `2`;
- `home`, identifying one `publication` and `document` pair;
- `navigation`, a non-empty array.

Each navigation node is exactly one of:

- a page with `title`, `publication`, `document`, and `destination`;
- a section with `title` and a non-empty `children` array.

A page is identified by the namespaced pair `publication:document`, such as `skill:overview`. Page nodes do not duplicate catalog-owned source paths, optionality, or home flags.

The assembler enforces these invariants before publication:

- page and section fields may not be mixed;
- unsupported fields are rejected;
- every `publication:document` pair and generated destination is unique;
- every catalog document appears exactly once in navigation;
- unknown or omitted catalog documents are rejected;
- destination values are safe relative POSIX Markdown paths;
- the first page is the declared global home and generates `index.md`;
- a missing source is omitted only when its catalog entry is optional;
- an empty section after optional-document filtering is omitted.

Page and section order are public information architecture and must be reviewed as such.

## Repository-tree publication preparation

Repository trees are generated pages, not canonical provider documents. `scripts/prepare_repository_tree_publication.py` creates a temporary site publication root before assembly. It copies the site-owned documentation templates and assets without following symlinks, then adds exactly six generated document declarations:

- `repository-trees/index.md`;
- `repository-trees/skill.md`;
- `repository-trees/policy.md`;
- `repository-trees/webapp.md`;
- `repository-trees/skill/template.md`;
- `repository-trees/webapp/template.md`.

The first four documents are grouped under the generated `Repository trees` navigation section. The Skill and Webapp copyable-template documents are separate generated navigation entries. The canonical `docs/publication-catalog.json` and `site-manifest.json` are not modified in place. The temporary declarations are passed through the ordinary assembler, so exact catalog-to-navigation coverage and destination validation still apply.

The Skill declaration is enabled only when the site source contains its template page. This preserves compatibility for reduced test fixtures while the production site always includes both copyable-template pages. A present nested template must be a regular file and may not be a symlink.

The preparation output root may not be a symlink, filesystem root, or a path overlapping the canonical site source. A non-empty output directory is replaced only when it contains the exact tool-owned marker.

## Complete repository-tree generation

`scripts/generate_repository_trees.py` runs after assembly and before either copyable-template generator. It uses `git ls-tree --full-tree -r -t -z HEAD` for each checked-out provider repository.

Consequently:

- only tracked Git entries are listed;
- untracked working-tree files and `.git` administration data are excluded;
- directory, regular-file, symlink, and gitlink types come from Git metadata;
- symlinks and gitlinks are displayed but never followed;
- path text is HTML-escaped and path bytes are percent-encoded in GitHub URLs;
- directories precede files and each group is sorted deterministically;
- all GitHub links use the exact full commit returned by `git rev-parse HEAD`;
- cataloged Markdown receives a Pages link plus an immutable source link;
- uncataloged files link only to GitHub and their contents are not copied by the tree generator.

Workflow-call revision overrides are reflected in generated links because the generator reads the actual checked-out commit rather than the normal lock-file value.

## Skill copyable-template tree generation

`scripts/generate_skill_template_tree.py` runs after the complete provider trees and before the Webapp copyable-template generator. It selects only the tracked `template/` subtree from the locked Skill checkout and renders that subtree as the Skill root received by a downstream template consumer.

Displayed paths are relative to the copy boundary, while immutable GitHub links continue to identify canonical `template/...` paths at the exact checked-out Skill commit. Cataloged Markdown files retain their human-readable Pages links. The complete Skill source tree remains the audit view for publication integration, distribution validation, canonical fixtures, negative fixtures, and source-maintainer tests.

Inline previews are owned by the complete Skill source-tree page. The dedicated Skill copyable-template page does not receive an inline preview panel or duplicate preview links. It retains immutable source links for every entry, keeping provider and aggregate preview byte budgets closed.

The generated page must show `SKILL.md` directly below the displayed copy root. Absence of a tracked `template/` directory is a hard build error rather than a reason to render an empty or fallback tree.

## Webapp copyable-template tree generation

`scripts/generate_webapp_template_tree.py` runs after the Skill copyable-template generator and before inline-preview generation. It selects only the tracked `template/` subtree from the locked Webapp checkout and renders that subtree as the repository root received by a downstream template consumer.

Displayed paths are relative to the copy boundary, while immutable GitHub links continue to identify canonical `template/...` paths at the exact checked-out Webapp commit. Cataloged Markdown files retain their human-readable Pages links. The complete Webapp source tree remains the audit view for publication tooling, distribution validation, clean-room fixtures, and source-maintainer tests.

Inline previews are owned by the complete Webapp source-tree page. The dedicated Webapp copyable-template page does not receive an inline preview panel or duplicate preview links. It retains immutable source links for every entry, keeping provider and aggregate preview byte budgets closed.

## Inline file-preview generation

`scripts/generate_repository_file_previews.py` runs after all repository-tree generators and before static-site generation. It uses the object IDs emitted by `git ls-tree`, then reads the exact committed blobs with `git cat-file`. It does not read preview content through mutable working-tree paths.

A file receives a preview link only when all of the following hold:

- the Git entry is a regular file, not a symlink or gitlink;
- the blob is at most 256 KiB;
- the complete blob decodes as strict UTF-8;
- the decoded text contains no NUL or disallowed control characters;
- provider candidate and aggregate byte budgets remain within the configured bounds.

The generator HTML-escapes repository text and writes deterministic preview pages under `repository-trees/previews/<publication>/<full-sha>/`. Preview pages have a restrictive content security policy and are loaded by the repository-tree page through an iframe with an empty `sandbox` attribute and `referrerpolicy="no-referrer"`. The immutable GitHub source link remains present for every file. Binary, oversized, invalid-text, symlink, and gitlink entries remain GitHub-only.

`assets/javascripts/repository-tree-viewer.js` updates the shared viewer label, source link, and iframe title when a preview link is selected. It does not inject repository content into the parent page and does not use `innerHTML`.

## Static repository-browser generation

`scripts/generate_repository_browser.py` generates the standalone `/files/` surface after the strict Zensical build and site-metadata normalization, and before final public-URL and generated-link validation. It receives the exact `site`, `skill`, `policy`, and `webapp` checkouts used by the build and writes branch entry pages plus hashed file-view pages under `build/site/files/`.

The browser derives paths from `git ls-tree`, reads regular-file content from exact blob object IDs with `git cat-file`, never follows symlinks or gitlinks, and labels every branch view with the checked-out full 40-character SHA. Text rendering is limited to strict UTF-8 regular files of at most 1 MiB, with a 64 MiB candidate-content ceiling per branch. Invalid, binary, control-bearing, or oversized files receive local fallback viewer pages instead of active content. Pygments highlighting is performed at build time; repository content is HTML-escaped and displayed in a sandboxed iframe under restrictive content security policy.

Desktop-width browser pages retain the split tree-and-file layout. At viewports up to 800 px, the unenhanced HTML deliberately keeps the existing 42/58 split as a no-JavaScript fallback. When the same-origin `repository-browser.js` controller loads, it adds `repository-browser-enhanced` to the document root and uses `data-mobile-view="files"` or `data-mobile-view="content"` on the browser shell so exactly one pane fills the dynamic viewport. Selecting a file switches to content; the explicit `Files` button switches back without rebuilding the tree, so open `<details>` state and tree scroll position are retained. The hidden pane is made `inert` while narrow and both panes are interactive on desktop. `data-mobile-view` is intentionally retained across desktop-width transitions as the preferred pane to restore if the viewport becomes narrow again. Swipe gestures and browser-history interception are not part of this controller because source content may require horizontal scrolling and platform back gestures must remain unambiguous.

`prepare_browser_root()` is intentionally fail-closed. `build/site` must already exist as a regular directory, but `build/site/files/` must not exist at invocation time. The generator writes `.repository-browser-root` as ownership/provenance metadata but does not use that marker to delete or replace a pre-existing browser tree. This differs deliberately from the assembly workspace: a browser re-run should regenerate the enclosing Pages artifact or explicitly remove the prior generated `files/` subtree rather than grant the browser generator recursive deletion authority.

The stable public entry points are `/files/` and `/files/<branch>/`. Hashed `content/*.html` paths are implementation details. The parent tree retains immutable full-SHA GitHub links, while browser rendering itself has no runtime GitHub API, raw-content, CDN, or client-side syntax-highlighting dependency.

## Index-guided navigation generation

`scripts/generate_index_navigation.py` runs after the static repository browser has been generated. For `skill`, `policy`, and `webapp`, it starts from the provider-owned `docs/index.md`, reads index content from exact committed Git blobs, recursively follows links that resolve to child `index.md` files, and writes the schema-versioned graph to `build/index-navigation.json`.

The graph preserves provider heading order, link labels, descriptions, source lines, normalized fragments, and target classifications. Repository-relative links may contain `..` only when normalization remains inside the repository. Broken internal targets, unsafe schemes, URL queries, invalid UTF-8, control characters, non-regular linked indexes, duplicate section headings, and repository-root escapes fail the build. Cycles, maximum depth, and indexes reached from multiple distinct parent indexes remain diagnostics rather than publication-policy failures.

`scripts/generate_index_navigation_viewer.py` consumes that graph without reparsing provider Markdown and writes `/guided/`, `/guided/<provider>/`, nested reachable index pages, and `/guided/graph.json`. The graph revision for each provider must equal the checked-out full SHA. Cataloged document links resolve to the existing reader publication, fragment-free uncataloged regular-file targets resolve to the same immutable `/files/` snapshot, uncataloged regular-file targets with any fragment use the exact full-SHA immutable GitHub source, and index-to-index links remain within `/guided/`. Provider labels and descriptions are HTML-escaped; the standalone pages execute no repository-supplied scripts.

Guided pages are generated after the normal whole-site metadata pass, so `scripts/finalize_site_metadata.py` runs a second time with `--site-root build/site/guided`. This pass preserves the canonical/manifest/theme metadata contract, augments each `Page path` marker with the deployed public URL copy action, and adds an immutable GitHub URL copy action only when exactly one real provider source link exists. It rejects ambiguous or non-immutable GitHub targets instead of guessing, permits only the same-origin `/javascripts/guided-copy.js` helper through `script-src 'self'`, and keeps the `/guided/` landing page public-URL-only because it has no corresponding provider source.

The stable guided entry points are `/guided/`, `/guided/skill/`, `/guided/policy/`, and `/guided/webapp/`. The provider indexes remain the authority for guided semantics. `site-manifest.json` remains the separate reader-oriented publication information architecture and must not be silently regenerated from the guided graph.

## Assembly output boundary

`scripts/assemble_publications.py` assembles the prepared site publication and all locked provider publications into one temporary Zensical project.

The output root may not be a symlink, filesystem root, current working directory or its ancestor, a regular file, or a path that overlaps any publication root. A pre-existing non-empty output directory is removed only when it contains the assembler-owned `.publication-assembly-root` marker with the expected value. This prevents a mistyped `--output-root` from deleting unrelated data.

Asset traversal explicitly rejects file and directory symlinks before descending and never follows them.

## Generated link integrity

The build validates links after Zensical generates final HTML, after the standalone repository browser is added, after guided navigation is generated and normalized, and after translation reader metadata is finalized. `scripts/validate_site_links.py` reads `project.site_url`, checks generated pages and assets, validates same-site paths and fragments, and rejects links that escape the configured Pages path or target missing generated content. This includes repository-tree links to generated same-origin preview pages, landing-page links to `/files/` and `/guided/`, guided index-to-index fragment links, and per-document translation switcher links.

External origins, non-HTTP schemes, same-origin URLs outside the configured project path, and browser text fragments are outside the generated artifact and are not validated as local content. Repository source links are external immutable GitHub links; their URL construction is covered by unit tests rather than network requests during the build.

## Build provenance

Every uploaded Pages artifact contains `/build-provenance.json` with deterministic schema version 2:

- `schema_version`, the integer `2`;
- `repository`, currently `TakashiSasaki/templates`;
- `site_commit`, the full commit checked out into `site-source`;
- `publication_commits`, an object mapping `skill`, `policy`, and `webapp` to their checked-out full commits.

`scripts/write_publication_provenance.py` receives provider commits through repeated `--publication-commit NAME=SHA` arguments. Names are lowercase kebab-case. Commit values are lowercase full 40-character SHAs. Duplicate publication names, mutable refs, abbreviated SHAs, invalid repository identifiers, missing output directories, and symbolic-link outputs are rejected.

The file excludes timestamps, workflow run IDs, and mutable refs. It identifies build inputs but is not a cryptographic signature or artifact attestation.

## Published deployment metadata

The deployment workflow captures a timestamp with `TZ=Asia/Tokyo` before invoking the reusable build. The accepted format is exactly `YYYY-MM-DD HH:MM:SS JST`. An empty timestamp produces the stable footer text `Preview build (not deployed)`.

`project.site_url` must remain `https://templates.moukaeritai.work/`. The configured domain is hosted at the root path, so generated same-origin links must not retain `/templates/`. `scripts/finalize_site_metadata.py` performs the generic canonical/PWA metadata normalization pass and rejects duplicate canonical links. For normal generated pages, the same pass also inserts or validates exactly one `/app.webmanifest` link and one `#3f51b5` theme-color element. Sandboxed inline-preview pages deliberately receive canonical metadata only. The `/guided/` tree receives a dedicated post-generation normalization pass. After all normal and guided pages exist, `scripts/finalize_translation_reader.py` replaces generic canonical values with each page's actual public URL, then applies the explicit translation relationships described below. The build also scans generated HTML and XML for the retired GitHub project URL, the custom domain with the retired subpath, and root-relative `/templates/` attributes.

## Translation reader finalization

Provider translations remain non-authoritative derivatives and are never inferred by scanning provider directories. After canonical assembly, `scripts/publish_provider_translations.py` consumes only provider-owned `translations/manifest.json` entries from the same locked provider revisions. It validates translation synchronization and safety, publishes declared Markdown under language-first destinations such as `/ja/policy/...`, rewrites relative document and asset links against the canonical publication mapping, applies search exclusion to derivative translation pages, and writes the temporary `build/translation-publication.json` projection used by the HTML finalizer.

`scripts/finalize_translation_reader.py` consumes only that build-owned projection. It does not rediscover provider translations. The finalizer assigns self-canonical URLs to ordinary generated pages; for translated document groups it keeps the unsuffixed English page canonical, sets each derivative page's canonical URL to the English page, emits `hreflang` alternates, sets the generated HTML `lang` attribute, and injects one compact document-language switcher after the H1. An English canonical page receives links only for translations actually declared for that document, while each derivative page always links back to `English · Canonical`. Multiple declared translation languages for the same canonical page are grouped into one switcher rather than duplicated components.

`assets/stylesheets/translation-reader.css` owns the compact reader presentation and mobile wrapping behavior. Provider-owned non-authoritative notices remain visible and receive compact styling on non-English pages. Translation pages remain outside the canonical `site-manifest.json` navigation and are excluded from the initial search index, so English remains the default discovery and authority surface.

## PWA shell maintenance

The installable shell is owned entirely by the `site` branch:

- `assets/app.webmanifest` defines the root-scoped application identity, start URL, scope, standalone display mode, theme colors, and SVG icon declarations;
- `assets/icon.svg` is the shared scalable PWA icon and Zensical favicon;
- `assets/javascripts/pwa.js` preserves the static manifest and theme metadata when present and registers `/service-worker.js` with root scope in a secure context;
- `assets/service-worker.js` precaches only `/app.webmanifest` and `/icon.svg`; document navigation remains network-first, same-origin non-navigation document requests are not intercepted by the static cache, and failed offline document navigation returns an explicit HTTP 503 response instead of stale documentation.

Do not precache the portal home or generated documentation pages. Provider publications change independently, and document URLs must remain outside the static shell cache regardless of whether navigation arrives as a browser navigation request or an instant-navigation fetch. When cached static asset contents or cache strategy change, increment `CACHE_NAME` so the activation handler can delete the previous shell cache.

`tests/test_pwa_assets.py` owns the source-level PWA contract, including manifest shape, shared SVG safety, favicon and registration wiring, generated metadata insertion and preview exclusion, duplicate or conflicting metadata rejection, document exclusion from static caching, cache-version transition, and the guaranteed `Response` fallback. The Pages build separately verifies that the manifest, icon, service worker, registration script, manifest link, and theme-color metadata exist in the generated artifact, including the post-generated guided pages.

## Build and deployment policy

`.github/workflows/build-pages.yml` is build-only. It may run for pull requests targeting `site` or through `workflow_call`. It has `contents: read`, pins Python before executing repository Python code, resolves the locked publication revisions, checks out all publications, runs tests, prepares the temporary tree-page publication, assembles the portal, publishes explicitly declared synchronized translations and their temporary reader map, generates complete provider trees, generates Skill and Webapp copyable-template trees, generates bounded inline previews, strictly builds the site, normalizes canonical and PWA metadata, generates the bounded static repository browser, generates the immutable provider index-navigation graph and `/guided/` viewer, normalizes guided metadata, finalizes per-page canonical URLs and translation-reader metadata from the explicit translation publication map, verifies the generated public-URL boundary and Pages entry points, records provenance, validates links, and uploads a Pages artifact. It contains no deployment job or Pages write authority.

`.github/workflows/mobile-visual-regression.yml` is a pull-request-only consumer of that build artifact for same-repository pull requests targeting `site`. It has only `contents: read` and `actions: read`, waits for the matching successful `build-pages.yml` run at the exact pull-request head SHA, downloads that run's `github-pages` artifact, installs the controller pinned by `requirements-visual.txt` plus its matching Playwright Chromium build, and runs `scripts/check_mobile_layout.py` against the already-built site. The checker measures 360×800, 390×844, and 412×915 viewports, rejects page-wide horizontal overflow and mobile-density regressions, verifies full repository revisions remain on one line inside their local table scroll container, and enforces the 48 px portal-action floor. It also uploads 390×844 screenshots and `metrics.json` as short-lived review evidence. It does not build or deploy Pages and does not run repository code from fork pull requests.

`.github/workflows/deploy-pages.yml` is the sole deployment authority. Its only trigger is a push to `site`. The metadata, build, and deploy jobs each require:

```text
github.repository == TakashiSasaki/templates
github.event_name == push
github.ref == refs/heads/site
```

The metadata job captures the JST deployment timestamp. The build job invokes the reusable workflow at the exact pushed `site` SHA with `contents: read` only. The final deployment job alone receives `pages: write` and `id-token: write`, owns the `github-pages` environment, configures Pages, verifies that the configured Pages base URL is `https://templates.moukaeritai.work`, verifies the host and empty base path, and then deploys the uploaded artifact.

Default-branch status is not an authorization input. Changing the default branch therefore cannot authorize deployment from `skill`, `policy`, `webapp`, or another ref. Pull requests run only the reusable build workflow and cannot reach the deployment workflow because its trigger contains only a push to `site`.

Expected behavior:

| Event | Build artifact | Footer metadata | Pages deployment |
|---|---:|---|---:|
| pull request targeting `site` | yes | preview | no |
| push to `site` | yes | JST deployment timestamp | yes |
| `workflow_call` | yes | preview unless explicitly supplied | no |
| workflow on a provider branch | branch-local only | not applicable | no |
| push to any other branch | no site deployment workflow | not applicable | no |

For same-repository pull requests targeting `site`, the mobile visual regression workflow additionally consumes the successful preview artifact; it never grants deployment authority.

`deployment-state.json` records the active state and the final reviewed Skill revision. `DEPLOYMENT_RESTORATION.md` records the completed gates and restored authority boundary.

## Dependency updates

`requirements.txt` pins Zensical and build-time syntax-highlighting dependencies, including Pygments. `requirements-visual.txt` separately pins the Playwright controller used only by the mobile visual regression workflow; its matching Chromium build is installed by Playwright rather than committed to the repository. Update either dependency set intentionally, run the relevant full build and mobile visual checks, and review generated navigation, translation-reader routes and switchers, complete repository trees, both copyable-template trees, inline previews, the static repository browser, the guided navigation surface, canonical URLs, provenance, link-validation results, mobile geometry, and screenshots before merging.

## Local validation

Check out the four unrelated branches into separate directories at the commits recorded in `publication-sources.json`, then run:

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
python site/scripts/finalize_translation_reader.py \
  --site-root build/site \
  --translation-map build/translation-publication.json \
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
```

The mobile layout command uses the Chromium build matched to the pinned Playwright controller and writes screenshots plus `metrics.json` under `build/mobile-visual`. Use workflow-call revision overrides only for deliberate compatibility testing. Normal builds use the reviewed full-SHA lock file. Repository-tree links, preview URLs, repository-browser snapshots, guided-navigation graph/viewer output, and translation reader routes always use the actual checked-out commits.