# Portal overview

<div class="portal-landing">

<section class="portal-hero" aria-labelledby="portal-overview-title">
  <div class="portal-hero__copy">
    <p class="portal-kicker">Portal overview</p>
    <h1 id="portal-overview-title">Independent at source.<br><span>Integrated for readers.</span></h1>
    <p class="portal-hero__lead">
      Understand how the Skill, Policy, and Web application publications remain
      independently owned while appearing through one reproducible documentation portal.
    </p>
    <div class="portal-actions">
      <a class="portal-button portal-button--primary" href="../">Return to the visual entry page</a>
      <a class="portal-button portal-button--secondary" href="../guided/">Browse by index.md</a>
      <a class="portal-button portal-button--secondary" href="../repository-trees/">Inspect repository trees</a>
    </div>
    <div class="portal-signals" aria-label="Publication properties">
      <span>Independent histories</span>
      <span>Explicit allowlists</span>
      <span>Full-SHA inputs</span>
      <span>Validated output</span>
    </div>
  </div>
  <div class="portal-hero__visual">
    <img src="../images/landing-architecture.svg" alt="Skill, policy, and Web application templates connected through a validated documentation portal">
  </div>
</section>

<section class="portal-section" id="choose-a-template" aria-labelledby="choose-a-template-title">
  <div class="portal-section__heading">
    <p class="portal-kicker">Choose a publication</p>
    <h2 id="choose-a-template-title">Three responsibilities, one engineering system</h2>
    <p>Start from the artifact you need to build. Each publication owns a distinct responsibility boundary.</p>
  </div>

  <div class="portal-card-grid">
    <a class="portal-card portal-card--skill" href="../skill/">
      <span class="portal-card__icon"><img src="../images/icon-skill.svg" alt=""></span>
      <span class="portal-card__label">Skill</span>
      <strong>Build a reusable capability</strong>
      <span>Contracts, runtime decisions, interface routing, and guidance for CLI, MCP, and human Web callers.</span>
      <span class="portal-card__action">Explore Skill <span aria-hidden="true">→</span></span>
    </a>

    <a class="portal-card portal-card--policy" href="../policy/">
      <span class="portal-card__icon"><img src="../images/icon-policy.svg" alt=""></span>
      <span class="portal-card__label">Policy</span>
      <strong>Define how agents operate</strong>
      <span>Application-neutral adoption, bootstrap, managed operation, validation, lifecycle, and threat modeling.</span>
      <span class="portal-card__action">Explore Policy <span aria-hidden="true">→</span></span>
    </a>

    <a class="portal-card portal-card--webapp" href="../webapp/">
      <span class="portal-card__icon"><img src="../images/icon-webapp.svg" alt=""></span>
      <span class="portal-card__label">Web application</span>
      <strong>Deliver a verifiable product</strong>
      <span>Application contracts, implementation and release evidence, validation, responsibility boundaries, and migrations.</span>
      <span class="portal-card__action">Explore Web application <span aria-hidden="true">→</span></span>
    </a>
  </div>
</section>

<section class="portal-section portal-publication" aria-labelledby="publication-model-title">
  <div class="portal-section__heading">
    <p class="portal-kicker">Publication model</p>
    <h2 id="publication-model-title">Reviewed inputs become one reader-oriented portal</h2>
    <p>The <code>site</code> branch selects reviewed provider commits without merging their unrelated histories.</p>
  </div>
  <div class="portal-publication__layout">
    <img class="portal-publication__diagram" src="../images/publication-pipeline.svg" alt="Skill, policy, and Web application branches pass through catalogs, full-SHA locks, assembly, and validation before GitHub Pages publication">
    <div class="portal-principles">
      <article>
        <span>01</span>
        <div><h3>Explicit boundary</h3><p>Each provider catalog is an explicit allowlist. Uncataloged files do not become public by proximity.</p></div>
      </article>
      <article>
        <span>02</span>
        <div><h3>Immutable inputs</h3><p>Provider revisions are recorded as full commit SHAs rather than mutable branch tips.</p></div>
      </article>
      <article>
        <span>03</span>
        <div><h3>Validated output</h3><p>The integrated build checks navigation, links, fragments, repository trees, and provenance.</p></div>
      </article>
    </div>
  </div>
</section>

<section class="portal-tree-callout" aria-labelledby="repository-trees-title">
  <div>
    <p class="portal-kicker">Exact build inputs</p>
    <h2 id="repository-trees-title">Inspect the complete repository trees</h2>
    <p>Browse every tracked path at the exact <code>skill</code>, <code>policy</code>, and <code>webapp</code> revisions used by this publication.</p>
    <a class="portal-button portal-button--primary" href="../repository-trees/">Open repository trees</a>
  </div>
  <div class="portal-tree-callout__tree" aria-hidden="true">
    <span>templates/</span>
    <span>├── skill/</span>
    <span>├── policy/</span>
    <span>└── webapp/</span>
  </div>
</section>

</div>

## About this portal

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

## What is published

Each provider branch declares its public boundary in
`docs/publication-catalog.json`. Publication catalogs are explicit allowlists,
not requests to copy the branch or every file under `docs/`.

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
