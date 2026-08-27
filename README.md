# TakashiSasaki/templates

This repository provides two reusable authorities for building and maintaining software repositories, plus one integrated documentation site:

- **Composition** helps you choose and materialize Agent Skill or Web application structure, capabilities, lifecycle contracts, and validation.
- **Policy** helps you adopt reproducible coding-agent operating rules in a product repository.
- **Site** publishes the reviewed Composition and Policy documentation together at `https://templates.moukaeritai.work/`.

## Start here

Choose the path that matches the task you are trying to accomplish:

| I want to… | Start with |
|---|---|
| Bootstrap a coding agent to use this repository from another project | Read the machine-readable [`agent.json`](agent.json), also published at `https://templates.moukaeritai.work/agent.json` |
| Build or maintain an Agent Skill or Web application repository | [Composition](https://templates.moukaeritai.work/composition/) and its [guided view](https://templates.moukaeritai.work/guided/) |
| Understand which runtime, CLI, browser, service, MCP, or lifecycle capability to select | [Capabilities](https://templates.moukaeritai.work/capabilities/) and [Lifecycle](https://templates.moukaeritai.work/lifecycle/) |
| Add verifiable coding-agent operating rules to a repository | [Policy](https://templates.moukaeritai.work/policy/) |
| Understand Agent Skill-specific artifact semantics | [Skill](https://templates.moukaeritai.work/skill/) |
| Understand Web application-specific artifact semantics | [Webapp](https://templates.moukaeritai.work/webapp/) |
| Look up a repository term without leaving the documentation | [Glossary](https://templates.moukaeritai.work/glossary/) |
| Inspect the exact reviewed provider source behind a page | [Repository trees](https://templates.moukaeritai.work/repository-trees/) or [source files](https://templates.moukaeritai.work/files/) |

A first-time application author normally starts with **Composition**, then uses **Policy** when the product repository also needs coding-agent operating rules. You do not need to understand Site publication internals, provider branches, or deployment workflows before using either authority.

The rest of this README documents the repository authority and publication model for maintainers and readers who need provenance or Site implementation details.

## Repository authority model

This repository separates three authorities by responsibility:

| Branch | Authority | Start here when you need to |
|---|---|---|
| `composition` | Agent Skill and Web application artifact semantics, reusable application capabilities, lifecycle contracts, production recipes/schemas, and the deterministic composer | Define or materialize a Skill/Webapp composition |
| `policy` | Shared coding-agent operating policy and the `agent-policy` selection, validation, rendering, adoption, and release toolchain | Define or apply verifiable agent operating rules |
| `site` | The integrated documentation portal, reader information architecture, publication validation, repository views, PWA behavior, and the sole Pages deployment route | Read or publish the reviewed authorities together |

`composition` is an orphan branch with its own history. `policy` and `site` remain
independent authorities. The Site does not merge provider histories; it selects
reviewed full-commit revisions and assembles their declared publication
boundaries.

The public portal is `https://templates.moukaeritai.work/`. The custom domain is
served from the domain root, not from the retired `/templates/` project path.

Normative publication rules are in [`PUBLISHING.md`](PUBLISHING.md). Canonical
terminology integration is defined by [`GLOSSARY.md`](GLOSSARY.md). Runtime
freshness and PWA cache/fallback invariants are defined by
[`FRESHNESS.md`](FRESHNESS.md).

## Authority model

In Site publication terminology, `composition` and `policy` are the two external
**Provider branches**. The `site` branch is the integration and deployment
authority and is not an external Provider branch.

Skill and Webapp are still distinct artifact identities:

- `artifact.skill-core` owns Agent Skill trigger/workflow/resource semantics;
- `artifact.webapp-core` owns browser-product semantics;
- `capability.*` owns reusable runtime and public-interface capabilities;
- `lifecycle.*` owns reusable composition-state, contract-evolution, evidence,
  and release-handoff concerns.

The reader paths `/skill/` and `/webapp/` therefore remain useful, but both are
sourced from the same exact reviewed `composition` revision. Source ownership is
not reconstructed from reader URL grouping.

## Publication model

Each external provider owns `docs/publication-catalog.json`. Catalog schema
version 3 is an explicit allowlist for reader Markdown, machine-readable assets,
and the optional canonical provider glossary.

The Site owns:

- global reader navigation and generated destinations in `site-manifest.json`;
- full-SHA external-provider locks in `publication-sources.json`;
- assembly of `site`, `composition`, and `policy` publication inputs;
- integrated glossary generation with provider/path/revision provenance;
- repository-tree views for Composition and Policy;
- the static source browser for Site, Composition, and Policy;
- deterministic index-guided navigation for Composition and Policy;
- strict static-site build, link validation, provenance, freshness metadata, and
  Pages deployment.

A public document is identified by `publication:document`, for example
`composition:skill-contract`, `composition:contract-evolution`, or
`policy:overview`.

## Reader-facing entry points

The integrated portal exposes:

- `/agent.json` — the machine-readable coding-agent bootstrap projection;
- `/schemas/agent-bootstrap.schema.json` — its public JSON Schema;
- `/composition/` — composition architecture, catalog, and composer;
- `/skill/` — Agent Skill artifact semantics;
- `/capabilities/` — runtime, CLI, MCP, MCP Apps, browser, and service
  capabilities;
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

The standalone source browser uses Site, Composition, and Policy:

```sh
python site/scripts/generate_repository_browser_composition.py \
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

python site/scripts/generate_repository_browser_composition.py \
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

The Site no longer generates dedicated Skill or Webapp copyable-template trees.
Those workflows, scripts, and integration tests were tied to the retired
monolithic `template/` source model. Source inspection now presents the exact
Composition tree, while consumer repositories are produced by the composition
composer.
