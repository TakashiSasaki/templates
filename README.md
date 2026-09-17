# TakashiSasaki/templates

Four independent authorities provide reusable Composition and Policy systems and publish them through Integration and Site.

- **Composition** owns artifact, capability, lifecycle and topology semantics, Composer, schemas, documentation and translations.
- **Policy** owns coding-agent operating semantics, procedures, profiles, tooling, documentation and translations.
- **Integration** selects reviewed providers and produces a deterministic Integrated Publication Bundle, including reader IA, translation availability, glossary, guided navigation and exact provenance.
- **Site** renders the selected Bundle and owns presentation, browser runtime, PWA, accessibility and explicit GitHub Pages deployment.

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
| Inspect the exact reviewed provider source behind a page | Follow the immutable GitHub source links in [Guided navigation](https://templates.moukaeritai.work/guided/) |

A first-time application author normally starts with **Composition**, then uses **Policy** when the product repository also needs coding-agent operating rules. You do not need to understand Site publication internals, provider branches, or deployment workflows before using either authority.

The rest of this README documents the repository authority and publication model for maintainers and readers who need provenance or Site implementation details.

## Repository authority model

`composition + policy → integration → site → GitHub Pages`

Each authority retains an independent Git history. Site is not a parent authority.
The [authority model](docs/authority-model.md) and [machine discovery](agent.json)
describe the same topology. The published discovery document receives exact
provider provenance from the selected Bundle.

## Publication model

Site's only provider-publication selection is [integration-source.json](integration-source.json).
It binds an exact Integration revision, Bundle schema, identity and content digest.
Integration owns the provider pair; Site has no active provider publication lock.
New Integration releases do not trigger Site adoption or deployment.

An explicit Integration adoption changes this lock. A Site-only UI, PWA or security
fix retains it. Both use the same [Site qualification and deployment process](PUBLISHING.md).
The renderer runs with only Site and the immutable Bundle; provider checkouts and
Integration implementation source are absent.

## Local publication validation

Read [MAINTENANCE.md](MAINTENANCE.md), [PUBLISHING.md](PUBLISHING.md) and
[LANGUAGE.md](LANGUAGE.md). English is authoritative. Available stale translations
carry a visible non-authoritative warning and a link to current English.

The Site also independently consumes Composition's public Website contract and
Policy's maintenance rules. [reference-consumer.json](reference-consumer.json)
records these product/toolchain relationships separately from publication input.
They do not select provider publication revisions.

The [migration audit](migration/final-architecture-audit.md) records retirement of
the transitional local Integration producer and historical audit dispositions.

GitHub Pages environment restrictions are configured outside source control. Pull requests cannot change this setting; verify the environment allows only `site` before deployment.
