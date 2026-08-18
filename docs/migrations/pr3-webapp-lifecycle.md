# PR3 Webapp and lifecycle migration

## Purpose

PR3 migrates browser-specific Webapp semantics and extracts reusable product-lifecycle contracts into the production composition catalog.

This is an authority migration, not a branch-history merge.

## Source snapshots

- composition base after PR2: `fcdcbb9f0825f758743c74123d77c1068024b632`
- legacy Webapp source: `fa269e1310a37ad46f3644ed4f46954a815380ec`

The `webapp` branch remains unchanged by PR3.

## Artifact authority

`artifact.webapp-core` owns only Web-specific semantics:

- browser-facing surfaces and audiences;
- canonical routes/aliases/deep links/history intent;
- authentication/access-failure presentation;
- visible UI state vocabulary, recovery, announcements, and focus;
- responsive viewport lower bounds and input capabilities;
- Web-specific cross-contract invariants; and
- Web-specific implementation-evidence coverage.

The current legacy contract documents/schemas are migrated as exact Git blobs. Existing routes and UI-state version histories remain registered through v2 with their migration artifacts.

## Lifecycle authorities

PR3 introduces:

```text
lifecycle.contract-evolution
        ^
lifecycle.implementation-evidence
        ^
lifecycle.release-evidence
        ^
lifecycle.release-bundle
```

The arrows denote dependency direction toward the preceding layer. `artifact.webapp-core` requires `lifecycle.release-bundle`, thereby receiving the complete lifecycle chain transitively.

### Contract evolution

Owns the generic generated manifest format and validation of registry closure, schema/document binding, version histories, and migration inventory.

### Implementation evidence

The old Webapp-specific evidence target union is removed from the generic schema. Generic targets are now `contract-item` or `contract-transition`. Artifact-specific vocabulary and exact target coverage belong to artifact validators.

Template implementation evidence is empty. Product mode carries verified records, commands, and gates.

### Release evidence and bundle

The existing provider-neutral release document/schema shapes are retained as generic lifecycle contracts. New validators remove dependence on Webapp-specific validation modules while preserving exact-revision, command-digest, result/gate, chronology, and digest-closed handoff semantics.

## Generated manifest

The legacy static `contracts/manifest.json` is not copied. Every component registers its own contract metadata in `component.json`; `lifecycle.contract-evolution` uniquely owns the generated manifest destination.

Catalog tests implement deterministic rendering as executable specification for the later composer.

## Recipe changes

`webapp` becomes a production recipe over `artifact.webapp-core`; application capabilities remain optional.

The `skill` recipe also exposes lifecycle components as optional selections. Materialized tests run the same lifecycle validators in a Skill composition, demonstrating that the extracted lifecycle authorities no longer depend on Webapp semantics.

## Validation

PR3 production-catalog tests cover:

- exact source/catalog closure;
- dependency acyclicity;
- contract-registration global uniqueness and component ownership;
- unique generated-manifest ownership;
- deterministic manifest rendering;
- portable destination ownership for maximal Skill and Webapp selections;
- minimal and maximal Skill materialization; and
- Webapp materialization with Web-specific plus generic lifecycle validators.

## Deferred

PR3 does not implement the general resolver/composer, production composition locks, apply/update behavior, publication cutover, Site integration, or legacy branch retirement.
