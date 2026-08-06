# Templates documentation portal

This site is the single GitHub Pages entry point for the major branches of
`TakashiSasaki/templates`. It presents the documentation owned by the unrelated
`skill`, `policy`, and `webapp` branch histories as one reader-oriented portal.

The public origin is `https://templates.moukaeritai.work/`. The site is served
from the domain root; the former `/templates/` project path is not part of the
public information architecture.

The source branches remain independent and retain ownership of their canonical
documents. The `site` branch selects reviewed provider commits, validates the
combined publication, and owns the public information architecture and the only
GitHub Pages deployment route.

## Choose a publication

### Skill

Use the [Skill publication](skill/) for reusable skill contracts, runtime
decisions, interface routing, and guidance for CLI, MCP, and human Web callers.

### Policy

Use the [Policy publication](policy/) for application-neutral agent policy
adoption, bootstrap, managed operation, validation, release lifecycle, threat
modeling, and architecture decisions.

### Web application

Use the [Web application publication](webapp/) for Web application template
contracts, implementation and release evidence, validation, responsibility
boundaries, contract evolution, and migration guidance.

## Explore complete repository trees

Use the [repository tree overview](repository-trees/) to inspect every tracked
path in the exact `skill`, `policy`, and `webapp` revisions used by this build.
Directories are presented as collapsible trees. Cataloged documents link back to
their human-readable Pages locations, while all other files link to immutable
GitHub source views at the rendered full commit SHA.

The tree is an inventory, not a second publication mechanism. Listing a file
does not copy its contents into Pages or make an uncataloged document public.

## What is published

Each provider branch declares its public boundary in
`docs/publication-catalog.json`. The catalog is an explicit allowlist, not a
request to copy the branch or every file under `docs/`.

Only cataloged Markdown documents and explicitly cataloged non-Markdown assets
are assembled. Tests, workflows, helper scripts, working notes, generated files,
and future files are not published merely because they exist in a provider
branch. Machine-readable contracts and schemas are supporting material; the
navigation prioritizes explanatory Markdown intended for human readers.

The portal uses stable namespaced document identities such as
`policy:overview` and `webapp:implementation-evidence`. The `site` branch maps
those identities to reader-facing titles, hierarchy, ordering, and stable paths
under `/skill/`, `/policy/`, and `/webapp/`.

## Reproducible publication

Provider inputs are recorded as lowercase full 40-character commit SHAs in
`publication-sources.json`. A `site` commit therefore identifies exact provider
revisions rather than mutable branch tips.

Every uploaded Pages artifact also contains `/build-provenance.json`. It records
the built `site` commit and the exact `skill`, `policy`, and `webapp` commits.
This metadata identifies the inputs used for the publication; it is not a
cryptographic signature or artifact attestation.

## Change ownership

Canonical content changes are made and reviewed on the provider branch that owns
the document. A coordinated `site` pull request then updates the reviewed source
lock and, when necessary, the integrated navigation. Generated Markdown and HTML
remain build artifacts and are not committed to `site`.

The branch histories are not merged, rebased, or cherry-picked merely to publish
documentation. The site build checks out each provider independently at its
locked commit, assembles one temporary project, performs a strict static-site
build, validates generated links and fragments, records provenance, and uploads
the resulting Pages artifact.
