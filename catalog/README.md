# Production composition catalog

`catalog.json` is the closed inventory of production component and recipe authorities available from this `composition` revision.

Every component ID resolves to `components/<component-id>/component.json`; every recipe ID resolves to `recipes/<recipe-id>.json`. Catalog arrays are unique and lexically ordered, and validation requires exact agreement with the physical authority directories/files.

## Consumer selection guide

Choose the recipe from the artifact you are building, not from the language, framework, or deployment platform.

| You are building | Recipe | Base material and behavior | Lifecycle baseline |
| --- | --- | --- | --- |
| An Agent Skill repository | `skill` | Skill structure including `SKILL.md`, development guidance, and Skill-specific validation | `lifecycle.composition-state` only; application capabilities and contract/release lifecycle components are opt-in |
| A browser-facing Web application repository | `webapp` | Routes, surfaces, visible UI states, viewports, Web-specific validation, and framework-neutral browser application structure | `lifecycle.composition-state` + implementation evidence + contract evolution; the release lifecycle is opt-in through `lifecycle.release-bundle` |

Select optional application capabilities according to externally visible behavior. Include the capability you need directly; the Composer resolves its dependencies transitively.

| Need | Include | Automatically adds | What it contributes |
| --- | --- | --- | --- |
| A maintained implementation runtime, dependency/distribution rules, commands, environment, or deployment lifecycle | `capability.runtime` | — | Runtime selection and maintenance contract |
| A packaged command-line interface | `capability.cli` | `capability.runtime` | Caller-visible CLI contract |
| An MCP protocol endpoint/interface | `capability.mcp` | `capability.runtime` | MCP protocol, transport, client, security, and semantic-equivalence contract |
| An MCP Apps extension UI | `capability.mcp-apps` | `capability.mcp` and therefore `capability.runtime` | MCP Apps resources, bridge, visibility, sandbox, and fallback contract |
| An independently reachable non-browser service | `capability.service` | `capability.runtime` | Service interface contract |
| A standalone browser-facing interface backed by an application runtime | `capability.web-interface` | `capability.runtime` | Web interface, routing, security, health, and failure-isolation contract |

A browser-facing artifact does **not** imply `capability.runtime` or `capability.web-interface`. For example, a static/CDN Webapp can use the `webapp` recipe with no optional components. Add runtime-bound capabilities only when the product actually exposes those behaviors.

Lifecycle components are selected according to the product workflow. The `skill` recipe exposes each lifecycle level independently. The `webapp` recipe already includes contract evolution and implementation evidence in its baseline, and exposes `lifecycle.release-bundle` as the one top-level release choice. Choose the highest-level lifecycle behavior exposed by the recipe; prerequisites are resolved automatically:

| Need | Include | Dependency closure |
| --- | --- | --- |
| Versioned contract evolution and migrations | `lifecycle.contract-evolution` (`skill`) | contract evolution only |
| Implementation boundaries, proofs, authoritative commands, and release gates | `lifecycle.implementation-evidence` (`skill`; Webapp baseline) | implementation evidence -> contract evolution |
| Product-owned fixed-argv release execution and candidate verification | `lifecycle.release-execution` (`skill`) | release execution -> implementation evidence -> contract evolution |
| Revision-bound release evidence production | `lifecycle.release-evidence` (`skill`) | release evidence -> release execution -> implementation evidence -> contract evolution |
| Deterministic release bundle and one-command release orchestration | `lifecycle.release-bundle` (`skill` or `webapp`) | release bundle -> release evidence -> release execution -> implementation evidence -> contract evolution |

A minimal static Webapp therefore uses an empty include list and receives browser contracts plus implementation-evidence/contract-evolution support, but no release execution/evidence/bundle materials:

```json
{
  "schema_version": 1,
  "recipe": "webapp",
  "components": {"include": [], "exclude": []},
  "parameters": {}
}
```

A release-ready Webapp selects only the top-level release component:

```json
{
  "schema_version": 1,
  "recipe": "webapp",
  "components": {
    "include": ["lifecycle.release-bundle"],
    "exclude": []
  },
  "parameters": {}
}
```

A runtime-backed Webapp that does not use the Composition release lifecycle can instead select runtime independently:

```json
{
  "schema_version": 1,
  "recipe": "webapp",
  "components": {
    "include": ["capability.runtime"],
    "exclude": []
  },
  "parameters": {}
}
```

A Skill that exposes an MCP Apps UI and uses the complete release workflow can request only the two top-level choices; the resolver adds their prerequisites:

```json
{
  "schema_version": 1,
  "recipe": "skill",
  "components": {
    "include": ["capability.mcp-apps", "lifecycle.release-bundle"],
    "exclude": []
  },
  "parameters": {}
}
```

### Upgrading Webapp v3 to v4

`artifact.webapp-core` v4 changes the artifact dependency closure, so an existing managed Webapp at v3 crosses an explicit component-version compatibility boundary and must use `upgrade`, not ordinary `update`.

If the repository should keep the complete release lifecycle that v3 selected transitively, the v4 upgrade configuration must explicitly include `lifecycle.release-bundle`. If release execution/evidence/bundle behavior is not needed, omit it and review the upgrade plan before apply.

The v3 release contract files were `seed` material, so an upgrade that deselects the release lifecycle preserves their consumer-owned bytes rather than deleting them. After apply, any preserved `contracts/release-execution.json`, `contracts/release-evidence.json`, or `contracts/release-bundle.json` is no longer registered by the v4 baseline. The contract registry is intentionally closed, so validation fails until the consumer either archives those files outside `contracts/` (for example under `release-history/`) or deletes them after deciding the historical bytes are no longer needed. This cleanup is consumer-owned: perform it after the upgrade apply, then rerun `validate`.

Deselected lifecycle files do not select validators merely because similarly named files remain in the repository; the resolved component set in `.template-composition/lock.json` is the selection authority. The cleanup requirement above comes from the closed contract-document inventory, not from release-validator dispatch.

Use `plan` before `apply` to inspect the exact resolved component closure and materialized file actions. The recipe descriptors remain the machine-readable source of truth for which direct selections are permitted.

## Closure rules

Production catalog validation establishes:

- descriptor/recipe/schema validity;
- exact component source-file declaration;
- dependency/conflict target existence and dependency acyclicity;
- generic capability/lifecycle independence from artifact-specific authorities;
- recipe reference validity and disjoint required/default/optional selections;
- global uniqueness of registered contract IDs, document paths, and schema paths;
- component ownership of every registered contract document/schema/migration;
- a unique generated owner for `contracts/manifest.json`;
- deterministic manifest rendering from resolved `contract_registrations`;
- every resolvable production component owns at least one materialized file, because the composition lock requires every resolved component to have a file-ownership witness;
- portable single-owner material destinations; and
- successful materialized validation for production Skill and Webapp compositions.

The catalog is source authority, not consumer material and not an execution-hook registry.

The composer validates this closed source graph, resolves a recipe plus consumer configuration against one exact clean Git revision, and writes the resulting component/file closure to `.template-composition/lock.json` after successful initial materialization. Generated materials are dispatched only through allowlisted declarative generator IDs.

For an unmanaged target, initial composition refuses a pre-existing composition lock rather than inferring a managed-state transition. Existing managed repositories instead use explicit operations: `update` preserves the normalized intent recorded by lock schema v2 while advancing to a descendant Composition source revision, and `upgrade` accepts an explicit new configuration for changes such as recipe, component selection, parameters, or component versions. Neither operation is a general-purpose merge engine: locally modified `managed`/`generated` material and owner/ownership-mode transitions fail closed rather than being overwritten or inferred.
