# Audience foundation contract

## Session 4 scope

Session 4 supplies the semantic foundation for **Use templates** and **Maintain
templates**: active Policy maintainer publication, manifest schema v3, canonical
membership and navigation, assembly compatibility, audience context and browser
lifecycle integration. It does not establish a complete Maintain portal or a
finished audience interface.

| Member | Responsibility |
| --- | --- |
| [S4.1 #860](https://github.com/TakashiSasaki/templates/pull/860) | Promote the four Policy maintainer documents, their exact publication lock, navigation, generated projections and Website contract evidence. |
| [S4.2 #861](https://github.com/TakashiSasaki/templates/pull/861) | Closed schema v3 audience taxonomy, unique inventory, bidirectional navigation coverage, staging and locale compatibility, Website projections. |
| [S4.3 #862](https://github.com/TakashiSasaki/templates/pull/862) | Context resolution, one manifest-derived audience runtime projection, browser and instant-navigation integration, history, switching and reconciliation. |
| [S4.4 #863](https://github.com/TakashiSasaki/templates/pull/863) | Assembled-browser regression qualification and this durable foundation handoff. |

The logical ancestry is `site → #860 → #861 → #862 → #863`. Current exact heads,
base relationships, CI, review dispositions and next actions belong in the
[canonical Work ledger](https://github.com/TakashiSasaki/templates/pull/863#issuecomment-5673221687),
not in a tracked runtime session log. Successful qualification does not authorize
merge or substitute for independent exact-head review.

## Publication and design bindings

`publication-sources.json` selects the immutable provider content that Site builds.
`agent.json` and `assets/agent.json` project those same publication revisions.

| Provider | Site-selected publication revision |
| --- | --- |
| Composition | `8c6c1884fa97f3ef1ec6c1aa7deba4ad38c9f4ff` |
| Policy | `6023af1b6aed4a22407d9ca43106cd66cfee9fb6` |

Provider authority branch HEADs may advance independently. Their current values
and drift/compatibility evidence are recorded in the Work ledger. Branch movement
alone does not require publication promotion. Publication locks also remain
independent of Site's Composition product-consumer and Policy maintenance-consumer
pins in `reference-consumer.json` and their respective configurations.

The accepted Session 1 architecture revision is
`af55c7dc0176dd24393b4296b43c8e31d6171a11`. The matrix's Composition revision
`0f0c4012818a3b8646ad89fbca7db22c71ad5dd8` identifies its historical design audit;
it is **not** the Composition revision assembled by this foundation. Preserve
the matrix's historical evidence instead of changing production locks to match it.

## Foundation invariants

- The audience taxonomy is exactly `["use", "maintain"]`, in that order.
  Neutral is a shell state, not a document audience.
- Each of the 127 canonical manifest documents has a unique provider/document key
  and destination, one primary audience and distinct additional memberships.
  Every declared audience membership must appear in its navigation tree; every
  navigation reference must have that membership. Loading fails closed otherwise.
- Schema v2 compatibility and legacy `(home, navigation)` tuple unpacking remain
  available. Audience memberships do not create duplicate canonical content,
  translations or search identities.
- Assembly regenerates `audience-runtime.json` from the effective manifest.
  Published translation routes alias canonical records in that same projection.
  Python owns the projection; browser code consumes membership and public overview
  URLs without duplicating provider meaning or using the audit matrix as runtime data.
- Root arrival is neutral. A valid explicit audience takes precedence, then valid
  recorded journey context, then document primary audience. Shared services retain
  context. A failed or invalid projection does not fabricate Use membership.
- The registered controller updates `data-audience`, session context and
  `templates:audience-changed` on Zensical `document$`, back/forward and page-show
  transitions. Initialization is idempotent and stale asynchronous work is ignored.
- Namespaced history context survives Zensical's scroll-state replacements.
  Switching shared documents keeps the document and fragment; single-audience
  switches use the other journey's overview. Canonical tags remain context-free.
- The controller and runtime map participate in the existing static Service Worker
  contract. One controller fetch serves the document lifetime; subsequent page
  lifetimes revalidate through the existing cache/freshness behavior.

See [reconciliation](reconciliation.md) for candidate dispositions, history
representation, publication mapping and runtime behavior. The ten Site maintainer
publication candidates remain explicitly deferred to their own publication change.

## Qualification contract

Qualify the exact current heads and provider inputs, not historical CI or a
construction candidate. The current Site workflows govern required gates. Local
checks, remote CI, browser artifacts and independent review are separate evidence
layers, with current results and immutable run links in the Work ledger.

`scripts/check_audience_runtime.py` runs against the assembled Pages artifact and
records its `build-provenance.json`. It checks manifest/projection parity,
controller inclusion, direct links for both single and shared memberships, neutral
landing, unsupported explicit context, actual instant navigation, back/forward,
fragment-preserving switches, repeated initialization/events, one runtime fetch,
translated deep links, invalid-map fallback and offline reload. The canonical
build workflow runs it alongside existing browser/PWA checks. This is semantic
foundation regression coverage; visual audience design remains separate.

Also retain manifest, context, inventory, publication assembly/staging,
reader-navigation/locales, Website contracts, core tests, static build,
public-URL/link validation, provider coexistence, freshness, reference-consumer
and affected cross-authority qualification. No pending/skipped/unobserved check
is represented as a pass.

## Session boundary and human handoff

**Session 5 has not started.** The future session may consume the semantic state
and events, but this stack does not implement blue/cyan or amber/orange themes,
visual tokens, redesigned neutral landing cards, a final switcher, search audience
badges/filtering, or presentation-oriented breadcrumbs.

The one Session 4 whole-stack Codex review on #863 is the diagnostic finding
source. Do not request another whole-stack review as part of this remediation.
Its historical result is not exact-current-head member acceptance. Leave the PRs
open and unmerged for human handoff; any later merge requires the repository's
current review/acceptance gates and explicit human merge authorization.
