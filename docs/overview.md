# Portal overview

<div class="portal-landing">

<section class="portal-hero" aria-labelledby="portal-overview-title">
  <div class="portal-hero__copy">
    <p class="portal-kicker">Portal overview</p>
    <h1 id="portal-overview-title">Separated by authority.<br><span>Integrated for readers.</span></h1>
    <p class="portal-hero__lead">
      Skill and Web application semantics now share one Composition source without
      becoming the same artifact. Reusable application capabilities and lifecycle
      contracts have their own component authorities. Policy remains independent,
      while Site assembles the reviewed provider revisions into one portal.
    </p>
    <div class="portal-actions">
      <a class="portal-button portal-button--primary" href="../">Return to the visual entry page</a>
      <a class="portal-button portal-button--secondary" href="../composition/">Composition architecture</a>
      <a class="portal-button portal-button--secondary" href="../guided/">Browse by index.md</a>
      <a class="portal-button portal-button--secondary" href="../repository-trees/">Inspect repository trees</a>
    </div>
    <div class="portal-signals" aria-label="Publication properties">
      <span>Explicit authorities</span>
      <span>Explicit allowlists</span>
      <span>Full-SHA inputs</span>
      <span>Validated output</span>
    </div>
  </div>
  <div class="portal-hero__visual">
    <img src="../images/landing-architecture.svg" alt="Agent Skill, policy, and Web application documentation connected through a validated portal">
  </div>
</section>

<section class="portal-section" id="choose-an-entry-point" aria-labelledby="choose-an-entry-point-title">
  <div class="portal-section__heading">
    <p class="portal-kicker">Choose an entry point</p>
    <h2 id="choose-an-entry-point-title">Artifact semantics are separate from reusable capabilities</h2>
    <p>Start from the artifact or operating concern you need. Composition describes how compatible authorities are materialized together; it does not collapse their semantics.</p>
  </div>

  <div class="portal-card-grid">
    <a class="portal-card portal-card--skill" href="../skill/">
      <span class="portal-card__icon"><img src="../images/icon-skill.svg" alt=""></span>
      <span class="portal-card__label">Agent Skill</span>
      <strong>Define an agent-triggered workflow</strong>
      <span>Trigger, workflow, references, assets, helper scripts, agent routing, outputs, validation, and safety.</span>
      <span class="portal-card__action">Explore Agent Skill <span aria-hidden="true">→</span></span>
    </a>

    <a class="portal-card portal-card--policy" href="../policy/">
      <span class="portal-card__icon"><img src="../images/icon-policy.svg" alt=""></span>
      <span class="portal-card__label">Policy</span>
      <strong>Define how coding agents operate</strong>
      <span>Shared operating policy plus the agent-policy toolchain for contexts, validation, rendering, adoption, lifecycle, and release.</span>
      <span class="portal-card__action">Explore Policy <span aria-hidden="true">→</span></span>
    </a>

    <a class="portal-card portal-card--webapp" href="../webapp/">
      <span class="portal-card__icon"><img src="../images/icon-webapp.svg" alt=""></span>
      <span class="portal-card__label">Web application</span>
      <strong>Define browser-product semantics</strong>
      <span>Surfaces, routes, UI states, viewports, validation, and Web-specific evidence coverage composed with reusable lifecycle contracts.</span>
      <span class="portal-card__action">Explore Web application <span aria-hidden="true">→</span></span>
    </a>
  </div>
</section>

<section class="portal-section portal-publication" aria-labelledby="publication-model-title">
  <div class="portal-section__heading">
    <p class="portal-kicker">Publication model</p>
    <h2 id="publication-model-title">Two external providers become one reader-oriented portal</h2>
    <p>In Site publication terminology, a <strong>Provider branch</strong> is a repository-internal canonical source selected by the Site. The external provider set is now <code>composition</code> and <code>policy</code>. The <code>site</code> branch owns integration and deployment and is not an external provider.</p>
  </div>
  <div class="portal-publication__layout">
    <img class="portal-publication__diagram" src="../images/publication-pipeline.svg" alt="Composition and Policy revisions pass through explicit catalogs, full-SHA locks, assembly, and validation before GitHub Pages publication">
    <div class="portal-principles">
      <article>
        <span>01</span>
        <div><h3>Explicit boundary</h3><p>Each provider owns a publication catalog that allowlists public Markdown and machine-readable assets. Uncataloged files remain private to the source branch.</p></div>
      </article>
      <article>
        <span>02</span>
        <div><h3>Immutable inputs</h3><p><code>publication-sources.json</code> records Composition and Policy as reviewed full 40-character commit SHAs.</p></div>
      </article>
      <article>
        <span>03</span>
        <div><h3>Validated output</h3><p>The integrated build checks navigation, links, fragments, repository views, terminology, guided discovery, and provenance.</p></div>
      </article>
    </div>
  </div>
</section>

<section class="portal-tree-callout" aria-labelledby="repository-trees-title">
  <div>
    <p class="portal-kicker">Exact build inputs</p>
    <h2 id="repository-trees-title">Inspect the complete provider trees</h2>
    <p>Browse every tracked path at the exact <code>composition</code> and <code>policy</code> revisions used by this publication.</p>
    <a class="portal-button portal-button--primary" href="../repository-trees/">Open repository trees</a>
  </div>
  <div class="portal-tree-callout__tree" aria-hidden="true">
    <span>templates/</span>
    <span>├── composition/</span>
    <span>└── policy/</span>
  </div>
</section>

</div>

## About this portal

This site is the single GitHub Pages entry point for `TakashiSasaki/templates`.
The `composition` branch is the canonical source for Agent Skill and Web
application artifact semantics plus reusable application capabilities and
lifecycle contracts. The `policy` branch remains the independent canonical
coding-agent policy authority. The `site` branch owns reader information
architecture, integration validation, and the only Pages deployment route.

The public origin is `https://templates.moukaeritai.work/`. The site is served
from the domain root; the former `/templates/` project path is not part of the
public information architecture.

## Composition does not merge artifact semantics

The source authority is shared, but `artifact.skill-core` and
`artifact.webapp-core` remain distinct artifact identities. Runtime, CLI, MCP,
MCP Apps, browser exposure, and service behavior are reusable `capability.*`
components. Composition-state, contract evolution, implementation evidence,
release evidence, and release handoff are reusable `lifecycle.*` components.
The reader paths `/skill/`, `/webapp/`, `/capabilities/`, and `/lifecycle/`
reflect these semantic boundaries rather than separate provider ownership.

## Policy and Composition coexistence

Policy and Composition are intentionally independent authorities even when both
are adopted by the same consumer repository. Their coexistence contract is
specified in [Policy–Composition coexistence](policy-composition-coexistence.md).
The contract defines owned namespaces, prohibited dependencies, ownership
handoffs, collision rules, and cross-authority invariants without introducing a
third consumer-management tool.

## What is published

Each external provider declares its public boundary in
`docs/publication-catalog.json`. Publication catalogs are explicit allowlists,
not requests to copy a branch wholesale. Only cataloged Markdown documents and
explicitly cataloged machine-readable assets are assembled. Tests, workflows,
helper scripts, unlisted generated files, and future source files are not
published merely because they exist.

Machine-readable contracts and schemas are supporting material. Navigation
prioritizes explanatory Markdown intended for human readers. The Composition
provider exposes component descriptors, recipes, schemas, and selected contract
assets explicitly through its catalog while keeping consumer-generated
`contracts/manifest.json` out of source publication.

## Reproducible publication

Provider inputs are recorded as lowercase full 40-character commit SHAs in
`publication-sources.json`. A `site` commit therefore identifies exact
`composition` and `policy` revisions rather than mutable branch tips.

Every uploaded Pages artifact also contains `/build-provenance.json`. It records
the built `site` commit and the exact Composition and Policy commits. This
metadata identifies the publication inputs; it is not a cryptographic signature
or artifact attestation.

## Change ownership

Canonical Composition content changes on the `composition` branch. Canonical
Policy content changes on the `policy` branch. A coordinated Site change updates
the reviewed source lock and reader IA when necessary. Generated Markdown and
HTML remain build artifacts and are not committed to `site`.

The Site build checks out each provider independently at its locked revision,
assembles one temporary documentation project, builds the static site strictly,
validates links and terminology, records provenance, and uploads the Pages
artifact. Provider histories are not merged merely for publication.
