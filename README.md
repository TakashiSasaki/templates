# Composition

Composition is the canonical authority in `TakashiSasaki/templates` for reusable Agent Skill, Website, and Web application artifact semantics, shared foundations, application capabilities, lifecycle contracts, recipes, schemas, and the deterministic Composer.

A consumer repository is produced from an artifact recipe plus explicit consumer intent. The Composer resolves a deterministic component closure, materializes source and generated files, records the resolved state in `.template-composition/lock.json`, and leaves the consumer repository self-contained.

## Start here

**Building a browser-facing product?** Start with [Choose Website or Web application](docs/guides/website-webapp-selection.md). Choose from product identity and caller-visible behavior: content/document discovery and navigation use the `website` recipe, while task/state/action-oriented browser products use `webapp`. Static generation, server rendering, client rendering, CDN hosting, runtime selection, and PWA technology do not decide the artifact type.

After choosing the artifact, follow the matching zero-to-one path:

- [Website product walkthrough](docs/guides/website-product-walkthrough.md) — create a content/document-oriented Website from a separate product repository through Composition lifecycle, Website contracts, implementation evidence, and browser proof without introducing Webapp-only surfaces or UI states.
- [Webapp product walkthrough](docs/guides/webapp-product-walkthrough.md) — create an interactive Web application from a separate product repository through installation, `composition.json`, `inspect -> plan -> apply -> validate`, ownership, implementation, product tests, and evidence.
- [Agent Skill first-use walkthrough](docs/guides/skill-first-use-walkthrough.md) — create a reusable Agent Skill without first learning the Composition architecture.

**Running an independent clean-room evaluation?** Start with [Evaluating Composition](docs/evaluation-guide.md). It is the canonical evaluator entry point for the formal protocol, scorecard guide, scorecard schema, and output sequence. This maintainer/evaluator path is separate from ordinary consumer onboarding and does not change the consumer bootstrap contract.

For maintaining an existing managed repository, updating/upgrading Composition, recovery, ownership, or conflict handling, use [Using Composition](docs/consumer-guide.md).

Normal consumers use the installable `skills/composition/` runner and do **not** clone `TakashiSasaki/templates` or any provider branch. CPython 3.11 through 3.14 is the supported local prerequisite; Git is not required for normal consumer execution. The runner selects an immutable full-SHA Composition revision, downloads that revision as a GitHub HTTPS archive into an OS temporary directory, verifies a source-file digest inventory, builds or reuses the exact validated Python runtime, invokes the Composer with the consumer repository as its target, and removes the source snapshot after the invocation. Composition authority maintainers can still use the direct reviewed-source-checkout entrypoint; Git remains an authority-maintenance prerequisite for that path.

The named runtime cache is intentionally persistent for performance, but normal source acquisition is disposable: a templates checkout is not consumer state and is not retained under the runner cache. Managed `update` / `upgrade` verifies old-to-new revision ancestry with GitHub's compare API when running from an archive snapshot and fails closed when ancestry cannot be established.

For exact CLI options, inspect states, plan fields, ownership semantics, recovery rules, diagnostic codes, and exit behavior, use the [Composer reference](docs/reference/composer.md).

For architecture, provider-specific documentation, and machine-readable authority guides, use the [Composition documentation index](docs/index.md).

## Lifecycle at a glance

The public Composer workflow is:

```text
inspect -> plan -> apply -> validate
```

`initial` creates a newly managed repository from explicit consumer configuration. `update` preserves the normalized intent already recorded in the lock while reconciling to a descendant Composition source revision. `upgrade` accepts explicit new consumer intent and is required for compatibility-boundary changes such as component-version changes. Interrupted managed mutation is recovered by deterministic roll-forward from the durable transaction marker rather than by guessing or merging arbitrary local state.

Composition is deliberately fail-closed. Planning is read-only; mutation is preceded by a complete plan; local changes to Composition-owned bytes are not silently overwritten; and unsupported ownership or component transitions are rejected rather than inferred.

## Foundations, artifacts, capabilities, and lifecycle

The production catalog separates four reusable component roles:

- `foundation.*` defines shared mandatory baseline semantics introduced transitively by an artifact. `foundation.web` owns the shared browser identity, generalized routes, and viewports consumed by both Website and Webapp artifacts.
- `artifact.*` defines what is being built: `artifact.skill-core`, `artifact.website-core`, or `artifact.webapp-core`. Each browser artifact owns its domain-specific contracts plus the evidence-target derivation and validator logic for those artifact-owned semantics.
- `capability.*` defines reusable optional behavior such as runtime, CLI, MCP, MCP Apps, PWA, standalone browser interfaces, and headless services.
- `lifecycle.*` defines reusable composition-state, contract-evolution, implementation-evidence, checkpoint, release-evidence, and release-bundle behavior. `lifecycle.implementation-evidence` owns the artifact-neutral evidence machinery that artifact and capability validators consume.

A recipe selects exactly one artifact. Foundation components are not direct consumer choices; they are resolved transitively from artifact dependencies. `recipes/skill.json` selects `artifact.skill-core`. `recipes/website.json` selects `artifact.website-core`, whose baseline adds Website page structure, document metadata, discovery, and Website-specific evidence on top of `foundation.web`. `recipes/webapp.json` selects `artifact.webapp-core`, whose baseline adds application-specific routes, surfaces, UI states, and Webapp evidence on top of the same shared foundation.

Browser delivery topology remains orthogonal to artifact identity. A statically generated documentation or publishing product can use `website` with no runtime capability. A CDN-hosted stateful SPA can use `webapp` with no runtime capability. `capability.pwa` may be selected by either Website or Webapp and does not change which artifact is being built. Runtime, interface, and release capabilities are likewise explicit independent choices.

Every artifact requires `lifecycle.composition-state`, which materializes the self-contained consumer validator and lock schema under `.template-composition/`.

See the [Composition model](docs/architecture/composition-model.md), [production catalog architecture](docs/architecture/catalog.md), and [generated contract manifest architecture](docs/architecture/generated-contract-manifest.md) for the detailed design.

## Material ownership and safety model

Each materialized file has one component owner and one ownership mode:

- Managed material (`managed`) remains Composition-owned and may change only through guarded managed-state reconciliation;
- Generated material (`generated`) is recomputed deterministically from the resolved composition and remains Composition-owned; and
- Seed material (`seed`) transfers to consumer ownership after initial materialization, so later consumer or Policy edits are preserved.

Consumer-time validation requires `managed` and `generated` files to match their lock digests. Active `seed` files must remain present but may differ from their original bytes after ownership transfer. Changes to a component owner or ownership mode are never guessed; component-version changes require explicit upgrade, and descriptor-byte changes without a component-version change are rejected as source invariant violations.

See the [Composer reference](docs/reference/composer.md) for the complete operational contract and [Composer architecture](docs/architecture/composer-mvp.md) for resolver, reconciliation, transaction, and recovery details.

## Authority boundaries

Coding-agent operating policy is a separate `policy` authority. Composition does not interpret Policy profiles, `.agent-policy.yml`, `.agent-policy.lock`, or `.agent-policy/**`, and the Composer never invokes the `agent-policy` CLI. Policy-owned metadata paths are foreign reserved destinations for Composition.

The Skill artifact materializes `AGENTS.md` as `seed`; after initial composition it is consumer-owned and can later be adopted or rewritten by Policy without giving Composition ownership of Policy state. The canonical cross-authority rules are maintained by Site in the [Policy–Composition coexistence contract](https://templates.moukaeritai.work/coexistence/).

Site is separately responsible for reader-facing information architecture, publication mapping, and the generic schema-v3 publication protocol. Composition owns its provider declarations and provider-specific validation, while Site locks and publishes an exact reviewed Composition revision. See the [publication boundary](docs/publication-catalog.md) for the provider contract.

## Composition authority maintainer references

Here, a **Composition authority maintainer** means someone changing or maintaining the `composition` authority itself in `TakashiSasaki/templates`—for example, the Composer, production catalog, schemas, architecture, or provider publication contract. It does not mean a maintainer of a consumer Agent Skill, Website, or Web application repository; consumer repository maintainers should start with [Using Composition](docs/consumer-guide.md) and the matching first-use walkthrough.

The main deeper references are:

- [Composition documentation index](docs/index.md)
- [Composition model](docs/architecture/composition-model.md)
- [Production catalog architecture](docs/architecture/catalog.md)
- [Generated contract manifest](docs/architecture/generated-contract-manifest.md)
- [Composer architecture](docs/architecture/composer-mvp.md)
- [Production catalog guide](catalog/README.md)
- [Composition schema guide](schemas/README.md)

Historical migration provenance is intentionally separated from the current operational and architecture documentation. The reader-facing summary is [Composition authority migration history](docs/migrations/composition-authority-migration.md); stage-specific implementation notes remain Composition authority maintenance records rather than portal pages.
