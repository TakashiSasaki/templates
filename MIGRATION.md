# Historical P0 migration audit

This document records the pre-cutover audit. Its observations are historical, not
active build instructions. See [the final audit](migration/final-architecture-audit.md)
for current reachability and dispositions.

# Integration / Site migration contract

Status: P0 audit; independent Integration authority does not yet exist.

## Baseline and change contract

Audited Site: `d22657def1e706e07e9da80d3dcb0e91627ec39b`.
Composition HEAD: `ad7968581ff533225220c88fcfd7988483f52143`.
Policy HEAD: `41f0dd60b82847f3b93b6456e0ce70d70aa635e8`.
Reviewed publication inputs are Composition
`8c6c1884fa97f3ef1ec6c1aa7deba4ad38c9f4ff` and Policy
`6023af1b6aed4a22407d9ca43106cd66cfee9fb6`.
These publication identities are independent of Site's consumer/toolchain locks.
Refresh all identities before promotion or bootstrap.

The authorized first stack establishes an enforceable internal boundary, produces
a deterministic Publication Bundle, renders from that Bundle without provider
checkouts, and separates qualification. Preserve reader behavior and exact provider
selection. The only intentionally changed operational behavior is making deployment
explicitly dispatched. Do not deploy, advance locks, merge, create an Integration
branch, or claim final four-authority discovery in this stack.

The repository has no `contracts/repository-topology.json` declaration. Its authority
instructions, not the reusable Composition hub-and-orphan recipe, govern histories.
Never transfer authority history by merge, rebase, or cherry-pick.

## Intended ownership and active reachability

The canonical caller is `.github/workflows/site-producer.yml`; `build-pages.yml`
orchestrates it and acceptance. The exhaustive path inventory is
`migration/ownership.json`. Mixed modules are explicitly classified as ambiguous
pending the split below; that is a migration obligation, not permission to move all
of their behavior to one authority.

| Responsibility | Intended owner / boundary |
| --- | --- |
| Provider catalogs, generated-asset declarations, Composer and Policy semantics | Composition or Policy; consumed through their public contracts |
| Provider locks, staging, catalog closure, publication destinations, semantic audience/navigation membership | Integration |
| Provider translation manifests/content/synchronization metadata | Canonical provider; Integration derives availability |
| Translation link identities, localized graph data, integrated glossary | Integration data; Site renders chrome and warnings |
| Provider Git trees, bounded blob previews, canonical INDEX graph | Integration read models; Site renders trees, source pages and graph viewers |
| HTML, Zensical configuration, theme, CSS, search, audience shell, accessibility | Site |
| Site landing/runtime documentation and local public assets | Site fills Integration-declared destination slots |
| Site product worksheets and reference-consumer presentation | Site, using documented public consumer contracts; no provider resolver reconstruction |
| Provider freshness and cross-provider validation | Integration; candidate evidence does not adopt providers |
| Deployed-document freshness, service worker, PWA, Pages packaging/deployment | Site |
| Classifier, exact-input artifact transport and evidence verification | Shared mechanical contract utilities, with separate Integration/Site evidence identities |
| Local compatibility CLI aliases | Temporary migration compatibility; no independent semantic decisions |
| Policy configuration, generated policy and maintainer procedures | Policy semantics, Site consumer-owned selection/projection |

Integration must not import rendering/runtime code. Site's renderer must not import
Integration implementation, parse provider catalogs/manifests, access provider Git
objects, or accept provider checkout arguments. Shared wire contracts are versioned.
Site's own source views and Site-owned content remain downstream. Integration owns
semantic slot declarations; Site qualification checks their content closure.

## Historical finding dispositions at the audited head

- #880 F-01: confirmed reachable. Repository wrappers and navigation adapter enforce
  provider order. Move the data decisions to Integration and expose explicit records;
  preserve viewer behavior. Do not mechanically delete wrappers before callers move.
- #880 F-02 and #841 SA-03-001: the v3 CLI is active, including link rewriting.
  v4 is a generated-asset lifecycle contract, not evidence of a second complete
  renderer. Preserve both input versions where locked providers need them; consolidate
  orchestration at the Bundle producer. Reject blanket replacement solely by suffix.
- #859 SA-01-F01: Site worksheet projection is active. Projecting this Website's
  concrete routes into a public Composition contract is consumer implementation,
  not by itself a redefinition of Composition semantics. Destination selection moves
  upstream; Site retains product metadata and public-contract validation.
- #859 SA-01-F02: reject the proposed transfer of Site HTML metadata rendering to
  Composition. HTML metadata application belongs to Site under this migration.
- #839 SA-01-F01: reference-consumer projection is reachable and reads public
  declarations. Keep descriptive formatting in Site. Treat any reconstruction of
  provider resolution rules as a separate, evidence-backed defect, not an inference
  from the existence of a projection. No canonical provider state may be rewritten.

All four audit PRs remain open. At audit time each has a failing aggregate check,
no submitted review, no inline thread, no reviewer request and no reactions. Their
single ordinary comment is bot onboarding. None establishes migration acceptance.
Current Site native checks/deployment and current provider native CI have successful
runs; those are baseline observations, not acceptance of this migration.

## Bundle and qualification invariants

Bundle identity binds schema, exact producer/provider revisions, configuration and
content digests. Execution timestamps/run IDs/attempts are separate evidence. Use
safe bounded immutable content, exact inventories, collision checks and fail-closed
validation. Missing reusable evidence may regenerate; corrupt or misbound evidence
must fail. Reuse the existing artifact transport and qualification-frontier patterns.

Current translation coverage already distinguishes current/stale/missing and records
reviewed/current canonical blob identities. Reader publication currently skips stale
derivatives. Preserve that behavior through P4; available stale derivatives are P8.
Source previews already bound per-file/candidate/aggregate sizes; preserve those limits.

The mandatory isolation test runs Site with provider checkouts and Integration code
physically absent. Full migration acceptance compares generated reader output and
runs the applicable HTML/browser/PWA gates at a stable qualification frontier.
Provider candidate qualification terminates at the Bundle with no Pages artifact.

## Progression and handoff

S0 audit -> S1 boundary -> S2 Bundle -> S3 renderer -> S4 qualification.
Use predecessor PR branches as bases and continue construction while CI is pending.
After S4, request one cumulative Codex diagnostic review bound to the exact ordered
stack, then hand off without polling or merging. Human landing precedes P5 bootstrap.

Future P5 bootstraps an unrelated Integration history from Site's then-reviewed
provider locks. A changed producer revision changes overall Bundle identity; prove
provider payload equivalence separately and record bootstrap provenance. P6-C/P6-P
may run concurrently after prerequisites. P7 explicitly promotes exact merged inputs;
P8 permits structurally valid stale derivatives. Stop before P9–P11, Site adoption,
publication cutover or deployment unless separately authorized.

## S1 construction checkpoint

Catalog/materialization, glossary semantics and translation derivation now reside in
`integration/`. Existing script paths delegate to those implementations. Import
regressions prohibit Site dependencies in the Integration package and the reverse
edge in `site_renderer/`. Remaining mixed orchestration is migration compatibility
until the S2/S3 cutover; it is not an independent authority. The deployment regression
now enforces dispatch-only Site execution. Core construction validation: 1,368 tests
passed; focused Integration/translation/catalog/glossary validation: 73 tests passed.

## S2–S4 implementation checkpoint

The versioned `publication_bundle/` package is the shared wire contract, including
bounded provider source records. `integration/producer.py` owns semantic generation;
`site_renderer/` renders that output and fills only declared Site-owned content slots.
`publication_bundle/authority_content/` supplies reusable authority-local document and
translation contract helpers: Integration invokes these for providers, Site only for
its own source. Provider availability arrives already derived in the Bundle.

The canonical workflow now qualifies Integration in a separate job, uploads one
immutable Bundle, and consumes it in a renderer job with no provider checkouts.
`ci_artifacts/` generalizes existing Pages archive and attempt-window safeguards.
Its direct scheduled-artifact handoff verifies run/head/attempt, invocation name,
successful producing job, creation window, archive digest, exact Bundle producer and
provider revisions, all payload digests, model closure and provenance. It does not
introduce another cache or polling lane. Existing exact-input Pages reuse includes
the Bundle identity; absence may regenerate, invalid evidence fails closed.

Integration-only construction is classified by the existing base-authoritative CI
classifier. It schedules Integration qualification and requires its result at the
construction gate, without Site browser/PWA or Pages generation. CI-control or shared
contract changes still fail closed to full qualification. The current-provider
freshness diagnostic now uses Integration qualification exclusively. Direct provider
authority workflows remain unchanged pending P6; their existing Site compatibility
calls are transitional and do not establish the final upstream cadence yet.

`integration-qualification.yml` may be invoked with exact Composition and/or Policy
candidate overrides; omitted companions use the reviewed lock. It generates twice,
validates all Bundle models and requires deterministic regeneration. A green result
is compatibility evidence only. Promotion, reviewed release, Site adoption and
deployment are separate actions; none is performed here. The existing Policy
construction/qualification frontier and evidence applicability rules remain in use.

Local `run_site_preflight.py cross` now uses the same producer/renderer boundary.
The full Site qualification DAG remains for explicit migration/adoption validation;
normal Integration qualification ends before it. Legacy CLI orchestration remains
migration compatibility until P5/P9/P11 retirement, not a competing canonical build.
