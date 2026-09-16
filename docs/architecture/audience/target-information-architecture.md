# Target information architecture

> **Historical design record:** This pre-cutover design records the audience migration.
> The current public destination/semantic navigation authority is Integration's selected
> Publication Bundle. Site owns its audience UI and rendering. References below to
> a Site manifest or Site-owned integration describe the historical implementation.


This is the normative target reader taxonomy. It is not a production route map.
The [matrix](migration-matrix.json) assigns every audited canonical document to
label paths below these sections; canonical URL decisions belong to the later
Site foundation implementation. Existing destinations remain evidence rather
than an instruction to preserve accidental groupings.

```text
/ (neutral landing)
├── Use templates
│   ├── Start here
│   ├── Composition
│   ├── Website
│   ├── Web application
│   ├── Agent Skill
│   ├── Policy
│   ├── Capabilities
│   ├── Product lifecycle
│   ├── Repository topology
│   ├── Migrations
│   └── Reference
└── Maintain templates
    ├── Maintainer overview
    ├── Authorities
    │   ├── Site
    │   ├── Composition
    │   └── Policy
    ├── Authority coexistence
    ├── Self-hosting
    ├── Publication
    ├── Site operation
    ├── Validation and qualification
    ├── Development workflow
    ├── Architecture decisions
    ├── Repository history
    └── Repository inspection
```

## Why this taxonomy fits the audited repository

Use starts with the existing Website/Web application selector and three concrete
first-use walkthroughs. Composition groups concepts, consumer operations, and the
Site Playground. Website, Web application, and Agent Skill remain separate
artifact journeys; reusable capability pages do not become extra artifact types.
The shared Web selector belongs in Start here and shared Web guidance in
Reference, so an extra ambiguous "Web" portal is unnecessary.

Product lifecycle includes Composition state, contract evolution, implementation
evidence, checkpoints, and product release execution/evidence/bundles. These are
consumer responsibilities. Migrations provides a second discovery path for
consumer contract upgrades, distinct from historical authority migration records.
Repository topology describes selecting topology for a consumer, not how Site
acquires authority over providers. Reference retains technical Composition and
Policy contracts with additional maintainer memberships where justified.

Maintain gathers material currently dispersed among provider architecture,
publication pages, Policy ADRs, the coexistence page, and uncataloged Site root
contracts. Authorities distinguishes each semantic owner. Publication owns
integration discovery for locking, staging/cutover, catalog boundaries, language,
and glossary assembly. Site operation covers deployed freshness/PWA behavior.
Validation and qualification distinguishes provider evaluation/toolchain readiness
from testing a consumer product. Architecture decisions and Repository history
separate active design rationale from superseded decisions and authority migration.

Policy's existing provider/shared/consumer documentation layers remain meaningful
provider semantics but do not become Site audiences. Consumer application,
configuration, CLI and profile selection are Use. Provider release/publication,
repository layout, readiness and historical inventories are Maintain. Shared
references keep a single identity and can appear in both.

## Landing, switcher, navigation, and breadcrumbs

The neutral landing offers two explicitly labeled journeys with concise task
descriptions and direct starting links. It must not require a consumer to inspect
provider release pins or CI architecture to choose a product. The current landing
document remains a single canonical identity, reachable from both overviews.

The global switcher remains visible in both journeys and shared services, exposes
the current audience in text and accessible state, and follows the audience-model
transition table. Shared documents stay on the same canonical content/fragment;
single-audience documents switch to the other journey overview. Ordinary links
to a document outside the current journey announce that destination audience.

Navigation lists memberships for the resolved audience, with provider names used
as subject/ownership labels rather than audience substitutes. Breadcrumbs begin
with the resolved audience and follow the selected membership, falling back to
the first membership for that audience. Provider-owned index-guided disclosure
continues to reflect provider indexes; Site may contextualize its surrounding
navigation but must not rewrite provider meaning or silently suppress essential
cross-audience links.

## Shared services

These remain global utilities, never a third top-level reader audience.

| Service | Intended behavior |
| --- | --- |
| Search | Index each canonical document once per available language projection. Show primary and additional audience labels and semantic authority separately. Offer an explicit audience filter including shared documents. Default to the active audience with a visible option to search all; direct contextless search starts at all. Hits carry a compatible active context, otherwise resolve to primary. Avoid duplicate hits caused by navigation membership. |
| Glossary | Preserve the integrated provider-owned terms, stable term identity, related terms, locale availability, and exact provenance. Keep current audience while consulting terms. Linked documents use normal context resolution. Do not fork glossaries by audience. |
| Source browser | Preserve the bounded exact-SHA Site/Composition/Policy snapshots and immutable source/line links. It is a service for either audience; uncataloged source views are not published-document claims. Direct contextless access uses a neutral utility shell. |
| Repository trees | Three generated canonical Site documents are primary Maintain > Repository inspection, also Use > Reference for consumers inspecting material provenance. Tree previews and source lines inherit context without acquiring new document identities. |
| Build provenance | Global utility showing exact Site and provider publication revisions; distinguish those from Site's independent Composition/Policy consumer pins. Preserve context or use a neutral shell without context. Machine JSON stays data; it receives no invented audience document identity. |
| Guided and localized views | Keep canonical identity, provider ordering/disclosure semantics, locale availability and provenance. Language and audience are independent state; a locale switch preserves supported audience membership. |

Search badges/filtering must not treat source ownership as reader classification.
The Policy PWA guide is currently provider-authored reader help for the site;
both audiences need it, but Policy must first clarify its product identity and
relationship to Site's canonical PWA implementation before Site projects it as
general help. Do not transfer its semantics by relabeling it.

## Publication gaps and content boundaries

Maintain requires Site's `MAINTENANCE.md`, `PUBLISHING.md`,
`PUBLICATION_STAGING.md`, `PUBLICATION_FRESHNESS.md`, `FRESHNESS.md`, `GLOSSARY.md`,
`LANGUAGE.md`, `PWA.md`, authority model, and CI performance contract. These are
existing canonical material, but absent from the active catalog. Publish them
only in a later Site session with suitable source-relative link handling.

Composition needs a provider maintenance entry point linking existing catalog,
Composer architecture, evaluation, publication, release descriptors, validation,
and current provider procedures. There is no dedicated maintainer guide in the
audited catalog; `AGENTS.md` is procedural routing, not a human overview. The
existing `release/README.md` is a candidate with installer/provider and consumer
bootstrap concerns to clarify under Composition ownership. The existing
`docs/release-guide.md` remains the consumer product release guide.

Policy's `CONTRIBUTING.md` and `docs/policy-maintainer-workflow.md` should become
discoverable canonical maintainer publications. ADR-0008/0009 exist but are absent
from the audited catalog and ADR index; Policy should reconcile their publication
and index exposure. Its runtime README, repository-policy rules and operational
skills remain authoritative source references; their visibility in Source is not
a reason to publish every file as a narrative page.

`GLOSSARY_INVENTORY.md` explicitly excludes itself from publication and contains
historical review material: retain Source-only access. Site's old local copies
of migrated Composition architecture/migration material are not candidates;
project the canonical Composition documents. Repository-tracked runtime ledgers
and detailed PR findings must not become audience architecture or published help.

Section overview pages may be generated Site navigation projections of matrix
memberships; they must not invent provider contracts to fill a sparse section.
The new audience architecture itself stays repository-tracked in this phase;
later Site work decides its publication as canonical Site architecture with the
same validation and link checks as other future candidates.
