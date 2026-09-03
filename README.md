# TakashiSasaki/templates

This repository provides two reusable provider authorities for building and maintaining software repositories, plus one Site authority for repository integration and publication:

- **Composition** helps you choose and materialize Agent Skill, Website, or Web application structure, capabilities, lifecycle contracts, and validation.
- **Policy** helps you adopt reproducible coding-agent operating rules in a product repository.
- **Site** integrates reviewed Composition and Policy revisions and publishes their human- and machine-facing projections at `https://templates.moukaeritai.work/`.

## Start here

Choose the path that matches the task you are trying to accomplish:

| I want to… | Start with |
|---|---|
| Bootstrap a coding agent to use this repository from another project | Read the machine-readable [`agent.json`](agent.json), also published at `https://templates.moukaeritai.work/agent.json` |
| Build or maintain an Agent Skill, Website, or Web application repository | [Composition](https://templates.moukaeritai.work/composition/) and its [guided view](https://templates.moukaeritai.work/guided/) |
| Choose between a Website and Web application | [Website or Web application?](https://templates.moukaeritai.work/web/) |
| Understand which runtime, CLI, browser, service, MCP, or lifecycle capability to select | [Capabilities](https://templates.moukaeritai.work/capabilities/) and [Lifecycle](https://templates.moukaeritai.work/lifecycle/) |
| Add verifiable coding-agent operating rules to a repository | [Policy](https://templates.moukaeritai.work/policy/) |
| Understand Agent Skill-specific artifact semantics | [Skill](https://templates.moukaeritai.work/skill/) |
| Follow the Website product walkthrough | [Website](https://templates.moukaeritai.work/website/) |
| Understand Web application-specific artifact semantics | [Webapp](https://templates.moukaeritai.work/webapp/) |
| Look up a repository term without leaving the documentation | [Glossary](https://templates.moukaeritai.work/glossary/) |
| Inspect the exact reviewed provider source behind a page | [Repository trees](https://templates.moukaeritai.work/repository-trees/) or [source files](https://templates.moukaeritai.work/files/) |

A first-time application author normally starts with **Composition**, then uses **Policy** when the product repository also needs coding-agent operating rules. You do not need to understand Site publication internals, provider branches, or deployment workflows before using either authority.

The rest of this README documents the repository authority and publication model for maintainers and readers who need provenance or Site implementation details.

## Repository authority model

This repository separates three authorities by responsibility:

| Branch | Authority | Start here when you need to |
|---|---|---|
| `composition` | Agent Skill, Website, and Web application artifact semantics, reusable application capabilities, lifecycle contracts, production recipes/schemas, and the deterministic composer | Define or materialize a Skill/Website/Webapp composition |
| `policy` | Shared coding-agent operating policy and the `agent-policy` selection, validation, rendering, adoption, and release toolchain | Define or apply verifiable agent operating rules |
| `site` | Repository integration and publication authority: reviewed provider selection, integrated documentation portal, reader information architecture, cross-authority integration validation, projection parity, PWA behavior, and the sole Pages deployment route | Integrate or publish the reviewed authorities together without redefining provider semantics |

`composition` is an orphan branch with its own history. `policy` and `site` remain
independent authorities. The Site does not merge provider histories; it selects
reviewed full-commit revisions and assembles their declared publication
boundaries. Site is not a parent or super-authority above Composition or Policy,
and provider-specific semantics remain owned by their provider.

The public portal is `https://templates.moukaeritai.work/`. The custom domain is
served from the domain root, not from the retired `/templates/` project path.

Repository-wide authority ownership and the distinction between normative
requirements, guidance, evidence, projections, examples, and explanations are
defined by [`docs/authority-model.md`](docs/authority-model.md). Normative
publication rules are in [`PUBLISHING.md`](PUBLISHING.md). Canonical terminology
integration is defined by [`GLOSSARY.md`](GLOSSARY.md). Runtime freshness and PWA
cache/fallback invariants are defined by [`FRESHNESS.md`](FRESHNESS.md).

## Authority model

In Site publication terminology, `composition` and `policy` are the two external
**Provider branches**. The `site` branch is the repository integration and
publication authority and is not an external Provider branch. Its deployment
responsibility is part of that publication authority, not a higher-order right to
change provider semantics.

Agent Skill, Website, and Web application are distinct Composition-owned artifact
identities. Their detailed contracts and shared Web foundation semantics remain
canonical on the exact reviewed `composition` revision; Site only maps them into
reader routes.

The reader paths `/skill/`, `/web/`, `/website/`, and `/webapp/` therefore remain
useful, but all Composition-owned semantics behind them are sourced from the same
exact reviewed `composition` revision. Source ownership is not reconstructed from
reader URL grouping.

## Publication model

Each external provider owns `docs/publication-catalog.json`. Catalog schema
version 3 is an explicit allowlist for reader Markdown, machine-readable assets,
and the optional canonical provider glossary.

The Site owns:

- global reader navigation and generated destinations in `site-manifest.json`;
- full-SHA external-provider locks in `publication-sources.json`;
- assembly of `site`, `composition`, and `policy` publication inputs;
- cross-authority integration semantics that satisfy the Site ownership test in
  `docs/authority-model.md`;
- integrated glossary generation with provider/path/revision provenance;
- repository-tree views for Composition and Policy;
- the static source browser for Site, Composition, and Policy;
- deterministic index-guided navigation for Composition and Policy;
- strict static-site build, link validation, provenance, freshness metadata, and
  Pages deployment.

A public document is identified by `publication:document`, for example
`composition:skill-contract`, `composition:website-webapp-selection`, or
`policy:overview`.

## Reader-facing entry points

The integrated portal exposes:

- `/agent.json` — the machine-readable coding-agent bootstrap projection;
- `/schemas/agent-bootstrap.schema.json` — its public JSON Schema;
- `/composition/` — composition architecture, catalog, and composer;
- `/skill/` — Agent Skill artifact semantics;
- `/web/` — the Composition-owned Website/Web application selector;
- `/website/` — Website product walkthrough;
- `/capabilities/` — Site routing index for published Composition capability documents;
- `/webapp/` — Web application artifact semantics;
- `/lifecycle/` — composition-state and product-lifecycle contracts;
- `/policy/` — coding-agent policy;
- `/guided/` — provider-owned progressive disclosure from `index.md`;
- `/repository-trees/` — exact Composition and Policy tracked-path inventories;
- `/files/` — bounded Site/Composition/Policy source snapshots; and
- `/glossary/` — the validated integrated terminology projection.

Machine-readable component descriptors, recipes, schemas, contracts, and other
assets are supporting material. Primary navigation continues to prioritize
explanatory Markdown.

## Canonical bootstrap operations

After reading `agent.json`, first use `task_routing` to determine which independent
authorities the task requires. Provider independence does not make an authority
optional when the task itself requires that authority.

For Composition, execute the complete
`composition_bootstrap.verified_installer_argv` array exactly, resolving only its
documented placeholders and argument bindings. For Policy, execute the complete
`policy_bootstrap.immutable_installer_argv` array exactly, then use
`policy_workflow.unmanaged_inspect_argv` before any Policy adoption mutation.
When both routing conditions apply, follow `task_routing.combined.authority_order`
and keep the two providers' state and validation independent.

Do not reconstruct either bootstrap operation from installer or Skill metadata,
and do not independently reimplement the declared download or execute steps. The
`canonical_operation` and `reimplementation_policy` fields are machine-readable
reminders of this contract.


## Source locking and provenance

`publication-sources.json` contains exactly the reviewed `composition` and
`policy` full 40-character commit SHAs used by normal builds. Workflow-call
overrides exist only for deliberate compatibility/review testing.

Every uploaded Pages artifact contains `/build-provenance.json`, which records
the built `site` commit and exact Composition and Policy commits. It identifies
publication inputs; it is not a cryptographic attestation.

## Repository and guided views

Repository-tree generation uses the composition-era entrypoint:

```sh
python site/scripts/generate_repository_trees_composition.py \
  --repository TakashiSasaki/templates \
  --site-root site-publication \
  --output-root build \
  --publication composition=sources/composition \
  --publication policy=sources/policy
```

The standalone source browser uses the canonical Site-owned entrypoint and the
three active authorities directly:

```sh
python site/scripts/generate_repository_browser.py \
  --repository TakashiSasaki/templates \
  --output-root build/site \
  --branch site=site \
  --branch composition=sources/composition \
  --branch policy=sources/policy
```

Index-guided navigation uses one composition-era wrapper for graph, locale,
viewer, and localized-viewer generation:

```sh
python site/scripts/run_composition_navigation.py graph \
  --repository TakashiSasaki/templates \
  --output build/index-navigation.json \
  --provider composition=sources/composition \
  --provider policy=sources/policy

python site/scripts/run_composition_navigation.py viewer \
  --repository TakashiSasaki/templates \
  --graph build/index-navigation.json \
  --site-root site-publication \
  --output-root build/site \
  --provider composition=sources/composition \
  --provider policy=sources/policy

python site/scripts/finalize_site_metadata.py \
  --site-root build/site/guided \
  --canonical-url https://templates.moukaeritai.work/
```

Fragment-free uncataloged regular-file targets resolve to the same immutable
`/files/` snapshot. Uncataloged regular-file targets with any fragment use the
exact full-SHA immutable GitHub source because the Site cannot safely claim a
fragment mapping for an unrendered source file.

## Local publication validation

Check out the independent authorities into separate directories, using the
provider revisions locked by `publication-sources.json`:

```text
site/
sources/composition/
sources/policy/
```

Then run the material stages used by Pages:

```sh
python -m unittest discover --start-directory site/tests --verbose

python site/scripts/prepare_repository_tree_publication.py \
  --site-root site \
  --output-root site-publication

python site/scripts/assemble_publications_v3.py \
  --publication site=site-publication \
  --publication composition=sources/composition \
  --publication policy=sources/policy \
  --site-root site-publication \
  --output-root build

python site/scripts/publish_provider_translations.py \
  --publication site=site-publication \
  --publication composition=sources/composition \
  --publication policy=sources/policy \
  --site-root site-publication \
  --output-root build

python site/scripts/generate_repository_trees_composition.py \
  --repository TakashiSasaki/templates \
  --site-root site-publication \
  --output-root build \
  --publication composition=sources/composition \
  --publication policy=sources/policy

python site/scripts/generate_repository_file_previews_composition.py \
  --repository TakashiSasaki/templates \
  --site-root site-publication \
  --output-root build \
  --publication composition=sources/composition \
  --publication policy=sources/policy

zensical build --config-file build/zensical.toml --clean --strict

python site/scripts/generate_glossary.py \
  --repository TakashiSasaki/templates \
  --output build/site/glossary/index.json \
  --publication site=site-publication \
  --revision "site=$(git -C site rev-parse HEAD)" \
  --publication composition=sources/composition \
  --revision "composition=$(git -C sources/composition rev-parse HEAD)" \
  --publication policy=sources/policy \
  --revision "policy=$(git -C sources/policy rev-parse HEAD)"

python site/scripts/generate_repository_browser.py \
  --repository TakashiSasaki/templates \
  --output-root build/site \
  --branch site=site \
  --branch composition=sources/composition \
  --branch policy=sources/policy

python site/scripts/run_composition_navigation.py graph \
  --repository TakashiSasaki/templates \
  --output build/index-navigation.json \
  --provider composition=sources/composition \
  --provider policy=sources/policy

python site/scripts/run_composition_navigation.py locales \
  --graph build/index-navigation.json \
  --output build/index-navigation-locales.json \
  --provider composition=sources/composition \
  --provider policy=sources/policy

python site/scripts/run_composition_navigation.py viewer \
  --repository TakashiSasaki/templates \
  --graph build/index-navigation.json \
  --site-root site-publication \
  --output-root build/site \
  --provider composition=sources/composition \
  --provider policy=sources/policy

python site/scripts/finalize_site_metadata.py \
  --site-root build/site/guided \
  --canonical-url https://templates.moukaeritai.work/

python site/scripts/write_publication_provenance.py \
  --output build/site/build-provenance.json \
  --repository TakashiSasaki/templates \
  --site-commit "$(git -C site rev-parse HEAD)" \
  --publication-commit "composition=$(git -C sources/composition rev-parse HEAD)" \
  --publication-commit "policy=$(git -C sources/policy rev-parse HEAD)"

python site/scripts/validate_site_links.py \
  --site-root build/site \
  --config-file build/zensical.toml
```

Browser-level mobile/PWA checks remain governed by `FRESHNESS.md` and the
existing visual-regression workflows; the provider cutover does not weaken those
contracts.

## Deployment boundary

`.github/workflows/build-pages.yml` is build-only. It may run for pull requests
or through `workflow_call`, but it has read-only repository permission and no
Pages deployment authority.

`.github/workflows/deploy-pages.yml` is the only Pages deployment route and runs
only on a push to `site`. The external `github-pages` environment is configured
to allow exactly the `site` branch. Pull requests cannot change this setting;
changing it requires repository/environment administration. Do not broaden the
environment to all branches or introduce a second deployment workflow.

## Retired direct-copy publication path

The Site no longer generates dedicated Skill, Website, or Webapp copyable-template
trees. Those workflows, scripts, and integration tests were tied to the retired
monolithic `template/` source model. Source inspection now presents the exact
Composition tree, while consumer repositories are produced by the composition
composer.
