# Visible audience UX

This Site implementation consumes the reviewed architecture at
`af55c7dc0176dd24393b4296b43c8e31d6171a11` and the
[foundation contract](foundation-contract.md). It defines reader presentation;
Composition and Policy retain their independent semantic and publication authority.
Current stack revisions, qualification results and review state belong in the PR
Work ledger, not this document.

## Landing and global shell

The root always resolves neutral, including direct arrival, explicit query
parameters and reload with a stored journey. Its two primary links are **Use
templates** (use the supplied systems in another repository) and **Maintain
templates** (maintain this repository and its providers). Detailed destinations
remain below the choice in a disclosure. Japanese reader content has the same
structure.

The global shell displays the current journey text and two native buttons with
`aria-pressed`. It delegates all switching to `TemplatesAudienceContext`. Shared
documents keep their canonical route and fragment; single-audience documents use
the target overview. Where an overview has an actual published translation,
switching keeps that language. Otherwise the canonical overview is the fallback.

## Theme and navigation

CSS tokens consume only `html[data-audience]`: blue/cyan Use, amber/orange
Maintain and neutral unresolved/root. Reading backgrounds stay neutral. Labels,
pressed state, navigation markers, breadcrumbs and visible focus expose identity
without color; forced-color styles preserve controls. Slate appearance tokens
are defined for the existing theme's slate state.

The existing audience projection includes navigation trees produced from the
validated manifest, restricted to documents actually assembled. The shell
renders the selected tree and first matching breadcrumb. It consumes the existing
reader locale overlay for translated labels and supported routes. Provider index
content and disclosure meaning are preserved. Ordinary cross-audience document
links announce their destination audience before activation.

## Search and shared services

The search adapter integrates with the same open Shadow DOM contract as search
history. It classifies existing engine hits with primary/additional audiences and
independent authority labels. The explicit filter starts at the current journey,
or All audiences in a neutral shell; shared documents match both filters. The
adapter adds no index or document copies. Filtered keyboard selection excludes
hidden hits and preserves the existing search-history integration. Engine totals
continue to describe the underlying search query.

Final reader assembly records an exact `services` route inventory for generated
non-document HTML, excluding 404 and inline previews. These routes gain no
canonical document identities or primary audience. Their direct contextless
state is neutral; explicit or stored supported context is preserved by the same
controller. Unknown routes remain fail-neutral. Glossary, Source/file views and
index-guided views load the same shell. Their CSP permits only the same-origin
script/style/fetch capabilities needed by that shell, preserving other existing
restrictions. Provenance JSON remains machine data.

## Qualification and remaining publication work

`scripts/check_audience_runtime.py` qualifies visible UX in the same browser and
canonical artifact used by the foundation suite. It verifies exact Site/provider
provenance and source asset equality, records an artifact content digest, and
covers responsive navigation, theme contrast, native keyboard controls, focus,
forced colors, search classification/filtering/deduplication, locale and shared
services in addition to the foundation's history, instant-navigation and offline
checks. Existing canonical mobile/search/PWA freshness checks remain required
where applicable. No additional build or browser workflow is introduced.

The ten Site maintainer publication candidates remain deferred under the owning
Site rationale in [reconciliation](reconciliation.md). Their source visibility
is not canonical reader publication. This UX does not close Session 6 or claim
the entire audience migration complete. Final cross-authority closeout must bind
the landed UX Site revision and selected provider publications separately.
