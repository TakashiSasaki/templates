# Composition authority migration history

This document records the provenance of the authority migration that established `composition` as the canonical source for Skill/Webapp artifact semantics, reusable capabilities, lifecycle contracts, recipes, schemas, and the deterministic Composer.

It is historical context, not the operational guide. For current consumer behavior, use [Using Composition](../consumer-guide.md) and the [Composer reference](../reference/composer.md).

## Architecture foundation

[PR #265](https://github.com/TakashiSasaki/templates/pull/265) established the composition data model and machine-readable schemas. It separated `artifact.*`, `capability.*`, and `lifecycle.*` authorities; defined safe-path and file-ownership rules; introduced unresolved consumer intent and resolved lock contracts; and set semantic validation boundaries.

## Skill capability separation

[PR #266](https://github.com/TakashiSasaki/templates/pull/266) established the first closed production catalog, migrated Agent Skill semantics into `artifact.skill-core`, and extracted reusable runtime, CLI, MCP, MCP Apps, browser-interface, and service concerns into `capability.*` authorities.

See [Skill capability migration](pr2-skill-capabilities.md) for the detailed authority split and source snapshots.

## Webapp and lifecycle separation

[PR #267](https://github.com/TakashiSasaki/templates/pull/267) introduced `artifact.webapp-core` and extracted reusable lifecycle authorities for contract evolution, implementation evidence, release evidence, and release bundles. It also established deterministic generated contract-manifest ownership.

See [Webapp and lifecycle migration](pr3-webapp-lifecycle.md) for the detailed authority split and source snapshots.

## Deterministic Composer foundation

[PR #268](https://github.com/TakashiSasaki/templates/pull/268) added the first deterministic resolver/Composer and the public lifecycle shape:

```text
inspect -> plan -> apply -> validate
```

That initial implementation intentionally supported only initial composition and refused an existing lock rather than inventing update semantics. Later Composition work replaced that historical limitation with the current lock-v2 `initial` / `update` / `upgrade` and deterministic recovery model documented in the current consumer guide and Composer reference.

## Publication provider boundary

[PR #269](https://github.com/TakashiSasaki/templates/pull/269) established Composition as a publication provider with an explicit documentation catalog, guided index, glossary, machine-readable assets, and provider-specific publication validation. Skill and Webapp remained distinct artifact semantics inside the one `composition` provider rather than independent canonical publications.

## Site publication cutover

[PR #270](https://github.com/TakashiSasaki/templates/pull/270) moved Site publication to the Composition authority model. Site began locking one reviewed `composition` revision for Skill/Webapp artifact semantics, reusable capabilities, lifecycle contracts, recipes, schemas, Composer documentation, and related publication assets.

## Migration closure

[PR #272](https://github.com/TakashiSasaki/templates/pull/272) recorded the publication cutover as complete and established that the legacy `skill` and `webapp` branches were no longer source authorities or Site publication inputs.

The final legacy branch heads retained for provenance are:

- `skill`: `b8b735dbe525ca76316fec445cdce43db02a955e`;
- `webapp`: `fa269e1310a37ad46f3644ed4f46954a815380ec`.

Site subsequently recorded retirement readiness in [PR #275](https://github.com/TakashiSasaki/templates/pull/275) and completed legacy branch-ref retirement in [PR #277](https://github.com/TakashiSasaki/templates/pull/277). Historical provenance remains available through the archive refs; the deleted legacy branch refs are not operational dependencies.

## History boundary

The `composition` branch was created with independent orphan history. Legacy Skill and Webapp content was read as migration source material, but their branch histories were not merged, rebased, or cherry-picked into `composition`.

This record intentionally stops at authority migration and branch retirement. Current Composer lifecycle semantics, publication-protocol ownership, Policy coexistence, and other post-migration behavior belong to their present-tense canonical documentation rather than to this chronology.
