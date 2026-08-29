# Documentation Site maintenance

This file applies to the `site` integration/deployment authority.

## Authority responsibilities

- `composition` owns canonical Agent Skill and Web application artifact semantics, reusable `capability.*` and `lifecycle.*` components, production recipes/schemas, the deterministic composer, provider-owned `docs/index.md`, publication catalog, and composition terminology.
- `policy` owns canonical coding-agent operating policy, the `agent-policy` toolchain, provider-owned `docs/index.md`, publication catalog, and Policy terminology.
- `site` owns reader information architecture, full-SHA provider locking, publication assembly, integrated glossary generation, repository views, guided navigation, freshness/PWA integration, generated-site validation, provenance, and the only Pages deployment workflow.

Provider histories remain independent. Publication does not merge, rebase, or cherry-pick those histories. The Site checks out exactly the revisions locked in `publication-sources.json`.

## Change process

1. Change canonical content on the provider that owns it.
2. Validate and review that provider pull request, including provider-local publication validation.
3. Merge the provider pull request and record the actual merge commit SHA.
4. Create the coordinated Site pull request from `site`.
5. Classify the provider diff, prepare exact provider/Composition checkouts, then advance the reviewed full-SHA lock and agent revision projections together with `scripts/advance_publication_source.py`. The tool compare-and-swaps against the expected current lock and writes `publication-sources.json` only after its projection preflight succeeds.
6. Update `site-manifest.json`, reader navigation/localization, translations, glossary integration, or Site prose only when the provider public-interface change requires those Site-owned semantic changes.
7. Run the complete Site build against the exact locked inputs before merging the Site pull request.

The external provider set is exactly `composition` and `policy`. Skill and Web application remain separate reader/artifact concepts but are not separate provider checkouts.

The deterministic cutover tool handles only the mechanical current-revision boundary: `publication-sources.json`, `agent.json`, and `assets/agent.json`. It does not infer reader IA, translation freshness, glossary semantics, or publication-catalog meaning. A failed expected-current check, checkout-identity check, release-descriptor preflight, or projection-target safety check must be corrected rather than bypassed with separate hand edits.

## Publication catalogs

Every publication root used by the assembler contains `docs/publication-catalog.json` using schema version 3. The catalog is an explicit allowlist, not a branch-wide copy rule.

A catalog contains:

- `schema_version: 3`;
- a non-empty `documents` array with stable IDs and safe Markdown source paths;
- optional explicit non-Markdown `assets`; and
- optional `glossary.source`.

Paths must be safe relative POSIX paths and must not use parent traversal, `.git` components, ambiguous Windows forms, or symlink traversal. Asset trees may not smuggle Markdown into the public boundary.

`scripts/publication_contract.py` is the Site-owned canonical implementation of the generic schema-v3 publication protocol. It is deliberately stdlib-only and is both importable and directly executable. `scripts/assemble_publications.py` delegates catalog parsing and declared-source validation to this module instead of maintaining a second implementation.

The shared protocol covers only generic JSON/schema/path/document/asset/glossary boundary rules. Provider-specific semantics remain with the provider: for example Composition Markdown classification, reader-material coverage, production artifact inventory, and Policy-specific translation or policy-content checks do not move into Site. When provider CI starts consuming the shared validator, it must execute the file from a reviewed full Site commit SHA rather than a mutable branch tip; this is a development/publication dependency, not a consumer-runtime dependency.

## Navigation manifest

`site-manifest.json` schema version 2 defines the canonical reader information architecture. Each leaf names one `publication`, `document`, and generated `destination`.

The canonical publications in the integrated navigation are:

- `site` for portal-authored pages and generated repository-tree pages;
- `composition` for Composition, Agent Skill, application-capability, Webapp, lifecycle, and migration documentation;
- `policy` for coding-agent Policy documentation.

A reader path such as `/skill/` or `/webapp/` is a Site-owned presentation path. It does not establish provider ownership.

## Glossary maintenance

`GLOSSARY.md` is the normative integrated glossary contract. Canonical provider terminology remains in the semantic owner's `docs/glossary.yml`.

The Composition glossary is intentionally strict JSON syntax stored in a `.yml` file. The Site integration test must parse those exact bytes through the normal PyYAML loader so that JSON-as-YAML compatibility is proven by the real integration path rather than assumed from provider-local validation.

The integrated glossary records provider, source path, and exact source revision. Related-term references may cross provider boundaries, for example Composition-owned `templates-skill-profile` and Policy-owned `templates-policy-profile`.

Build-time annotation remains the semantic-linking mechanism. `finalize_glossary_annotations.py` annotates eligible human-readable HTML after all normal/guided/translated pages exist and before final public-URL/link validation.

## Repository-tree publication preparation

`scripts/prepare_repository_tree_publication.py` creates a temporary Site publication root and adds exactly three generated document declarations:

- `repository-trees/index.md`;
- `repository-trees/composition.md`;
- `repository-trees/policy.md`.

The tool copies Site-owned documentation/assets without following symlinks, augments the temporary publication catalog and manifest, and never modifies canonical `docs/publication-catalog.json` or `site-manifest.json` in place.

The retired Skill/Webapp copyable-template pages are not generated. Consumer repositories are materialized by the Composition composer rather than represented as committed `template/` source subtrees.

## Complete repository-tree generation

Production builds run:

```sh
python scripts/generate_repository_trees_composition.py \
  --repository TakashiSasaki/templates \
  --site-root site-publication \
  --output-root build \
  --publication composition=composition-source \
  --publication policy=policy-source
```

The entrypoint reuses the established tracked-tree safety implementation: `git ls-tree` defines the inventory, symlinks and gitlinks are displayed but not followed, path text is escaped, immutable GitHub links use the exact checked-out full SHA, and untracked files are absent.

Inline preview generation uses `generate_repository_file_previews_composition.py` for the same provider pair and reads committed blob objects rather than mutable working-tree content.

## Static repository browser

The bounded `/files/` source browser covers:

1. `site`;
2. `composition`;
3. `policy`.

`scripts/generate_repository_browser.py` is the canonical Site-owned generator and defines that authority set directly. The current production workflow still reaches it through `generate_repository_browser_composition.py`, which is compatibility-only and must not redefine branch order, root-index semantics, or rendering behavior.

The browser never follows symlinks or gitlinks. Eligible strict UTF-8 text is rendered from exact Git blob IDs under size/content limits; other entries receive safe fallback views plus immutable source links.

## Index-guided navigation generation

Production guided navigation uses the provider order `composition`, then `policy`.

The Composition-era wrapper is used for all four stages:

```sh
python scripts/run_composition_navigation.py graph \
  --repository TakashiSasaki/templates \
  --output build/index-navigation.json \
  --provider composition=composition-source \
  --provider policy=policy-source

python scripts/run_composition_navigation.py locales \
  --graph build/index-navigation.json \
  --output build/index-navigation-locales.json \
  --provider composition=composition-source \
  --provider policy=policy-source

python scripts/run_composition_navigation.py viewer \
  --repository TakashiSasaki/templates \
  --graph build/index-navigation.json \
  --site-root site-publication \
  --output-root build/site \
  --provider composition=composition-source \
  --provider policy=policy-source

python scripts/run_composition_navigation.py locale-viewer \
  --repository TakashiSasaki/templates \
  --graph build/index-navigation.json \
  --locale-overlays build/index-navigation-locales.json \
  --translation-map build/translation-publication.json \
  --site-root site-publication \
  --output-root build/site \
  --pair-map build/guided-locale-publication.json \
  --provider composition=composition-source \
  --provider policy=policy-source

python scripts/finalize_site_metadata.py \
  --site-root build/site/guided \
  --canonical-url https://templates.moukaeritai.work/
```

Provider `docs/index.md` files remain the canonical progressive-disclosure semantics. The Site graph/viewers do not transfer that ownership to translations or reader IA.

For linked source files, fragment-free uncataloged regular-file targets resolve to the same immutable `/files/` snapshot. Uncataloged regular-file targets with any fragment use the exact full-SHA immutable GitHub source because the Site has no rendered-document fragment contract for those files.

## Source locking and workflow overrides

Normal builds resolve Composition and Policy from `publication-sources.json`. Each value is a lowercase full 40-character commit SHA. This file is the sole committed authority for the current external provider publication revisions.

For a reviewed cutover, `scripts/advance_publication_source.py` requires the old lock value through `--expected-current`, an exact target provider checkout, and an exact Composition checkout at the prospective Composition revision. It renders the prospective lock and machine-facing agent projection from committed provider bytes before mutation, updates both agent projections first, and replaces the source lock last. This ordering makes an interrupted operation fail closed rather than advancing the authority before its projections are prepared.

`composition_ref` and `policy_ref` workflow-call inputs are deliberate compatibility/review overrides. Empty inputs must resolve to the lock; they must never fall back to a pull-request merge ref or another mutable branch.

## Build order

The reusable build performs, in order:

1. Site checkout and provider-lock resolution;
2. exact Composition and Policy checkouts;
3. Site unit/integration tests;
4. temporary repository-tree publication preparation;
5. schema-v3 assembly and provider translations;
6. repository trees and inline previews;
7. strict Zensical build;
8. integrated glossary generation;
9. canonical/PWA metadata normalization;
10. static source browser;
11. guided graph/locales/viewers and guided metadata;
12. translation reader finalization;
13. build-time Glossary annotation;
14. public-URL, entry-point, provider-order, and generated-link validation;
15. build provenance; and
16. Pages-artifact upload.

Generated Markdown, integrated glossary files, browser pages, repository previews, guided graph/pages, and final HTML are build artifacts and are not committed.

## Provenance

`/build-provenance.json` records the exact built `site` commit plus Composition and Policy revisions. Freshness identity and Service Worker behavior remain governed by `FRESHNESS.md`.

## Deployment boundary

`.github/workflows/build-pages.yml` is build-only and read-only with respect to repository contents. `.github/workflows/deploy-pages.yml` is the only deployment route and runs only for a push to `site`.

The external `github-pages` environment must allow exactly the `site` branch. Pull requests cannot change this repository/environment setting. Do not broaden it to all branches and do not introduce a second deployment authority.
