# Documentation site maintenance

This file applies only to the unrelated `site` branch.

## Branch responsibilities

- `skill`, `policy`, and `webapp` own their canonical documentation, their provider-owned `index.md` navigation, their own `docs/publication-catalog.json` files, and any canonical `docs/glossary.yml` terminology assigned to that provider. They do not own or initiate GitHub Pages deployment.
- `site` is the repository default branch and owns the integrated portal home, cross-publication navigation, source locking, assembly, deterministic glossary integration and `/glossary/` projection, build-time inline Glossary annotation, generated complete-source repository trees, generated copyable-template trees, bounded inline file previews, the bounded static repository browser, the deterministic index-navigation graph and `/guided/` projection of the exact provider inputs, explicit translation-reader publication/finalization, generated-site validation, build provenance, freshness identity, and the only Pages deployment workflow.
- Generated Markdown, integrated glossary JSON/HTML, translation publication maps, preview HTML, repository-browser HTML, guided-navigation JSON/HTML, and final annotated site HTML are temporary build artifacts and must not be committed.

The four major branches have unrelated histories. Do not merge, rebase, or cherry-pick between them merely to publish documentation. The site build checks out each publication independently at the full commit recorded in `publication-sources.json`.

## Change process

1. Make canonical documentation, provider-owned index navigation, glossary terminology, catalog changes, and provider-owned translation metadata on the provider branch that owns them.
2. Validate the provider pull request locally and in CI. Glossary-bearing provider changes should also run the reusable Site compatibility build against the proposed provider revision so the canonical glossary parser checks term IDs, origin-specific fields, localized labels, authority metadata, related-term references, and cross-provider conflicts before merge.
3. Merge the provider pull request and record its actual merge commit SHA.
4. Branch the coordinated portal change from `site` and open a pull request whose base is `site`.
5. Update `publication-sources.json` to the reviewed provider merge commit using a lowercase full 40-character SHA.
6. Update `site-manifest.json` whenever a publication document is added or removed, or when reader-facing titles, hierarchy, ordering, or generated destinations change. Do not derive this reader-oriented manifest from provider `index.md` files. Translation routes remain a separate derivative projection and are not added to the canonical navigation manifest. A glossary-term addition does not by itself require a navigation-manifest change.
7. Require the integrated documentation build, glossary integration and viewer generation, explicit translation publication and reader finalization, complete repository-tree generation, Skill and Webapp copyable-template tree generation, inline-preview generation, static repository-browser generation, index-navigation graph generation, guided-viewer generation and metadata normalization, build-time Glossary inline annotation, build provenance and freshness-identity projection/verification, and generated-link validation to succeed against the exact locked commits before merging the site pull request.

Provider catalog and site navigation coverage must be exact. A coordinated change can therefore fail intentionally between the provider merge and the corresponding site update.

## Publication catalogs

Each publication root contains `docs/publication-catalog.json`.

The current canonical catalog contract is schema version 3. It contains:

- `schema_version`, the integer `3`;
- a non-empty `documents` array;
- an optional `assets` array for explicit non-Markdown asset roots;
- an optional `glossary` object containing exactly one `source` field.

Each document entry contains exactly:

- `id`, a stable lowercase kebab-case identifier within that publication;
- `source`, a safe relative POSIX Markdown path;
- `optional`, a boolean;
- `home`, a boolean.

Each catalog defines exactly one non-optional home document. Document IDs and source paths are unique within the publication. Catalog paths reject absolute paths, backslashes, colon-bearing Windows or NTFS-ambiguous forms, empty or dot components, parent traversal, `.git` components in any case, and symlink traversal.

Asset entries contain exactly `source`, `destination`, and `optional`. Asset source and destination roots must be unique and non-overlapping. Asset trees may not contain symlinks, `.git` subtrees, or Markdown files.

When `glossary` is present, `glossary.source` must be a safe relative `.yml` path to an existing regular file that does not traverse symlinks and does not overlap an asset source. Individual terms are not listed in the publication catalog, so adding a term to an already declared glossary does not require a catalog change.

## Glossary maintenance

`GLOSSARY.md` is the normative glossary contract. Canonical provider terminology lives in the semantic owner's `docs/glossary.yml`; `site` integrates those sources from the same exact provider revisions used for the rest of the publication.

Normal glossary maintenance should preserve these boundaries:

- English `term`, `definition`, and external-term `summary` remain canonical semantic prose;
- `localized_labels`, including Japanese preferred labels and aliases, are lexical discovery metadata only;
- repository-defined concepts use stable globally unique `templates-*` IDs and have one provider owner;
- externally defined concepts use `external-*` IDs and retain explicit external authority metadata;
- `related_terms` may reference only existing stable term IDs and may not self-reference;
- adding a valid term must not require updating a Site-side exhaustive list of all term IDs;
- provider pull requests should run the reusable Site compatibility build before merge, while the later Site lock promotion verifies the exact merged provider SHA again;
- `/glossary/index.json` is the machine-readable integrated model and `/glossary/` is its non-authoritative human projection.

After every normal, guided, translated, and other human-readable HTML surface has been generated and finalized, `scripts/finalize_glossary_annotations.py` consumes `/glossary/index.json` and performs one build-time annotation pass before public-URL and generated-link validation. It derives candidate text only from Glossary terms, aliases, and localized labels, inserts stable `/glossary/#<term-id>` links into eligible document content, skips ambiguous normalized labels rather than guessing, and leaves code, navigation/chrome, existing links, specialized SVG/MathML/template/form text containers, the Glossary viewer, repository-tree viewers, and `/files/` source views untouched. A later valid term, alias, or localized label therefore becomes annotatable automatically when its provider revision is promoted; no Site-side term list or document-specific configuration is maintained.

The browser runtime is progressive enhancement only; it is not the annotation engine. `zensical.template.toml` includes `stylesheets/glossary-inline.css` and `javascripts/glossary-inline.js` globally so the delegated controller remains available across `navigation.instant` transitions, but initial page load performs no Glossary JSON fetch, term-map construction, runtime text scan, or dialog construction. Build-time annotations remain ordinary `/glossary/#<term-id>` anchors as the no-JavaScript and stale-runtime fallback. When the runtime is available, it promotes each annotation to a native button while retaining that fallback URL for the explicit `Open in Glossary` action. Enhanced trigger activation never navigates implicitly: `/glossary/index.json` is fetched only after activation, successful reads open the in-place dialog, and load or lookup failures remain in that dialog with the explicit navigation link. The active trigger exposes `aria-busy="true"` plus a progress cursor while the read-model load is pending, and the pending state is cleared on success, cancellation, navigation races, and error paths. `scripts/finalize_glossary_annotations.py` injects missing runtime assets into annotated standalone pages, including `/guided/`. Annotated guided pages retain `default-src 'none'` and permit only the additional same-origin resources required by this runtime: `script-src 'self'`, `connect-src 'self'`, and `style-src 'self'` alongside an already-required inline-style permission when one is present. Guided pages without Glossary annotations keep their original CSP and receive no Glossary runtime assets.

The initial seed terms are representative test fixtures, not a closed vocabulary. Integration tests may require representative terms and provenance invariants but must permit additional valid terms.

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

Guided pages are generated after the normal whole-site metadata pass, so `scripts/finalize_site_metadata.py` runs a second time with `--site-root build/site/guided`. This pass preserves the canonical/manifest/theme metadata contract, augments each `Page path` marker with the deployed public URL copy action, and adds an immutable GitHub URL copy action only when exactly one real provider source link exists. It rejects ambiguous or non-immutable GitHub targets instead of guessing, permits the same-origin `/javascripts/guided-copy.js` helper through `script-src 'self'`, and keeps the `/guided/` landing page public-URL-only because it has no corresponding provider source. A later Glossary annotation pass may additionally inject the same-origin Glossary stylesheet and controller only on guided pages that actually contain annotations; for those pages it preserves `default-src 'none'`, adds `connect-src 'self'` for the integrated Glossary read model, and adds `style-src 'self'` without broadening any existing script or connection origin.

The stable guided entry points are `/guided/`, `/guided/skill/`, `/guided/policy/`, and `/guided/webapp/`. The provider indexes remain the authority for guided semantics. `site-manifest.json` remains the separate reader-oriented publication information architecture and must not be silently regenerated from the guided graph.

## Assembly output boundary

`scripts/assemble_publications.py` assembles the prepared site publication and all locked provider publications into one temporary Zensical project.

The output root may not be a symlink, filesystem root, current working directory or its ancestor, a regular file, or a path that overlaps any publication root. A pre-existing non-empty output directory is removed only when it contains the assembler-owned `.publication-assembly-root` marker with the expected value. This prevents a mistyped `--output-root` from deleting unrelated data.

Asset traversal explicitly rejects file and directory symlinks before descending and never follows them.

## Generated link integrity

The build validates links after Zensical generates final HTML, after the integrated glossary viewer, the standalone repository browser, and guided navigation are added, after translation reader metadata is finalized, and after eligible human-readable document text has received build-time Glossary annotation. `scripts/validate_site_links.py` reads `project.site_url`, checks generated pages and assets, validates same-site paths and fragments, and rejects links that escape the configured Pages path or target missing generated content. This includes generated Glossary annotation links, repository-tree links to generated same-origin preview pages, landing-page links to `/glossary/`, `/files/`, and `/guided/`, glossary related-term links, guided index-to-index fragment links, and per-document translation switcher links.

External origins, non-HTTP schemes, same-origin URLs outside the configured project path, and browser text fragments are outside the generated artifact and are not validated as local content. Repository source links are external immutable GitHub links; their URL construction is covered by unit tests rather than network requests during the build.

## Build provenance

Every uploaded Pages artifact contains `/build-provenance.json` with deterministic schema version 2:

- `schema_version`, the integer `2`;
- `repository`, currently `TakashiSasaki/templates`;
- `site_commit`, the full commit checked out into `site-source`;
- `publication_commits`, an object mapping `skill`, `policy`, and `webapp` to their checked-out full commits.

`scripts/write_publication_provenance.py` receives provider commits through repeated `--publication-commit NAME=SHA` arguments. Names are lowercase kebab-case. Commit values are lowercase full 40-character SHAs. Duplicate publication names, mutable refs, abbreviated SHAs, invalid repository identifiers, missing output directories, and symbolic-link outputs are rejected.

The provenance command also projects the exact build identity into `/site-version.json` and annotates every eligible generated HTML document with exactly one `<meta name="templates-site-revision">` element. The generated JSON and HTML annotations are re-read and verified before artifact upload; their normative schema and cache/freshness relationship are defined in `FRESHNESS.md`.

`build-provenance.json` excludes timestamps, workflow run IDs, and mutable refs. It identifies build inputs but is not a cryptographic signature or artifact attestation.

## Published deployment metadata

The deployment workflow captures a timestamp with `TZ=Asia/Tokyo` before invoking the reusable build. The accepted format is exactly `YYYY-MM-DD HH:MM:SS JST`. An empty timestamp produces the stable footer text `Preview build (not deployed)`.

`project.site_url` must remain `https://templates.moukaeritai.work/`. The configured domain is hosted at the root path, so generated same-origin links must not retain `/templates/`. `scripts/finalize_site_metadata.py` performs the generic canonical/PWA metadata normalization pass and rejects duplicate canonical links. For normal generated pages, the same pass also inserts or validates exactly one `/app.webmanifest` link and one `#3f51b5` theme-color element. Sandboxed inline-preview pages deliberately receive canonical metadata only. The `/guided/` tree receives a dedicated post-generation normalization pass. After all normal and guided pages exist, `scripts/finalize_translation_reader.py` replaces generic canonical values with each page's actual public URL, then applies the explicit translation relationships described below. The build then applies build-time Glossary annotations to eligible human-readable text before scanning generated HTML and XML for the retired GitHub project URL, the custom domain with the retired subpath, and root-relative `/templates/` attributes.

## Translation reader finalization

Provider translations remain non-authoritative derivatives and are never inferred by scanning provider directories. After canonical assembly, `scripts/publish_provider_translations.py` consumes only provider-owned `translations/manifest.json` entries from the same locked provider revisions. It validates translation synchronization and safety, publishes declared Markdown under language-first destinations such as `/ja/policy/...`, rewrites relative document and asset links against the canonical publication mapping, applies search exclusion to derivative translation pages, and writes the temporary `build/translation-publication.json` projection used by the HTML finalizer.

`scripts/finalize_translation_reader.py` consumes only that build-owned projection. It does not rediscover provider translations. The finalizer assigns self-canonical URLs to ordinary generated pages; for translated document groups it keeps the unsuffixed English page canonical, sets each derivative page's canonical URL to the English page, emits `hreflang` alternates, sets the generated HTML `lang` attribute, and injects one compact document-language switcher after the H1. An English canonical page receives links only for translations actually declared for that document, while each derivative page always links back to `English · Canonical`. Multiple declared translation languages for the same canonical page are grouped into one switcher rather than duplicated components.

`assets/stylesheets/translation-reader.css` owns the compact reader presentation and mobile wrapping behavior. Provider-owned non-authoritative notices remain visible and receive compact styling on non-English pages. Translation pages remain outside the canonical `site-manifest.json` navigation and are excluded from the initial search index, so English remains the default discovery and authority surface.

## PWA shell maintenance

The installable shell and runtime freshness behavior are owned entirely by the `site` branch. `FRESHNESS.md` is the normative document-cache and freshness-state contract.

- `assets/app.webmanifest` defines the root-scoped application identity, start URL, scope, standalone display mode, theme colors, and SVG icon declarations;
- `assets/icon.svg` is the shared scalable PWA icon and Zensical favicon;
- `assets/javascripts/pwa.js` preserves the static manifest and theme metadata when present, registers `/service-worker.js` with root scope and `updateViaCache: "none"` in a secure context, explicitly checks for an updated worker when an active registration already exists, and owns the persistent freshness-status UI used by instant navigation; registration failures and background update-check failures are reported separately;
- `assets/service-worker.js` keeps the versioned static shell cache separate from `templates-portal-documents-v1`. The shell precaches the manifest, icon, Site-owned common stylesheets, and Site-owned local JavaScript needed to render previously viewed documentation. Generated documents are never added to that static shell namespace.

Browser navigations and same-origin document-like instant-navigation requests remain network-first and use `fetch(request, { cache: "no-cache" })` so the HTTP cache is revalidated. A same-origin HTTP 200 HTML response may update the exact runtime document-cache entry. Document-cache writes and authoritative deletes are serialized per request URL. HTTP 404/410 is authoritative and removes the exact stored document before returning the network response. Ordinary non-transient 4xx such as 403 never fall back to stale documentation. HTTP 5xx and network failures may use a stored document only when the client can prove an explicit `cached-unverified` indication; otherwise the original 5xx or explicit HTTP 503 path remains in force. A stored response whose response URL differs from the current request URL is rejected as a synthetic fallback so redirect/base-URL semantics are not silently changed.

For full browser navigation, cached fallback HTML carries its own fixed freshness notice. For instant navigation, `pwa.js` applies the persistent status element and acknowledges it through a `MessageChannel` before the Service Worker may expose cached HTML. This makes stale indication a safety condition: an old/unaware controlled client that cannot acknowledge the UI receives no unindicated cached document. A later verified document-like response clears the persistent indicator.

Do not precache the portal home or generated documentation pages in the static shell. Routine shell-asset content changes converge through HTTP revalidation. Increment `CACHE_NAME` when the shell cache strategy, namespace, or compatibility contract changes so activation can delete incompatible shell caches. Preserve `templates-portal-documents-v1` across compatible shell updates; change the document namespace only when its storage or representation contract becomes incompatible.

`tests/test_pwa_assets.py` owns the source-level PWA contract, including manifest shape, shell-asset coverage, shared SVG safety, registration wiring, generated metadata insertion and preview exclusion, duplicate/conflicting metadata rejection, document classification, runtime cache separation, response cloning, authoritative deletion, fail-closed stale indication, and cache-version transition. `scripts/check_pwa_freshness.py` owns the Chromium lifecycle contract: document HTTP-cache revalidation, runtime document-cache update and survival across a shell update, acknowledged stale fallback, later warning clearing, ordinary 4xx non-fallback, transient 5xx fallback, authoritative deletion, offline cached navigation, and explicit 503 for cache misses or clients that cannot establish the freshness UI. `scripts/check_pwa_capabilities.py` separately exercises the live `templates:get-freshness-capabilities` message contract. The Pages build separately verifies that the manifest, icon, service worker, registration script, manifest link, theme-color metadata, `/site-version.json`, and per-page revision metadata exist and satisfy their contracts in the generated artifact.

## Build and deployment policy

`.github/workflows/build-pages.yml` is build-only. It may run for pull requests targeting `site` or through `workflow_call`. It has `contents: read`, pins Python before executing repository Python code, resolves the locked publication revisions, checks out all publications, runs tests, prepares the temporary tree-page publication, assembles the portal, publishes explicitly declared synchronized translations and their temporary reader map, generates complete provider trees, generates Skill and Webapp copyable-template trees, generates bounded inline previews, strictly builds the site, generates the integrated glossary JSON and human viewer, normalizes canonical and PWA metadata, generates the bounded static repository browser, generates the immutable provider index-navigation graph and `/guided/` viewer, normalizes guided metadata, finalizes per-page canonical URLs and translation-reader metadata from the explicit translation publication map, applies build-time Glossary annotations to eligible final HTML, verifies the generated public-URL boundary and Pages entry points, records provenance and projects/verifies the public freshness identity, validates links, and uploads a Pages artifact. It contains no deployment job or Pages write authority.

`.github/workflows/mobile-visual-regression.yml` is a pull-request-only consumer of that build artifact for same-repository pull requests targeting `site`. It has only `contents: read` and `actions: read`, waits for the matching successful `build-pages.yml` run at the exact pull-request head SHA, downloads that run's `github-pages` artifact, installs the controller pinned by `requirements-visual.txt` plus its matching Playwright Chromium build, then runs `scripts/check_mobile_layout.py`, `scripts/check_pwa_freshness.py`, and `scripts/check_pwa_capabilities.py` against the already-built site. The layout checker measures 360×800, 390×844, and 412×915 viewports, rejects page-wide horizontal overflow and mobile-density regressions, verifies full repository revisions remain on one line inside their local table scroll container, and enforces the 48 px portal-action floor. The PWA lifecycle checker verifies document revalidation, runtime document-cache fallback/deletion, stale indication, static-shell convergence, and Service Worker update propagation in a real browser context; the capability checker verifies the live freshness-state vocabulary and associated URLs/cache namespace. The workflow uploads screenshots, `metrics.json`, `pwa-freshness.json`, and `pwa-capabilities.json` as short-lived review evidence. It does not build or deploy Pages and does not run repository code from fork pull requests.

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

`requirements.txt` pins Zensical and build-time syntax-highlighting dependencies, including Pygments. `requirements-visual.txt` separately pins the Playwright controller used only by the mobile visual regression workflow; its matching Chromium build is installed by Playwright rather than committed to the repository. Update either dependency set intentionally, run the relevant full build, mobile layout, PWA freshness lifecycle, and capability checks, and review generated navigation, glossary output, translation-reader routes and switchers, complete repository trees, both copyable-template trees, inline previews, the static repository browser, the guided navigation surface, canonical URLs, provenance/freshness identity, link-validation results, mobile geometry, PWA lifecycle evidence, and screenshots before merging.

## Local validation

Check out the four unrelated branches into separate directories at the commits recorded in `publication-sources.json`, then run:

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
python site/scripts/generate_index_navigation_locales.py \
  --graph build/index-navigation.json \
  --output build/index-navigation-locales.json \
  --translation-map build/translation-publication.json \
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
python site/scripts/generate_index_navigation_locale_viewer.py \
  --repository TakashiSasaki/templates \
  --graph build/index-navigation.json \
  --locale-overlays build/index-navigation-locales.json \
  --translation-map build/translation-publication.json \
  --site-root site-publication \
  --output-root build/site \
  --pair-map build/guided-locale-publication.json \
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
python site/scripts/finalize_guided_locales.py \
  --site-root build/site \
  --pair-map build/guided-locale-publication.json \
  --canonical-url https://templates.moukaeritai.work/
python site/scripts/finalize_glossary_annotations.py \
  --site-root build/site \
  --glossary build/site/glossary/index.json
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
python site/scripts/check_pwa_capabilities.py \
  --site-root build/site \
  --output build/mobile-visual/pwa-capabilities.json
```

The mobile layout command uses the Chromium build matched to the pinned Playwright controller and writes screenshots plus `metrics.json` under `build/mobile-visual`. The PWA freshness lifecycle command uses the same Chromium installation and writes `pwa-freshness.json` while validating HTTP-cache revalidation, runtime document-cache update/persistence, visible or acknowledged stale fallback, ordinary 4xx non-fallback, 5xx fallback, authoritative deletion, static-shell convergence, worker update propagation, and explicit 503 for cache misses/fail-closed clients. The separate capability command writes `pwa-capabilities.json` and validates the live freshness-state message contract. Use workflow-call revision overrides only for deliberate compatibility testing. Normal builds use the reviewed full-SHA lock file. Repository-tree links, preview URLs, repository-browser snapshots, guided-navigation graph/viewer output, glossary output and inline annotations, and translation reader routes always use the actual checked-out commits.
