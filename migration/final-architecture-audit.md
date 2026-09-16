# Final authority separation audit

P9 (#901) landed at `6ca4e0ed49070855131bf353d4de6c119f12429f` and P10
(#902) at `a91a439a956f9f14b71bd1091f4394a118e77dbb`. This P11 candidate
removes the transitional paths after their callers moved to the Bundle renderer.
Deployment is a later, explicit action after final exact-head acceptance.

## Frozen adoption frontier

- Integration: `d2316a54db4011ba2936355065a86c80c2942c74`
- Composition: `c4a0c1085e80cec151aeed0eab653876d66c6896`
- Policy: `e8ee2bd1a4fad3dfbf60c25c8cb1de9b64b8b2ab`
- Bundle schema: 2
- Identity: `9a4d21438bd112ff4ae24bfe628a6461d5c5e60476ede08acda7d5316dc2161e`
- Content digest: `3091735d13cebf4c265f2ae8157189b2b542ac14c032d27674f841daebd9da7f`

Independent Integration qualification regenerated twice at this exact frontier and
matched the qualified release artifact's identity/content digest. Integration ran
without Site rendering/runtime. Its provider translations have 32 current, 2 stale
and 82 missing reader records. Site never advances their synchronization metadata.

## Reachability and removals

The canonical path is `site-producer.yml` → verified immutable acquisition →
`site_renderer.render` → Site HTML/runtime checks. External regeneration, only when
release artifact evidence is unavailable, calls the immutable Integration workflow.
It is not a Site provider producer. The renderer accepts no provider roots.

An AST import walk from workflow scripts plus renderer subprocess entry points found
83 reachable modules and zero Integration implementation imports. Dynamic Site-owned
translation metadata and public Website/PWA contract validation entry points were
also inspected. Physical isolation qualification checks the executable boundary.

Removed responsibilities include:

| Retired Site path | Current owner / replacement |
|---|---|
| `integration/`, `produce_publication_bundle.py`, `qualify_integration.py` | Independent Integration producer and qualification |
| `publication-sources.json`, resolver, provider promotion/staging helpers | Integration reviewed provider selection |
| `site-manifest.json`, publication staging, reader locale labels | Bundle destination/navigation models |
| v3/v4 assembly/catalog parsers, glossary/graph producers, provider translation compiler | Integration semantics and deterministic Bundle |
| Composition-specific tree/browser wrappers and provider Git collection entry points | Generic Site rendering of authenticated Bundle models |
| Provider/coexistence/freshness workflows and moving Composition browser diagnostics | Provider-native / Integration compatibility qualification |
| Separate mobile/search artifact replay and detailed provider profiling | Canonical exact-artifact browser/PWA DAG |
| Tracked duplicate discovery/reference JSON | Generated presentation from one Site template and public consumer state |
| Provider-pair runtime freshness and artifact identity aliases | Exact Site + Integration Bundle identity |

`publication_bundle/` now contains consumer wire/model/path helpers, not a Bundle
producer. Provider source identity and translation manifest closure stay upstream.
Site's own source browser and translation compiler are valid Site responsibilities;
`site_renderer/owned_content` explicitly rejects provider checkout namespaces.
Its stale Site translations retain their reviewed hashes and receive the warning UI.

## Test ownership

Tests of deleted provider catalogs, source producers, staging and historical
promotion implementations were retired with those implementations. They are not
silently counted as executed upstream. Integration's independent qualification
revalidates its current graph, manifest closure, source/preview, provenance and
determinism contracts. The precise removed path inventory is recorded in
`retired-site-paths.json` and the Git diff.

Site retains archive/run/head/attempt/upload-window/digest adversarial tests, consumer
inventory/closure tests, renderer isolation, source-view escaping/sandbox bounds,
generic graph/link rendering, audience/search/accessibility/mobile/browser/PWA tests.
New output-model fixtures replace producer-generated UI fixtures. Discovery union
tests require all remaining tests to be reached; skips do not count as acceptance.
Static current/stale/missing rendering and complete coverage failures are tested
before any HTML write. Browser checks cover reload, switching, history, offline,
worker updates and slow convergence of stale warnings.

## Historical findings

| Audit | Current disposition and evidence |
|---|---|
| #889 / SA01 authority layering | No actionable finding was reported. Provider semantic production is now absent from Site. Playground reads a provider-produced public projection. |
| #890 / DUP01 discovery copies | Resolved: `agent.json` and its schema have one checked-in source; build projects exact Bundle provenance. |
| #890 / DUP02 reference consumer copies | Resolved: public JSON is generated once; independent product/toolchain contracts remain Site consumer inputs. |
| #890 / DUP03 navigation/staging duplicates | Superseded by architecture: Integration owns navigation/staging; Site's old files are removed. |
| #890 / DUP04 and #880 / F02 v3/v4 assembly | Resolved: both Site semantic assembly entry points/parsers are removed. |
| #880 / F01 provider wrappers/order | Resolved: wrapper producers removed; source browser uses supplied Bundle model order and glossary uses stable generic sorting. |
| #859 Website worksheet concern | Site's installed public Composition consumer contracts describe its own Website product. No provider semantics are reconstructed. The old navigation-to-worksheet generator is removed; managed validators/consumer state remain untouched. |
| #812 historical PWA cache-miss behavior | Superseded by current PWA implementation and exact-head full acceptance on P9/P10. P11/final Site acceptance re-executes the same assertions before deployment. |

These historical PRs were already closed when inspected; no audit was closed merely
to clear this migration. New findings require current reachability evidence.

## Release safety

All four authority histories remain independent. Site's explicit lock may remain
unchanged while either providers or Integration advance. No upstream event deploys
Site. `deploy-pages.yml` is manual, restricted to `site`, and is the only workflow
with Pages write permission. The live `github-pages` environment allows exactly
`site`; the configured custom domain enforces HTTPS.

The deployment build now reaches the complete qualification DAG, including browser,
PWA and stale warnings, using one timestamped artifact shared by the consumers.
A failed or skipped required acceptance job prevents deployment. Final deployment
and live-reader evidence are recorded separately after the reviewed P11 candidate
lands; this document is not a claim that a provisional head has deployed.
