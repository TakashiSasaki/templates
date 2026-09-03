# Integrated publication policy

This policy applies to the `site`, `composition`, and `policy` authorities in
`TakashiSasaki/templates`.

## Objective

The `site` branch publishes one human-readable GitHub Pages portal from exact
reviewed revisions of two external Provider branches:

- `composition` — canonical Agent Skill, Website, and Web application artifact
  semantics, shared foundations, reusable capabilities, lifecycle contracts,
  recipes, schemas, and composer documentation;
- `policy` — canonical coding-agent operating policy and the agent-policy
  toolchain.

`site` is the repository integration and publication authority. Pages deployment
is part of that publication authority. Site is not an external Provider branch
and is not a parent or super-authority above Composition or Policy. The portal may
group Composition material under reader-oriented paths such as `/skill/`,
`/web/`, `/website/`, `/webapp/`, `/capabilities/`, and `/lifecycle/`; those paths
do not create separate source ownership.

The publication system must be explicit, reproducible, reviewable, and safe
against accidental branch-wide disclosure.

## Responsibilities

Provider branches (`composition` and `policy`) own:

- canonical documentation and supporting public assets;
- `docs/publication-catalog.json`, which defines the provider's public boundary;
- `docs/glossary.yml` when the provider owns canonical terminology;
- stable document IDs and canonical source paths;
- stable glossary term IDs and repository-owned definitions;
- provider-owned `index.md` navigation semantics; and
- provider-local validation of public-boundary changes.

The `site` branch owns:

- portal home and reader-facing information architecture;
- cross-provider titles, grouping, ordering, and generated destinations;
- reviewed full-SHA source locks in `publication-sources.json`;
- integrated assembly and strict static-site generation;
- cross-authority integration semantics that satisfy the Site ownership test in
  `docs/authority-model.md`;
- integrated glossary generation;
- repository trees, bounded inline previews, and the static source browser for
  exact build inputs;
- deterministic index-guided navigation for Composition and Policy;
- generated link, fragment, asset, canonical-URL, and provenance validation; and
- the sole repository workflow authorized to deploy GitHub Pages.

A document is globally identified by `publication:document`, for example
`composition:skill-contract`, `composition:website-webapp-selection`,
`composition:contract-evolution`, or `policy:overview`.

## Repository-wide authority semantics

`docs/authority-model.md` is the canonical Site-owned normative contract for
repository-wide authority ownership and semantic roles. It defines the Site
ownership test and distinguishes normative authority, normative requirements,
guidance, evidence, projections, examples, and explanations without classifying
material by file format alone.

This publication policy applies that model to publication and integration. It
must not be used to promote provider-specific guidance into a requirement, make a
projection into a new semantic source, or transfer Composition/Policy semantics
to Site. Provider-specific rules remain owned by the provider even when Site
publishes, validates, translates, or projects them.

## Human and machine projection parity

The human-facing portal and the machine-facing repository/bootstrap surface are
different projections of the same reviewed authorities. They may differ in
presentation, navigation, progressive disclosure, localization, and executable
detail, but they must not lead humans and coding agents to different normative
models of this repository.

The projections must converge on the same:

- authority owner for each task or semantic domain;
- exact reviewed Composition and Policy publication revisions;
- provider lifecycle, ownership, and safety semantics;
- independence of Policy and Composition, including that Policy is optional
  relative to Composition; and
- Site-owned cross-provider integration contracts whose meaning affects safe
  consumer behavior.

The Site may explain, organize, route, translate, visualize, and integrate
provider-owned material. Site-owned reader prose must not silently redefine
Composition or Policy semantics. Site may own genuinely cross-provider semantics,
such as the Policy–Composition coexistence contract, only when the rule satisfies
the ownership test in `docs/authority-model.md`: it governs integration or
interaction between independent authorities and cannot correctly be owned by
either provider independently.

The machine-facing projection must expose enough authority metadata for a coding
agent to discover those boundaries without being forced through the deployed
human portal. In particular, `agent.json` must project the exact locked
Composition and Policy revisions, their distinct authority roles, the independent
and optional relationship of Policy to Composition, Site's non-mutating
integration role, and the canonical Site-owned coexistence contract. Executable
bootstrap remains a separate concern: exposing Policy as an authority does not
make Policy a Composition dependency or merge their consumer management planes.

Parity is validated through stable semantic identifiers, authority roles,
revision identity, and canonical contract references. It does not require human
prose and machine-readable data to be textually identical or to present concepts
in the same order.

## Public boundary

Publication catalogs are explicit allowlists. The assembler must not infer that
a file is public from its directory, extension, Git tracking status, or presence
in a provider branch.

The following rules apply:

1. Only Markdown entries in a provider publication catalog are rendered as
   documentation pages.
2. Only non-Markdown assets explicitly declared by the applicable catalog are
   copied as provider assets.
3. A provider glossary participates only when a schema-version-3 catalog declares
   `glossary.source`.
4. Tests, workflows, scripts, generated output, working notes, and newly added
   files do not become cataloged documentation merely because they are tracked.
5. Branch-wide copies and unrestricted glob-based publication are prohibited for
   cataloged documentation and provider assets.
6. Machine-readable contracts, descriptors, recipes, and schemas may be
   published as explicit supporting assets, while navigation should prioritize
   explanatory Markdown.
7. Catalog paths, glossary paths, and asset traversal must reject unsafe paths,
   parent traversal, `.git` components, and symbolic-link traversal.

Adding a file to a provider branch does not publish it. Adding or changing a
catalog entry is a public-interface change and requires review.

## Composition publication boundary

`composition` is one provider even though it contains several semantic classes:

- `foundation.web` is the transitive shared browser foundation for Website and
  Web application artifacts;
- `artifact.skill-core`, `artifact.website-core`, and `artifact.webapp-core`
  remain distinct artifact identities;
- `capability.*` components are reusable optional capabilities rather than
  artifact classifiers; and
- `lifecycle.*` components are reusable lifecycle contracts.

The Site must not reconstruct `skill`, `website`, or `webapp` as independent
canonical providers. Reader grouping may distinguish them and may expose shared
Web material separately, but provenance must resolve to one exact Composition
revision.

Consumer-generated `contracts/manifest.json` is not a source publication file.
The Composition provider publishes the descriptors, contract registrations, and
schemas from which the composer deterministically generates it.

## Glossary publication

`GLOSSARY.md` is the Site glossary contract. Provider-owned
`docs/glossary.yml` files are canonical semantic inputs integrated from the exact
reviewed revisions used by the rest of the build.

The integrated glossary must:

- preserve globally unique stable term IDs;
- record provider, source path, and exact source revision for every term;
- reject duplicate IDs and unresolved related-term references;
- preserve external authority metadata for `external-*` concepts; and
- permit cross-provider relations such as Composition-owned
  `templates-skill-profile` relating to Policy-owned `templates-policy-profile`.

The Composition glossary is intentionally encoded as strict JSON syntax in a
`.yml` file. JSON is a YAML 1.2 subset; the actual Site PyYAML integration path
must parse and validate those exact bytes during CI.

## Source locking and provenance

`publication-sources.json` contains exactly `composition` and `policy`. Each
locked revision must be a lowercase full 40-character commit SHA.

The reusable build workflow may accept explicit reviewed overrides, but absence
of an override resolves to the lock. It must never fall back from a missing
provider output to the pull-request merge ref or another mutable branch.

Every Pages artifact contains `/build-provenance.json` recording:

- the built `site` commit;
- the exact Composition commit; and
- the exact Policy commit.

The provenance record identifies inputs; it is not a cryptographic attestation.

## Repository views

Repository trees and inline previews cover the exact Composition and Policy
provider revisions. The source browser covers `site`, `composition`, and
`policy`. These are bounded build-time views, not cataloged-document ownership.

Symlinks and gitlinks are never followed. Eligible preview content is read from
immutable Git blob objects, must be strict UTF-8 text, and is capped at 256 KiB.
Preview content is rendered only inside a sandboxed inline frame; source text is
escaped and is never injected into the trusted parent DOM. Entries that do not
meet the preview boundary retain immutable source links instead.

The former Skill/Webapp copyable-template trees are retired. Source inspection
must present the Composition source tree rather than regenerate the abandoned
monolithic `template/` distribution model.

## Index-guided navigation

The canonical guided graph contains providers in deterministic order:

1. `composition`;
2. `policy`.

Provider-owned `docs/index.md` files supply the semantic progressive-disclosure
structure. Site may render localized overlays but must not transfer canonical
navigation ownership to translated material.

The graph records the exact full-SHA provider revisions used by publication.

For guided links, an uncataloged regular tracked file with any fragment opens the exact full-SHA immutable GitHub source. Fragment-free uncataloged regular files may use the bounded immutable `/files/` snapshot.

Nested guided-index URLs identify the current reviewed provider/path projection; the exact provider revision is recorded in the guided page and graph rather than encoded in that nested URL.

## Stable reader entry points

The integrated IA must provide at least:

- `/`;
- `/composition/`;
- `/skill/`;
- `/web/`;
- `/website/`;
- `/webapp/`;
- `/capabilities/`;
- `/lifecycle/`;
- `/policy/`;
- `/repository-trees/` with Composition and Policy entries;
- `/files/` with Site, Composition, and Policy entries;
- `/guided/` with Composition and Policy entries; and
- `/glossary/`.

Generated destinations are stable public paths controlled by `site-manifest.json`.
They are independent of provider source paths.

## Deployment authority

Only `.github/workflows/deploy-pages.yml` may deploy GitHub Pages, and it runs
only for a push to `site`. Pull-request builds may construct and upload a Pages
artifact for validation but cannot deploy it.

The GitHub Pages deployment environment is an external release gate. Its custom
deployment branch policy must allow exactly the `site` branch. The obsolete
`main` authorization has been removed. Do not broaden the environment to all
branches or add another deployment authority.

`https://templates.moukaeritai.work/` is the configured Pages base URL. HTTPS
enforcement is enabled. The retired `/templates/` project path must not reappear
in generated public URLs.

## Acceptance checks

Before a Site cutover is considered complete:

- source-lock parsing proves the provider set is exactly Composition and Policy;
- both provider checkouts are at the locked full SHAs;
- repository and public `agent.json` projections are byte-identical and schema-valid;
- machine authority discovery projects the exact locked Composition and Policy
  revisions, distinct authority roles, Policy's independent/optional relationship,
  Site's non-mutating integration role, and the canonical coexistence contract;
- human and machine authority descriptions are consistent with
  `docs/authority-model.md` and do not make Site a provider super-authority;
- every catalog document is mapped exactly once by `site-manifest.json`;
- the Composition glossary parses through the actual Site YAML loader;
- repository trees/browser/guided navigation use the new provider set;
- no Skill/Webapp copyable-tree generator is part of the build;
- `/build-provenance.json` records Site, Composition, and Policy revisions;
- generated links/fragments/canonical URLs validate; and
- the `site`-only deployment boundary remains intact.

## Coordinated cross-authority document-set changes

When adding a provider document would make either a provider-first or Site-first
merge fail the exact catalog-coverage contract, use `PUBLICATION_STAGING.md`.
The required sequence is Site staging PR → provider publication PR → Site
promotion PR. The staging PR must leave the active Site manifest and provider
locks coherent; the provider candidate build must use the reviewed full-SHA Site
staging revision and explicitly name the staging ID; and the promotion PR must
advance the provider lock to the actual merged provider commit and succeed again
without staging.

`publication_staging_id` is a build-only compatibility input. It must never be
supplied by `.github/workflows/deploy-pages.yml` or treated as a permanent
publication mode. Staging changes Site-owned integration metadata only; provider
prose, catalogs, glossary definitions, and provider translations remain owned by
the provider authority.
