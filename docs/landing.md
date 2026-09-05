# Templates documentation portal

<div class="portal-landing portal-landing--cover">

<section class="portal-cover" aria-labelledby="portal-cover-title">
  <div class="portal-cover__copy">
    <p class="portal-cover__kicker">Start from the task you want to complete</p>
    <h1 id="portal-cover-title">
      Build a <span class="portal-accent portal-accent--webapp">Website or Web application</span>,
      create an <span class="portal-accent portal-accent--skill">Agent Skill</span>,
      or add coding-agent rules
    </h1>
    <p class="portal-cover__lead">
      You normally do <strong>not</strong> turn this <code>templates</code> repository into your product repository.
      Keep your product in a separate repository, then use the appropriate templates tooling and contracts there.
    </p>
    <div class="portal-cover__actions">
      <a class="portal-cover__button portal-cover__button--primary" href="web/">
        Website or Web application <span aria-hidden="true">→</span>
      </a>
      <a class="portal-cover__button portal-cover__button--secondary" href="composition/use/skill-first-use-walkthrough/">
        Create an Agent Skill <span aria-hidden="true">→</span>
      </a>
    </div>
    <ul class="portal-cover__signals" role="list">
      <li>Start with a concrete task; learn the architecture later.</li>
      <li>Composition owns browser-product selection and shared Web semantics.</li>
      <li>Policy is optional and independent from Composition.</li>
    </ul>
  </div>

  <div class="portal-cover__visual">
    <img src="images/landing-architecture.svg" alt="Composition defines Agent Skill, Website, and Web application artifacts while Policy independently defines coding-agent operation; the Site publishes both authorities through one validated portal">
  </div>
</section>

<section class="portal-authority" aria-labelledby="portal-build-title">
  <div class="portal-section-heading">
    <p class="portal-section-heading__kicker">What do you want to do?</p>
    <h2 id="portal-build-title">Choose a task, not an internal authority</h2>
    <p>Each entry point routes to the authority that owns the detailed procedure. You do not need to understand Composition, capabilities, or lifecycle contracts before starting. Want to explore the resolved output interactively first? <a href="playground/">Try Composition Playground</a>.</p>
  </div>

  <div class="portal-artifact-grid">
    <a class="portal-artifact-card portal-artifact-card--webapp" href="web/">
      <span class="portal-artifact-card__icon"><img src="images/icon-web.svg" alt=""></span>
      <span class="portal-artifact-card__copy">
        <strong>Choose Website or Web application</strong>
        <span>Follow Composition's canonical selector, then continue to the published Website or Web application walkthrough.</span>
      </span>
      <span class="portal-artifact-card__arrow" aria-hidden="true">→</span>
    </a>

    <a class="portal-artifact-card portal-artifact-card--skill" href="composition/use/skill-first-use-walkthrough/">
      <span class="portal-artifact-card__icon"><img src="images/icon-skill.svg" alt=""></span>
      <span class="portal-artifact-card__copy">
        <strong>Create an Agent Skill</strong>
        <span>Follow the Release Note Helper walkthrough from a separate consumer repository to a concrete knowledge-augmented Skill and behavioral evaluation.</span>
      </span>
      <span class="portal-artifact-card__arrow" aria-hidden="true">→</span>
    </a>
  </div>
</section>

<section class="portal-policy-panel" aria-labelledby="portal-policy-title">
  <span class="portal-policy-panel__icon"><img src="images/icon-policy.svg" alt=""></span>
  <div class="portal-policy-panel__copy">
    <p class="portal-policy-panel__label">Independent task · Policy</p>
    <h2 id="portal-policy-title">Add coding-agent rules to a repository</h2>
    <p>Use the Policy getting-started path for fresh adoption or migration of existing agent instructions. Policy is a separate authority, not a Composition capability.</p>
  </div>
  <a class="portal-policy-panel__action" href="policy/getting-started/">Start Policy adoption <span aria-hidden="true">→</span></a>
</section>

<section class="portal-authority" aria-labelledby="portal-repository-model-title">
  <div class="portal-section-heading portal-section-heading--compact">
    <p class="portal-section-heading__kicker">Mental model</p>
    <h2 id="portal-repository-model-title">Work in your product repository</h2>
    <p>The normal relationship is:</p>
  </div>

```text
TakashiSasaki/templates
        |
        | provides tooling and contracts
        v
your separate product repository
```

<p>Clone or create your product repository separately. The provider-owned tutorials tell you what to install or run there. The <code>templates</code> repository itself is primarily the source of the tooling, contracts, and documentation.</p>
</section>

<nav class="portal-doc-nav" aria-labelledby="portal-doc-nav-title">
  <div class="portal-section-heading portal-section-heading--compact">
    <p class="portal-section-heading__kicker">Already started, or want the model?</p>
    <h2 id="portal-doc-nav-title">Explore the architecture and references</h2>
  </div>
  <div class="portal-doc-links">
    <a class="portal-doc-link" href="composition/">Explore Composition</a>
    <a class="portal-doc-link" href="playground/">Composition Playground</a>
    <a class="portal-doc-link" href="composition/concepts/">Composition concepts</a>
    <a class="portal-doc-link" href="web/">Website or Web application?</a>
    <a class="portal-doc-link" href="website/">Explore Website</a>
    <a class="portal-doc-link" href="webapp/">Explore Web application</a>
    <a class="portal-doc-link" href="skill/">Explore Agent Skill</a>
    <a class="portal-doc-link" href="policy/">Explore Policy</a>
    <a class="portal-doc-link" href="capabilities/">Capabilities</a>
    <a class="portal-doc-link" href="lifecycle/">Lifecycle</a>
    <a class="portal-doc-link" href="/glossary/">Glossary</a>
    <a class="portal-doc-link" href="/guided/">Browse by index.md</a>
    <a class="portal-doc-link" href="repository-trees/">Repository trees</a>
    <a class="portal-doc-link" href="files/">Source files</a>
  </div>
</nav>

<section class="portal-guarantees" aria-labelledby="portal-guarantees-title">
  <div class="portal-section-heading portal-section-heading--compact">
    <p class="portal-section-heading__kicker">Publication guarantees</p>
    <h2 id="portal-guarantees-title">Reviewed sources, reproducible output</h2>
  </div>
  <div class="portal-guarantees__grid">
    <article>
      <span class="portal-guarantees__mark" aria-hidden="true">01</span>
      <div><h3>Separated by responsibility</h3><p>Composition, Policy, and Site integration have explicit authorities.</p></div>
    </article>
    <article>
      <span class="portal-guarantees__mark" aria-hidden="true">02</span>
      <div><h3>Locked for integrity</h3><p>The Site selects reviewed Composition and Policy revisions by full commit SHA.</p></div>
    </article>
    <article>
      <span class="portal-guarantees__mark" aria-hidden="true">03</span>
      <div><h3>Validated for readers</h3><p>Assembly, navigation, links, provenance, glossary semantics, and Pages output are checked.</p></div>
    </article>
  </div>
</section>

</div>