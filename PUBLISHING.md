# Site publication and deployment

## Input authority

Modeling, Composition, and Policy remain independent providers. Integration
selects their exact provider tuple and owns publication mappings, staging,
translation availability, glossary, guided graphs and exact provenance. Site
selects only an exact reviewed Integration release through
`integration-source.json`.

The Integration selection therefore covers Composition and Policy provider
revisions explicitly; it does not grant Site direct access to either provider.

The lock binds the Integration commit, Bundle schema, identity and content digest.
There is no active `publication-sources.json` in Site. Provider candidate work
and Integration releases stop before Site PWA qualification or deployment unless
the downstream gates and automation mode explicitly authorize the next boundary.

## Immutable acquisition and rendering

The canonical `site-producer.yml` locates the selected qualified Integration artifact.
The existing transport verifies run/head, workflow attempt, artifact creation
window, archive digest, safe extraction, Bundle identity and internal provenance.
Absent or expired artifact evidence permits regeneration by the exact pinned
Integration workflow. Corrupt or misbound evidence fails closed.

`render_publication_bundle.py` receives the Bundle and Site source only. It renders
provider documents, read models and translations already qualified upstream.
It does not parse provider catalogs, translation manifests or Git objects.
Site's own content and translations remain Site-owned.
The selected provider models still supply bounded build-time views for the
transitional Site source presentation; that presentation is removed by the
following browser-retirement change.

`build-provenance.json` records the exact Site revision and adopted Bundle identity,
Integration revision and provider provenance. `publication-bundle.json` exposes
the selected immutable contract. Execution times do not change Bundle identity.

## Qualification and explicit release

A Site-only fix retains the Integration lock. Explicit adoption changes the lock
and qualifies the new immutable input. Neither operation follows a moving branch.

`build-pages.yml` performs consumer contracts, rendering, generated links, audience,
search, glossary, translation warnings, accessibility, mobile,
PWA and Service Worker acceptance against one exact generated Pages artifact.
Focused construction follows the existing CI classifier; the final frontier uses
`ci/full-qualification` and requires all actual acceptance suites to succeed.
Review findings must be dispositioned and exact-head acceptance must remain valid.

The publication controller has three explicit modes: `shadow` (the initial mode,
read-only reports), `adoption-only` (an authorized Integration/Site lock PR, no
Pages write), and `auto-publish` (the same gates followed by Pages deployment).
Compatibility is never authorization. Every mode requires exact input identities,
trusted policy/controller identity, positive qualification results, freshness and
an allowlisted expected patch. The controller stops on unknown, invalid,
unsupported, stale, failed, or unauthorized results.

The initial repository configuration is `shadow`; it does not mutate locks or
publish. After review and landing, one explicit activation may select the next
mode after the minimal-permission GitHub App token, branch protection, and
`github-pages` environment restrictions are verified. The activation procedure
is not self-applied by this implementation PR.

In `auto-publish`, the Pages path captures the deployment timestamp, performs
the complete qualification DAG against the final Site SHA, and deploys the exact
artifact produced by that run. The browser consumers and deployment job do not
regenerate or rewrite it. Only the deployment job has `pages: write` and
`id-token: write`; a kill switch stops new adoption/deployment and keeps the
last successful publication. Rollback selects a previously known-good immutable
lock and artifact through a separate guarded procedure.

## Reader routes

The Bundle supplies the public destination model. Current entry points include
`/composition/`, `/skill/`, `/web/`, `/website/`, `/webapp/`, `/capabilities/`,
`/lifecycle/`, `/policy/`, `/guided/` and `/glossary/`. Provider source browsing is
provided by immutable GitHub blob/tree links at the exact recorded revisions.
The former Skill/Webapp copyable-template trees are retired.

Current and stale provider translations are included exactly as Integration declares.
Stale pages display a static accessible warning and current English link, including
when cached offline. Missing translations do not create routes. Translation freshness
and deployed-document/cache freshness are separate dimensions.

## Publication and source-link safety

Integration's Publication catalogs are explicit allowlists. Branch-wide copies and
unrestricted glob-based publication are prohibited. Adding a file to a provider branch does not publish it.
Generated destinations are stable public paths in the Bundle contract.
The Site, Composition, and Policy source browsers display bounded build-time views.
Symlinks and gitlinks are never followed. Source content is escaped and sandboxed,
not executed as application HTML. The Bundle bounds provider content before Site
receives it. Site source/provenance links outside those browser views identify
exact full commit revisions.

## External deployment gate

The `github-pages` environment custom deployment branch policy must allow exactly the `site` branch.
The obsolete `main` authorization has been removed. Do not broaden the environment to all branches.
`https://templates.moukaeritai.work/` is the configured Pages base URL and HTTPS enforcement is enabled.
These settings were verified during the final architecture audit; recheck before release.
