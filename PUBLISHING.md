# Integrated publication policy

This policy applies to the unrelated `site`, `skill`, `policy`, and `webapp`
branch histories in `TakashiSasaki/templates`.

## Objective

The `site` branch publishes one human-readable GitHub Pages portal that includes
reviewed documentation from the `skill`, `policy`, and `webapp` branches without
combining their Git histories or transferring ownership of their canonical
content. The same Pages artifact may also expose a bounded source-oriented file
browser for the exact build inputs and a bounded index-guided navigation surface
that projects provider-owned `index.md` structure under the rules below.

The publication system must be explicit, reproducible, reviewable, and safe
against accidental branch-wide disclosure.

## Responsibilities

Provider branches (`skill`, `policy`, and `webapp`) own:

- canonical documentation and supporting public assets;
- `docs/publication-catalog.json`, which defines the provider's public boundary;
- stable document IDs and canonical source paths;
- whether a cataloged document or asset is required or optional;
- one required publication home document;
- provider-owned `index.md` files and the semantic navigation paths expressed by
  their headings, link order, link labels, link destinations, and short
  descriptions;
- provider-local validation of catalog and documentation changes.

The `site` branch owns:

- the global portal home and reader-oriented information architecture;
- cross-publication titles, hierarchy, ordering, and generated destinations for
  cataloged documentation;
- reviewed full-SHA source locks in `publication-sources.json`;
- integrated assembly and strict static-site generation;
- generated repository inventories and bounded inline file previews;
- the bounded static file-browser snapshots for `site`, `skill`, `policy`, and
  `webapp` build inputs;
- the deterministic index-navigation graph and human-readable projection of the
  exact reviewed `skill`, `policy`, and `webapp` provider inputs without
  redefining their provider-owned navigation semantics;
- generated link, fragment, asset, canonical-URL, and provenance validation;
- the sole repository workflow authorized to deploy GitHub Pages.

A document is globally identified by the pair `publication:document`, for
example `policy:overview` or `webapp:implementation-evidence`.

## Public boundary

Publication catalogs are explicit allowlists for rendered documentation and
supporting publication assets. The assembler must not infer that a file is a
published document from its directory, extension, Git tracking status, or
presence in a provider branch.

The following rules apply:

1. Only Markdown entries in a provider publication catalog are rendered as
   documentation pages.
2. Only non-Markdown assets declared by the applicable catalog schema are copied
   as provider publication assets.
3. Tests, workflows, scripts, generated output, working notes, and newly added
   files do not become cataloged documentation merely because they are tracked.
4. Branch-wide copies and unrestricted glob-based publication are prohibited for
   cataloged documentation and provider assets. The separate repository inventory,
   inline-preview, static file-browser, and index-guided navigation surfaces may
   expose only the bounded Git-object representations or navigation metadata
   explicitly permitted below.
5. Machine-readable contracts and schemas may be published as supporting
   assets, but the navigation should lead readers through explanatory Markdown.
6. Catalog paths and asset traversal must reject parent traversal, unsafe path
   forms, `.git` components, and symbolic-link traversal.
7. Repository inventory previews, static file-browser pages, and index-guided
   navigation pages are separate bounded rendering surfaces and must satisfy
   every applicable constraint in the following sections.

Adding a file to a provider branch does not publish it as a cataloged document or
provider asset. Adding or changing a catalog entry is a public-interface change
and requires review as such. A tracked regular file can nevertheless become
visible in the separate file-browser snapshot when it satisfies the bounded
browser rules below; this does not make it a cataloged document or asset.
Likewise, a path referenced by a provider-owned `index.md` may be represented as
navigation metadata or linked to the file browser without becoming a cataloged
documentation page.

## Repository inventory

The integrated site may publish a generated directory-tree inventory for the
reviewed `skill`, `policy`, and `webapp` checkouts. This inventory is metadata
about the Git tree and is separate from the publication catalog boundary.

A path appearing in the inventory does not make the file part of the Pages
publication as a cataloged document or provider asset. The tree generator must
not copy unlisted file contents; the separate inline-preview and file-browser
generators may emit only the bounded escaped representations defined below.

The inventory may provide:

- a human-readable, collapsible view of every tracked path;
- immutable GitHub links using the full checked-out commit SHA;
- Pages links for Markdown files that are already cataloged and navigable;
- entry-type labels for symlinks and gitlinks;
- a sandboxed inline frame for eligible regular text files.

The inventory must be generated from Git tree metadata rather than an
unrestricted filesystem walk. Untracked files and `.git` administration data
must not appear. The generators must not follow symlinks or gitlinks. Mutable
branch names must not be used in generated file links.

### Inline previews

Inline preview generation has a narrower mandatory boundary:

- content is read from the exact Git blob objects named by `git ls-tree`, never
  from mutable working-tree paths;
- only regular files that decode as strict UTF-8 text are eligible;
- NUL bytes, invalid UTF-8, disallowed control characters, binary files,
  symlinks, and gitlinks are excluded;
- each preview source is limited to 256 KiB;
- candidate and aggregate preview byte budgets are enforced before publication;
- repository markup is HTML-escaped and shown as text rather than rendered as
  active repository HTML;
- generated preview pages declare a restrictive content security policy and are
  loaded through an iframe with the `sandbox` attribute and no permissions;
- preview URLs include the provider publication and exact checked-out revision;
- the immutable GitHub source link remains available as the fallback and source
  of record.

Repository-tree pages and preview HTML are generated into the temporary assembled
project before the strict static-site build. Temporary catalog and navigation
declarations must be validated by the same assembler that validates canonical
documentation. Generated Markdown, preview HTML, and final site HTML remain build
artifacts and must not be committed.

### Static file browser

The static file browser is a source-oriented rendering surface at `/files/`. It
covers the exact checkout used for the `site` implementation and the exact
`skill`, `policy`, and `webapp` provider checkouts used by the same build. The
human branch labels are navigation labels only; each browser page must display
and render the corresponding full 40-character checked-out commit SHA.

The browser must satisfy all of the following constraints:

- directory and entry discovery is derived from `git ls-tree` metadata;
- regular-file content is read from the exact Git blob object IDs named by the
  tree, not from mutable working-tree paths;
- symlinks and gitlinks are listed as metadata but are never followed;
- only strict UTF-8 regular files without NUL bytes, bidirectional controls, or
  other disallowed control characters are rendered as text;
- each rendered text file is limited to 1 MiB, and candidate text content is
  limited to 64 MiB per branch before publication;
- every regular tracked file receives a local browser target; files outside the
  text boundary receive a metadata/fallback page rather than active file content;
- syntax highlighting is generated at build time with the pinned Pygments
  dependency using the file name to select an appropriate lexer, with plain-text
  fallback when no lexer matches;
- source text is HTML-escaped before publication, and generated file pages use a
  restrictive content security policy;
- desktop-width views keep the tree and selected file visible in a split browser
  layout; at narrow viewports a same-origin progressive-enhancement controller
  may switch between full-height Files and Content panes while the no-JavaScript
  fallback remains the bounded split layout;
- the hidden narrow-viewport pane is non-interactive, an explicit Files control
  restores the unchanged tree state, and the selected file remains isolated in
  an iframe with the `sandbox` attribute and no permissions;
- line numbers and line wrapping can be toggled locally without executing
  repository-supplied code;
- ordinary text viewing has no runtime GitHub API, raw-content, or CDN dependency;
- an immutable full-SHA GitHub source link may remain available as an explicit
  fallback and source-of-record link.

The browser is generated only after the strict Zensical build has created the
final site directory, so `zensical build --clean` cannot delete it. It must be
generated before final site-link validation and before the Pages artifact is
uploaded. Browser HTML is a build artifact and must not be committed.

### Index-guided navigation

The index-guided navigation surface at `/guided/` exists so that a human reader
can follow and evaluate the same provider-owned progressive-disclosure path that
an AI agent can use before falling back to search or unrestricted source
browsing. It is a projection of navigation metadata, not a second catalog and
not a replacement for the Site-authored reader navigation.

The guided-navigation implementation must satisfy all of the following rules:

- the only top-level providers are `skill`, `policy`, and `webapp`;
- each provider traversal starts at that exact checkout's `docs/index.md`;
- `index.md` content is read from exact Git blob object IDs named by the checked
  out revision rather than mutable working-tree content;
- only `index.md` nodes reached from the explicit provider root participate in
  guided navigation; size and content validation is performed when each node is
  reached, so unrelated index-shaped files elsewhere in the repository do not
  become guided inputs merely because of their name;
- provider `index.md` files are interpreted only through the conservative
  reserved-index shape accepted by the navigation parser: headings and Markdown
  link entries with short descriptions; arbitrary provider Markdown or raw HTML
  is not rendered as guided-navigation content;
- provider-controlled titles, section names, labels, and descriptions are HTML
  escaped before they appear in generated HTML;
- strict UTF-8, NUL/control-character, repository-root escape, unsafe URL scheme,
  malformed-host-or-port, broken-link, symlink, and gitlink boundaries fail
  closed;
- a directory link is followed recursively only when it resolves to an
  `index.md` regular file in the same provider revision;
- cycles, multiple navigation parents, and maximum index depth are recorded as
  diagnostics so the information architecture can be evaluated without
  inventing an unvalidated policy limit;
- the schema-versioned machine-readable graph is published at
  `/guided/graph.json` and records the exact provider full SHA for every provider;
- the human viewer consumes that graph rather than reparsing provider Markdown,
  so graph semantics and human presentation cannot drift independently;
- an index-to-index link opens the generated guided index page; a link to an
  already cataloged document opens the Site's existing stable documentation
  destination; an uncataloged regular tracked file without a fragment opens the
  corresponding immutable `/files/` viewer; an uncataloged regular tracked file
  with any fragment opens the exact full-SHA immutable GitHub source so a
  semantic or line fragment is not silently attached to a local fallback page
  that may not expose a matching anchor; a directory without a followed index
  opens the corresponding provider source-browser entry point; and an HTTP(S)
  external link remains external;
- each guided page displays its provider, exact full SHA, source `index.md` path,
  and immutable GitHub source link;
- the graph revision for a provider must equal the checked-out provider revision
  used for catalog assembly, repository trees, previews, and `/files/`; revision
  disagreement fails before guided output is accepted;
- generated guided HTML uses a restrictive content security policy, permits the
  same-origin PWA manifest injected by Site metadata normalization, and does not
  execute repository-supplied code;
- ordinary guided browsing has no runtime GitHub API, raw-content, or CDN
  dependency except when a user explicitly follows an immutable full-SHA GitHub
  source link used as the source of record or semantic-fragment fallback.

The guided surface is generated after the static file browser because
uncataloged guided targets may resolve to file-browser pages. Both surfaces must
be generated before final site-link validation and before the Pages artifact is
uploaded. Guided HTML and graph JSON are build artifacts and must not be
committed.

## Human-readable information architecture

The portal must provide a clear entry point for each major publication:

- `/skill/` for reusable skill and interface contracts;
- `/policy/` for application-neutral agent policy and operation;
- `/webapp/` for Web application template contracts and evidence.

It must also provide stable generated inventory entry points:

- `/repository-trees/`;
- `/repository-trees/skill/`;
- `/repository-trees/policy/`;
- `/repository-trees/webapp/`.

The source-oriented browser has stable entry points:

- `/files/` for browser selection;
- `/files/site/` for the deployed site implementation snapshot;
- `/files/skill/`, `/files/policy/`, and `/files/webapp/` for the reviewed
  provider snapshots.

The index-guided surface has stable entry points:

- `/guided/` for choosing a provider-owned navigation path;
- `/guided/skill/`, `/guided/policy/`, and `/guided/webapp/` for the reviewed
  provider navigation roots;
- `/guided/graph.json` for the schema-versioned machine-readable representation
  used by the human viewer.

The Site-authored navigation and provider-owned guided navigation are
complementary. Site navigation is organized by reader task and conceptual
hierarchy, while the guided surface intentionally preserves provider-owned index
order, grouping, labels, and descriptions. The Site must not silently derive or
replace its primary navigation from arbitrary Markdown parsing merely because a
guided graph exists.

Overview, adoption, operation, architecture, evidence, release, ADR, and
migration material should be grouped under descriptive titles in Site-authored
navigation. Raw contracts, schemas, and other machine-readable files should
remain reachable from explanatory documents without dominating primary
navigation.

Generated destinations are stable public paths. Renaming a source file does not
require a public URL change when the stable document ID and destination remain
unchanged. A destination change must be reviewed as a compatibility change. File
browser content URLs are implementation details keyed by immutable provider
revision and source-path identity. Nested guided-index URLs identify the current
reviewed provider/path projection; the exact provider revision is recorded in
the guided page and graph rather than encoded in that nested URL. Only the branch
browser and guided provider entry points above are stable public paths.

## Reproducibility and provenance

Normal builds use lowercase full 40-character commit SHAs from
`publication-sources.json`. Mutable branch names, tags, and abbreviated SHAs are
not acceptable source locks.

The build artifact contains `build-provenance.json` with:

- the repository identifier;
- the exact `site` commit;
- the exact `skill`, `policy`, and `webapp` commits.

Repository-tree links, preview URLs, file-browser pages, the index-navigation
graph, and guided-navigation pages must use the corresponding checked-out
commit. Workflow-call revision overrides therefore produce inventory, preview,
browser, graph, and guided output for the overridden commit rather than the
normal lock value.

The provenance file identifies deterministic source inputs. It is not a digital
signature, software bill of materials, or artifact attestation.

Workflow-call revision overrides are reserved for deliberate compatibility
checks. They do not replace the reviewed lock file for normal publication.

## Change workflow

A provider publication change uses this sequence:

1. Change canonical documentation and, when applicable, the publication catalog
   on the owning provider branch.
2. Validate the provider publication locally and in CI.
3. Merge the provider pull request and record the actual merge commit full SHA.
4. Create a coordinated branch from the current `site` head.
5. Update `publication-sources.json` to the reviewed provider merge commit.
6. Update `site-manifest.json` when documents, reader-facing titles, hierarchy,
   order, or generated destinations change.
7. Build the integrated site against the exact locked commits.
8. Require tests, repository-tree generation, inline-preview generation, strict
   site generation, static file-browser generation, index-navigation graph and
   guided-viewer generation, entry-point checks, provenance generation, and
   generated-link validation to pass.
9. Merge the `site` pull request. A push to `site` is the only deployment event.

Provider and `site` changes remain separate pull requests because they have
different ownership and review responsibilities. A period in which a provider
merge is not yet represented by the `site` lock is valid and intentional.

## Deployment authority

`.github/workflows/build-pages.yml` is build-only. It may create and upload a
Pages artifact, but it has no Pages write or OpenID Connect token authority and
must not call `actions/deploy-pages`.

`.github/workflows/deploy-pages.yml` is the sole deployment workflow. It accepts
only a push to `refs/heads/site` in `TakashiSasaki/templates` and grants Pages
write and identity-token permissions only to the deployment job. Default-branch
status is not an authorization input.

`https://templates.moukaeritai.work/` is the configured Pages base URL. It is a
root-hosted site: the configured base path must be empty, and generated links
must not retain the former `/templates/` project path. The deployment workflow
compares the repository-owned expected URL with the `actions/configure-pages`
base URL, host, and base-path outputs and fails closed before deployment when
GitHub's external Pages settings drift.

The GitHub `github-pages` environment is an external repository setting and is
not changed by a pull request. Its custom deployment branch policy must allow
exactly the `site` branch for this repository. A stale rule that allows `main`
instead of `site` causes the build and artifact upload to succeed while the
deployment job is rejected before runner steps begin.

The custom domain and TLS controls are also external repository and DNS state.
Before publication is complete, the Pages custom domain must be
`templates.moukaeritai.work`, the certificate must be approved, and HTTPS
enforcement is enabled. A custom Actions deployment does not rely on a committed
`CNAME` file; GitHub's Pages setting and DNS are the authoritative domain state.

The environment rule is a release gate. Before declaring publication complete,
verify that:

- `site` is the allowed deployment branch;
- obsolete `main` authorization has been removed;
- the `site` push workflow completes its build and deploy jobs successfully;
- `/`, `/skill/`, `/policy/`, and `/webapp/` are reachable;
- all four `/repository-trees/` entry points are reachable;
- `/files/` and all four branch browser entry points are reachable;
- `/guided/` and `/guided/skill/`, `/guided/policy/`, and `/guided/webapp/` are
  reachable;
- `/guided/graph.json` records the same reviewed provider full SHAs as the
  provider checkouts and deployed provenance;
- preview links load the corresponding sandboxed frame without replacing source
  links;
- file-browser text pages show line-number and wrapping controls and do not need
  a runtime GitHub API or CDN request to render their text;
- guided pages preserve provider-owned link labels and descriptions without
  executing provider-supplied markup or code;
- the deployed `/build-provenance.json` matches the reviewed lock file;
- HTTP requests redirect to HTTPS and the deployed response uses the custom
  domain.

Do not broaden the environment to all branches as a workaround. The workflow
conditions and environment policy should independently enforce the same
`site`-only deployment boundary.

## Completion criteria

A publication update is complete only when all of the following hold:

- each required catalog document appears exactly once in integrated navigation;
- unknown and uncataloged files are not rendered as cataloged documentation;
- required provider entry points are generated;
- repository inventories cover all tracked entries without following symlinks
  or gitlinks;
- repository inventory links use the exact checked-out provider commits;
- inline previews are generated only from eligible bounded Git blobs and render
  escaped text in sandboxed frames;
- binary, oversized, symlink, gitlink, and invalid-text entries retain GitHub-only
  fallback behavior in the inline-preview surface;
- the static file browser covers `site`, `skill`, `policy`, and `webapp` at their
  exact checked-out full SHAs and reads eligible content only from named Git blobs;
- browser syntax highlighting is build-time only, text is escaped, line-number
  and wrapping toggles work without repository code execution, and non-text or
  oversized files receive fallback pages;
- each provider guided root is generated from its exact checked-out
  `docs/index.md`, and every reachable index node represented in
  `/guided/graph.json` has a corresponding human viewer page;
- the guided graph and viewer use the same full-SHA provider snapshots as
  publication assembly and `/files/`, preserve provider-owned navigation
  metadata, escape provider text, and fail closed on invalid navigation targets;
- graph diagnostics record cycles, multiple-parent indexes, and maximum depth
  without converting those observations into unsupported policy limits;
- internal links, fragments, assets, preview targets, browser targets, guided
  targets, and canonical URLs validate;
- provenance records exact full-SHA inputs;
- no provider branch can deploy Pages;
- a `site` push successfully deploys the reviewed artifact.