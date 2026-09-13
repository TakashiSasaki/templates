# Publication staging contract

## Purpose

`publication-staging.json` allows Site to describe a future reader mapping before the corresponding provider document is added to the provider publication catalog.

The staging contract exists only to validate a coordinated cross-authority document-set change without creating an invalid active publication state. It does not publish a document, change `publication-sources.json`, or authorize deployment.

The active publication authority remains the exact pair of:

- `site-manifest.json` and `reader-navigation-locales.json` from the selected Site revision; and
- the exact provider catalogs from the selected Composition and Policy revisions.

A staged mapping becomes effective only inside a non-deploying compatibility build that explicitly names its staging ID. A compatibility build may select an explicit ordered comma-separated set of IDs to stage one coordinated document set atomically; it never stages unselected entries.

## Why staging is required

The Site assembler intentionally enforces exact provider-catalog coverage:

- a Site mapping to an uncataloged provider document fails closed; and
- a cataloged provider document with no Site mapping also fails closed.

For a new provider document, independently merging either side first would therefore create a deliberately rejected intermediate pair. The staging contract resolves sequencing without relaxing either check.

## Contract shape

`publication-staging.json` is schema version 1 and contains a non-empty `mappings` array. Every mapping records:

- a stable staging `id` used only to select the compatibility overlay;
- the owning external `publication`, exactly `composition` or `policy`;
- the future provider `document` ID;
- the Site-owned reader `title` and generated `destination`;
- an exact active sibling page identified by `insert_after.publication` and `insert_after.document`; and
- Site-owned navigation `localizations` when the staged canonical title is not already represented by the active locale overlay.

The staging record does not contain provider prose, provider glossary definitions, provider translation content, or a provider revision. Provider content always comes from the exact provider checkout supplied to the compatibility build.

## Materialization

`scripts/materialize_publication_staging.py` applies one explicitly selected mapping, or an explicit ordered set selected with `--staging-ids`, to a newly created private qualification snapshot. It never replaces `site-manifest.json` or `reader-navigation-locales.json` in the input Site checkout.

Materialization is fail-closed. It requires:

- the active Site manifest and navigation locale overlay to validate before staging;
- unique selected staging IDs;
- a target provider document that is not already active;
- a destination that is not already active;
- exactly one active insertion anchor per mapping;
- safe Markdown destination syntax;
- exact localization coverage for every active Site reader locale when the title is new;
- the selected mappings to have unique publication/document keys, destinations, titles, and locale label IDs; and
- the fully materialized combined manifest and locale overlay in the private snapshot to pass the ordinary canonical validators.

The materializer copies the reviewed Site input into a private sibling directory, writes the staged manifest and locale overlay only inside that directory, validates that snapshot, then verifies that the source manifest and locale bytes still match the inputs from which the snapshot was derived. If the source mapping changes while the snapshot is being created, materialization fails and removes only the private snapshot. No rollback writes are ever made to the source checkout, so a concurrent source writer cannot be overwritten by staging cleanup.

The successful CLI prints the private qualification root path. The caller must use that root for the staged qualification path. The source checkout remains the pristine reviewed Site revision and remains suitable for repository-contract tests and revision/provenance operations.

The materializer does not edit the provider catalog. After materialization, the ordinary strict assembler still requires exact catalog coverage against the exact provider candidate. A candidate provider that does not contain the staged document therefore fails in the normal way.

## Workflow boundary

`.github/workflows/build-pages.yml` exposes optional `publication_staging_id` and `publication_staging_ids` reusable-workflow inputs. Their defaults are empty.

When both inputs are empty:

- no staging materialization step runs;
- pull-request Site builds use the committed active manifest; and
- the deployment workflow uses the committed active manifest.

When an external provider compatibility workflow explicitly supplies a staging selection, the final staging-qualified workflow must:

1. check out the exact Site revision;
2. resolve and check out the exact provider revisions;
3. create and validate a private qualification snapshot for the explicit staging selection;
4. pass that returned snapshot root to every provider-dependent Site integration, publication-preparation, translation-chrome, and assembly step that is intended to qualify the staged combination; and
5. keep repository-contract fixtures and the reviewed Site checkout pristine.

The staging path is build-only. It must not be wired into `deploy-pages.yml`.

The Site staging stack may introduce the materializer and the workflow consumption boundary in separate dependent PRs. The stack tip is the qualification contract: until the consumer step passes the returned snapshot root downstream, the staging prerequisite is not yet sufficient for provider landing qualification.

## Coordinated document-set cutover

Use the following sequence for a new provider document when neither authority can merge its active change first:

1. **Site staging PR** — add the staged Site mapping and materialization protocol while leaving the active Site manifest unchanged. Merge only after normal Site exact-head acceptance.
2. **Provider publication PR** — add the provider document to `docs/publication-catalog.json`. Pin the provider compatibility workflow to the reviewed Site staging revision, pass the exact provider candidate revision, and explicitly select the staging ID. Merge only when the full materialized Site build passes.
3. **Site promotion PR** — advance the provider source lock to the merged provider commit and promote the same staged Site mapping into the active manifest/localization data. Validate the ordinary, non-staged Site build against the exact provider lock before merge.

The Site promotion must not use staging as a permanent runtime mode. Once active publication is coherent, normal builds must succeed without a publication staging input.

A later maintenance change may remove an obsolete staging record after no pinned provider compatibility workflow requires that historical Site staging revision. Removing or retaining an unused record has no effect on active publication because staging is opt-in.

## Authority boundaries

Site staging owns only integration metadata: reader title, grouping/order anchor, destination, and Site chrome localization.

Composition and Policy continue to own their canonical documents, publication catalog entries, glossary definitions, translation files, and translation synchronization metadata. Site must not create a translated provider document merely because it localizes the navigation label.

Exact provider commit SHAs remain the only publication inputs. A mutable provider branch name is not a staging authority.
