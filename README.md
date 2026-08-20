# Composition

Composition is the canonical authority in `TakashiSasaki/templates` for reusable Skill and Web application artifact semantics, application capabilities, lifecycle contracts, recipes, schemas, and the deterministic Composer.

A consumer repository is produced from an artifact recipe plus explicit consumer intent. The Composer resolves a deterministic component closure, materializes source and generated files, records the resolved state in `.template-composition/lock.json`, and leaves the consumer repository self-contained.

## Start here

If you are creating or maintaining a concrete Agent Skill or Web application repository, start with [Using Composition](docs/consumer-guide.md). It provides the task-oriented `initial` / `update` / `upgrade` / recovery workflow, file-editing rules, and conflict handling.

For exact CLI options, inspect states, plan fields, ownership semantics, recovery rules, diagnostic codes, and exit behavior, use the [Composer reference](docs/reference/composer.md).

For architecture, provider-specific documentation, and machine-readable authority guides, use the [Composition documentation index](docs/index.md).

## Lifecycle at a glance

The public Composer workflow is:

```text
inspect -> plan -> apply -> validate
```

`initial` creates a newly managed repository from explicit consumer configuration. `update` preserves the normalized intent already recorded in the lock while reconciling to a descendant Composition source revision. `upgrade` accepts explicit new consumer intent and is required for compatibility-boundary changes such as component-version changes. Interrupted managed mutation is recovered by deterministic roll-forward from the durable transaction marker rather than by guessing or merging arbitrary local state.

Composition is deliberately fail-closed. Planning is read-only; mutation is preceded by a complete plan; local changes to Composition-owned bytes are not silently overwritten; and unsupported ownership or component transitions are rejected rather than inferred.

## Artifacts, capabilities, and lifecycle

The production catalog separates three kinds of reusable authority:

- `artifact.*` defines artifact-specific semantics such as `artifact.skill-core` and `artifact.webapp-core`;
- `capability.*` defines reusable runtime/interface/service behavior such as runtime, CLI, MCP, MCP Apps, browser, and headless-service capabilities; and
- `lifecycle.*` defines reusable composition-state, contract-evolution, implementation-evidence, release-evidence, and release-bundle behavior.

`recipes/skill.json` selects `artifact.skill-core`; application capabilities and product lifecycle components are opt-in. `recipes/webapp.json` selects `artifact.webapp-core`; its release lifecycle resolves transitively through `lifecycle.release-bundle`, while runtime and interface capabilities remain optional. A static/CDN Web application therefore does not acquire an application runtime merely because it is browser-facing.

Every artifact requires `lifecycle.composition-state`, which materializes the self-contained consumer validator and lock schema under `.template-composition/`.

See the [Composition model](docs/architecture/composition-model.md), [production catalog architecture](docs/architecture/catalog.md), and [generated contract manifest architecture](docs/architecture/generated-contract-manifest.md) for the detailed design.

## Ownership and safety model

Materialized files use explicit ownership modes:

- `managed` files remain Composition-owned and may change only through guarded managed-state reconciliation;
- `generated` files are recomputed deterministically from the resolved composition and remain Composition-owned; and
- `seed` files transfer to consumer ownership after initial materialization, so later consumer or Policy edits are preserved.

Consumer-time validation requires `managed` and `generated` files to match their lock digests. Active `seed` files must remain present but may differ from their original bytes after ownership transfer. File-owner or ownership-mode transitions are never guessed, component-version changes require explicit upgrade, and descriptor-byte changes without a component-version change are rejected as source invariant violations.

See the [Composer reference](docs/reference/composer.md) for the complete operational contract and [Composer architecture](docs/architecture/composer-mvp.md) for resolver, reconciliation, transaction, and recovery details.

## Authority boundaries

Coding-agent operating policy is a separate `policy` authority. Composition does not interpret Policy profiles, `.agent-policy.yml`, `.agent-policy.lock`, or `.agent-policy/**`, and the Composer never invokes the `agent-policy` CLI. Policy-owned metadata paths are foreign reserved destinations for Composition.

The Skill artifact materializes `AGENTS.md` as `seed`; after initial composition it is consumer-owned and can later be adopted or rewritten by Policy without giving Composition ownership of Policy state. The canonical cross-authority rules are maintained by Site in the [Policy–Composition coexistence contract](https://templates.moukaeritai.work/coexistence/).

Site is separately responsible for reader-facing information architecture, publication mapping, and the generic schema-v3 publication protocol. Composition owns its provider declarations and provider-specific validation, while Site locks and publishes an exact reviewed Composition revision. See the [publication boundary](docs/publication-catalog.md) for the provider contract.

## Maintainer references

The main deeper references are:

- [Composition documentation index](docs/index.md)
- [Composition model](docs/architecture/composition-model.md)
- [Production catalog architecture](docs/architecture/catalog.md)
- [Generated contract manifest](docs/architecture/generated-contract-manifest.md)
- [Composer architecture](docs/architecture/composer-mvp.md)
- [Production catalog guide](catalog/README.md)
- [Composition schema guide](schemas/README.md)

Historical migration provenance is intentionally separated from the current operational and architecture documentation. The reader-facing summary is [Composition authority migration history](docs/migrations/composition-authority-migration.md); stage-specific implementation notes remain repository-maintainer records rather than portal pages.
