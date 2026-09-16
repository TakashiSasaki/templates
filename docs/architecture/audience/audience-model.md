# Audience model

> **Historical design record:** This pre-cutover design records the audience migration.
> The current public destination/semantic navigation authority is Integration's selected
> Publication Bundle. Site owns its audience UI and rendering. References below to
> a Site manifest or Site-owned integration describe the historical implementation.


## Purpose and vocabulary

The audience axis separates the repository in which the reader intends to act.
It prevents consumer work from requiring an understanding of the publication
system, while giving repository maintainers a coherent operational journey.

| Identifier | Reader label | Primary task |
| --- | --- | --- |
| `use` | Use templates | Use the systems supplied here in another repository: choose and implement a product, adopt Policy, operate Composer, select capabilities, implement lifecycle contracts, migrate contracts, or consult technical reference. |
| `maintain` | Maintain templates | Maintain or evolve `TakashiSasaki/templates`, its Composition or Policy providers, authority integration, publication, self-hosting, CI, release system, or repository architecture. |

This is **not beginner versus advanced**. Maintaining a consumer product is
`use`. Composer reference, schemas, product release evidence, and Webapp
validation contracts remain Use material even when technically demanding.
Maintaining the Composer implementation or releasing the Policy toolchain is
`maintain`. A document's title, directory, or use of "maintenance", "architecture",
"release", or "validation" cannot decide its audience alone.

The audited Composition consumer guide already makes this consumer/authority
maintainer distinction. Its product release guide is Use material; its evaluation
guide is explicitly for authority maintainers and independent evaluators.

## Authority and audience are independent

**Authority asks: Who owns the meaning of this information?**
**Audience asks: In which reader journey should it be encountered?**

Composition owns Composition semantics, including artifact/component contracts,
Composer, catalogs, schemas, and its provider release procedures. Policy owns
Policy semantics, including application, authorship, compiler, release, and
maintenance procedures. Site owns reader IA, audience projection, and publication
integration under the [repository authority model](../../authority-model.md).
Site does not become a semantic super-authority by classifying provider pages.

Provider catalog IDs, source paths, semantic roles, and publication allowlists
remain provider-owned. Providers MUST NOT be required to encode Site navigation
labels, colors, portal paths, or audience memberships in their catalogs. A later
provider session can clarify mixed semantic roles or expose canonical maintenance
material; Site then projects the reviewed provider revision. No provider histories
are merged, rebased, or cherry-picked across authority boundaries.

## Identity and membership

Every canonical published document MUST have exactly one primary audience and
zero or more distinct additional audiences drawn from `{use, maintain}`. The
primary audience MUST NOT also occur in the additional list. An empty additional
list means single-audience relevance, not lower importance.

Identity remains `authority:document-id`, bound to the selected source revision
for publication provenance. A generated destination is its canonical published
route; labels, locale projections, and audience context are independent of that
identity. One canonical document may have multiple navigation memberships within
one journey or across both journeys. There MUST NOT be parallel Use/Maintain
copies of its content, search identity, or canonical link.

Each declared audience MUST have at least one target membership. Membership order
selects a deterministic default breadcrumb within that audience. An explicit
navigation membership may select a more specific breadcrumb without changing the
document identity. A technical architecture document may be primary Use under
Reference and additional Maintain under Authorities > Composition.

## Context resolution

Audience context is semantic navigation state, scoped to the current reading
journey, not inferred from arbitrary URL substrings or document filenames.
Future Site implementation MUST implement the following resolution order:

1. On the root landing route, render the neutral shell; do not silently redirect
   into a previously selected audience. The landing's inventory classification
   does not select its theme.
2. For a document, honor an explicit supported audience carried by navigation,
   an audience switch, or a recognized context parameter if the document belongs
   to that audience.
3. Otherwise preserve the existing journey context if the document belongs to it.
4. Otherwise choose the document's primary audience. Invalid/unsupported context
   is ignored, never a third audience or an authorization signal.

With no explicit or existing context, a direct/deep link therefore chooses the
primary audience. An absent or invalid membership selection chooses the first
membership for the resolved audience. Fragments select content, not audience.
Reload and browser back/forward MUST restore a valid recorded navigation context;
when unavailable, apply the same primary fallback. The representation of context
(history state, a validated parameter, or equivalent) is a later Site decision.
Canonical URLs and canonical tags MUST remain independent of that representation.

| Document membership | Arrival | Resolved audience |
| --- | --- | --- |
| Use only | Any context or direct access | Use |
| Maintain only | Any context or direct access | Maintain |
| Both, primary Use | Direct/deep link without context | Use |
| Both, primary Maintain | Direct/deep link without context | Maintain |
| Both | Navigation from Use | Use |
| Both | Navigation from Maintain | Maintain |
| Both | Explicit switch | Selected audience, same canonical document and fragment |
| Single audience | Switch to the other audience | Other journey's overview; do not misclassify the document |

Cross-audience links MUST identify the destination audience before activation.
On arrival, the label, navigation, breadcrumb, and theme update together. Merely
consulting a shared service (Search, Glossary, Source) preserves valid context.
Entering a document from a service uses the same resolver; it cannot accidentally
turn a Use-only document into Maintain material.

## Theme and accessible presentation

The root landing is neutral. Use uses a blue/cyan semantic theme; Maintain uses
an amber/orange semantic theme. Exact colors and CSS are outside this design.
Theme selection MUST derive from the resolved semantic audience, with a neutral
shell state for the landing and contextless shared services. Neutral is not an
audience enum value and cannot classify a canonical document.

Color MUST NOT be the sole distinction. The Site MUST expose explicit audience
labels, an accessible audience switcher, selected navigation state, meaningful
breadcrumbs, and audience classification in search results. Keyboard access,
visible focus, readable contrast, responsive layouts, and assistive-technology
state must preserve the distinction without relying on hue. A switch must be
understandable before activation and must not discard the reader's fragment on
a shared document. Scattered CSS path tests or hard-coded document-name themes
are nonconformant.

## Non-goals of this architecture formalization

- No final landing-page redesign or final theme implementation.
- No production migration of `site-manifest.json` or active two-portal navigation.
- No Composition provider implementation changes.
- No Policy provider implementation changes.
- No duplicate audience-specific copies of canonical documents.
- No generic metadata platform, universal retrospective semantic-role taxonomy,
  new provider runtime dependency, or authority-history mixing.
- No inference of deployment, release, review, or merge acceptance from this
  design inventory. Audit revisions describe evidence, not future qualified pins.
