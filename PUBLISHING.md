# Integrated publication policy

This policy applies to the unrelated `site`, `skill`, `policy`, and `webapp`
branch histories in `TakashiSasaki/templates`.

## Objective

The `site` branch publishes one human-readable GitHub Pages portal that includes
reviewed documentation from the `skill`, `policy`, and `webapp` branches without
combining their Git histories or transferring ownership of their canonical
content.

The publication system must be explicit, reproducible, reviewable, and safe
against accidental branch-wide disclosure.

## Responsibilities

Provider branches (`skill`, `policy`, and `webapp`) own:

- canonical documentation and supporting public assets;
- `docs/publication-catalog.json`, which defines the provider's public boundary;
- stable document IDs and canonical source paths;
- whether a cataloged document or asset is required or optional;
- one required publication home document;
- provider-local validation of catalog and documentation changes.

The `site` branch owns:

- the global portal home and reader-oriented information architecture;
- cross-publication titles, hierarchy, ordering, and generated destinations;
- reviewed full-SHA source locks in `publication-sources.json`;
- integrated assembly and strict static-site generation;
- generated link, fragment, asset, canonical-URL, and provenance validation;
- the sole repository workflow authorized to deploy GitHub Pages.

A document is globally identified by the pair `publication:document`, for
example `policy:overview` or `webapp:implementation-evidence`.

## Public boundary

Publication catalogs are explicit allowlists. The assembler must not infer that
a file is public from its directory, extension, Git tracking status, or presence
in a provider branch.

The following rules apply:

1. Only Markdown entries in a provider publication catalog are rendered as
   documents.
2. Only non-Markdown assets declared by the applicable catalog schema are
   copied.
3. Tests, workflows, scripts, generated output, working notes, and newly added
   files remain unpublished unless deliberately cataloged.
4. Branch-wide copies and unrestricted glob-based publication are prohibited.
5. Machine-readable contracts and schemas may be published as supporting
   assets, but the navigation should lead readers through explanatory Markdown.
6. Catalog paths and asset traversal must reject parent traversal, unsafe path
   forms, `.git` components, and symbolic-link traversal.

Adding a file to a provider branch does not publish it. Adding or changing a
catalog entry is a public-interface change and requires review as such.

## Human-readable information architecture

The portal must provide a clear entry point for each major publication:

- `/templates/skill/` for reusable skill and interface contracts;
- `/templates/policy/` for application-neutral agent policy and operation;
- `/templates/webapp/` for Web application template contracts and evidence.

Navigation is organized by reader task and conceptual hierarchy rather than by
repository layout alone. Overview, adoption, operation, architecture, evidence,
release, ADR, and migration material should be grouped under descriptive titles.
Raw contracts, schemas, and other machine-readable files should remain
reachable from explanatory documents without dominating primary navigation.

Generated destinations are stable public paths. Renaming a source file does not
require a public URL change when the stable document ID and destination remain
unchanged. A destination change must be reviewed as a compatibility change.

## Reproducibility and provenance

Normal builds use lowercase full 40-character commit SHAs from
`publication-sources.json`. Mutable branch names, tags, and abbreviated SHAs are
not acceptable source locks.

The build artifact contains `build-provenance.json` with:

- the repository identifier;
- the exact `site` commit;
- the exact `skill`, `policy`, and `webapp` commits.

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
8. Require tests, strict site generation, entry-point checks, provenance
   generation, and generated-link validation to pass.
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

The GitHub `github-pages` environment is an external repository setting and is
not changed by a pull request. Its custom deployment branch policy must allow
exactly the `site` branch for this repository. A stale rule that allows `main`
instead of `site` causes the build and artifact upload to succeed while the
deployment job is rejected before runner steps begin.

The environment rule is a release gate. Before declaring publication complete,
verify that:

- `site` is the allowed deployment branch;
- obsolete `main` authorization has been removed;
- the `site` push workflow completes its build and deploy jobs successfully;
- `/templates/`, `/templates/policy/`, and `/templates/webapp/` are reachable;
- the deployed `build-provenance.json` matches the reviewed lock file.

Do not broaden the environment to all branches as a workaround. The workflow
conditions and environment policy should independently enforce the same `site`
-only deployment boundary.

## Completion criteria

A publication update is complete only when all of the following hold:

- each required catalog document appears exactly once in integrated navigation;
- unknown and uncataloged documents are not published;
- required provider entry points are generated;
- internal links, fragments, assets, and canonical URLs validate;
- provenance records exact full-SHA inputs;
- no provider branch can deploy Pages;
- a `site` push successfully deploys the reviewed artifact.
