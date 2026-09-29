# TakashiSasaki/templates

Five independent authorities provide reusable source, Composition, Policy, Integration, and Site capabilities while preserving independent histories.

- **Modeling** owns bounded information-model records and their generated discovery projections.
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

### Maintain this repository

Use the [maintainer guide](docs/maintainer-onboarding.md), [local preview](MAINTENANCE.md)
and [publication runbook](PUBLISHING.md). Source flows one way:

`Modeling + Composition + Policy + other providers -> Integration Bundle -> Site -> Pages`.

Authorities retain independent Git histories. Integration resolves configured branches
once per build and records exact provenance. Site consumes successful artifacts without
adoption commits, provider checkouts or controller pins. A Site appearance change can be
tested and released against an already downloaded publication. New catalog documents
receive generated routes and navigation. There is no backward-compatibility requirement.

[Site source navigation](index.md) links the implementation and local documentation.
