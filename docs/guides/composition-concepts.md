# Composition concepts for first-time readers

This page is an **explanatory guide**, not a second semantic authority. It is for readers who can follow a task-oriented walkthrough but want a compact mental model for repository-specific uses of words such as *recipe*, *artifact*, *component*, *contract*, *material*, and *lock*.

Canonical repository terminology remains in `docs/glossary.yml`. Exact Composition semantics remain in the component descriptors, recipes, schemas, and [Composition model](../architecture/composition-model.md). Operational behavior remains in the [Composer reference](../reference/composer.md). If this page ever disagrees with those authorities, follow the authority and fix this page.

You do **not** need to read this page before creating a Web application or Agent Skill. The first-use walkthroughs remain the primary zero-to-one paths.

## Mental model

Composition starts from the kind of artifact you want to build and explicit consumer intent. It resolves reusable authorities, then materializes their declared files into a separate consumer repository.

```text
what you want to build
        |
        v
      recipe  +  consumer intent
        |
        v
resolved component closure
   |          |          |
   v          v          v
artifact   capability  lifecycle
component  components  components
        \      |      /
         \     |     /
          v    v    v
            Composer
               |
               v
       consumer repository
       |- contracts/
       |- schemas/
       |- ordinary product files
       `- .template-composition/
```

The important distinction is between **selection**, **semantics**, and **materialization**:

- a **recipe** is the consumer-facing starting selection;
- **components** are the reusable source authorities selected directly or transitively;
- components may register **contract documents** and schemas or materialize other files;
- the **Composer** resolves the complete component closure and materializes it;
- the **Composition lock** records the exact resolved state after successful materialization.

## Common words with Composition-specific usage

| Word | Do not assume | How to read it here |
| --- | --- | --- |
| **Recipe** | a sequence of CLI steps or tutorial instructions | A starting selection that chooses exactly one artifact component and defines which reusable capability or lifecycle components are required, defaulted, or selectable. The walkthrough is the procedure; the recipe is selection authority. |
| **Artifact** | one generated file | The kind of produced thing whose identity-specific semantics are being defined. Current production recipes create an Agent Skill or a Web application. |
| **Artifact component** | the finished product itself | The Composition component that owns artifact-specific reusable semantics. `artifact.skill-core` and `artifact.webapp-core` are current examples. |
| **Component** | a visual UI widget or package dependency | A closed reusable Composition source authority. Component descriptors declare dependencies, conflicts, materialized destinations, ownership modes, and optional contract registrations. |
| **Capability component** | a property automatically implied by the artifact | An optional artifact-neutral behavior such as runtime, packaged CLI, MCP, MCP Apps, standalone browser interface, or headless service. Select it only when the product actually exposes that behavior. |
| **Lifecycle component** | a chronological project phase | Reusable product-lifecycle machinery such as Composition state, contract evolution, implementation evidence, lifecycle checkpoints, or release behavior. |
| **Contract** | only an HTTP/API contract | In Composition documentation, concrete selected components can register machine-readable contract documents and schemas for artifact or lifecycle behavior. The exact meaning belongs to the registered contract and its owning component; there is no single generic `contract.json`. |
| **Material** | an abstract design input | A file destination materialized into the consumer repository by a resolved component. Each destination has exactly one component owner and one ownership mode. |
| **Seed material** | immutable template output | Initial content whose byte ownership transfers to the consumer after materialization. The file remains required while selected, but consumer edits may diverge from the initial digest. |
| **Managed / generated material** | files the consumer may freely replace | Composition-controlled bytes. Consumer-time validation requires them to continue matching the resolved lock state. |
| **Composition lock** | a mutex or process lock | `.template-composition/lock.json`, the deterministic record of the exact source revision, normalized intent, resolved components, ownership, and material digests. |

### Artifact component is not Artifact contract

These are deliberately different concepts.

- **Artifact component** is a Composition authority class: it owns reusable semantics specific to the kind of artifact being produced.
- **Artifact contract** is a repository-wide Policy-owned classification for requirements that define what a produced artifact must contain or do.

The integrated glossary is the canonical place to disambiguate these terms. Composition must not create a second definition of the Policy-owned `Artifact contract` merely because the words are similar.

## Example: minimal Web application

A minimal static browser application can start with the `webapp` recipe and no optional components:

```json
{
  "schema_version": 1,
  "recipe": "webapp",
  "components": {
    "include": [],
    "exclude": []
  },
  "parameters": {}
}
```

The recipe selects `artifact.webapp-core` plus its baseline lifecycle dependencies. The Webapp artifact component supplies browser-specific contract families such as routes, surfaces, UI states, and viewports. After materialization, the consumer repository receives editable seed contract documents such as:

```text
contracts/routes.json
contracts/surfaces.json
contracts/ui-states.json
contracts/viewports.json
```

Those files describe the product you are building; they are not a complete implementation. Product code, framework choice, storage, tests, and other consumer-owned files are implemented separately.

If the product later needs a maintained implementation runtime, a packaged CLI, MCP, a service, or the complete release lifecycle, include the appropriate top-level capability or lifecycle component. The Composer resolves transitive requirements rather than requiring the consumer to enumerate every prerequisite.

## Example: Agent Skill

The `skill` recipe selects `artifact.skill-core`. Its initial material includes the Skill structure and validation needed to begin a separate consumer repository. Application capabilities and most product lifecycle machinery remain opt-in rather than being implied by the fact that the artifact is a Skill.

For example, an instruction-only or knowledge-augmented Skill does not need an application runtime merely because other Skills may expose CLI, MCP, or service behavior.

## Where to go next

- To build a Web application now, use the [Webapp product walkthrough](webapp-product-walkthrough.md).
- To build an Agent Skill now, use the [Agent Skill first-use walkthrough](skill-first-use-walkthrough.md).
- To choose optional components, use the [production catalog guide](../../catalog/README.md).
- For strict semantics and ownership rules, use the [Composition model](../architecture/composition-model.md).
- For exact commands and diagnostics, use the [Composer reference](../reference/composer.md).
- For canonical repository terminology and cross-authority disambiguation, use the integrated glossary generated from provider-owned `docs/glossary.yml` sources.


## Component roles: a practical mental model

A **recipe** is the consumer-facing starting point. It chooses an **artifact component**—the answer to “what am I building?”—and exposes only optional components that a consumer may deliberately select. A **component** is the reusable authority that contributes one coherent set of semantics and materials to that resolved product.

Read component roles as four questions, in this order:

1. **Foundation — What shared base is required?** A foundation is automatically introduced through an artifact dependency. It is mandatory when the artifact needs it, but it is not a product capability to select directly.
2. **Artifact — What am I building?** An artifact defines the product identity and its identity-specific contracts.
3. **Capability — What else can it do?** A capability adds an externally observable behavior, such as PWA support, a runtime, a CLI, or an MCP interface.
4. **Lifecycle — How is it managed over time?** A lifecycle component supplies reusable machinery for validation, evolution, evidence, checkpoints, or release.

A future Website recipe, for example, can select a Website artifact that requires a shared Web foundation. A consumer sees the Website identity and can choose PWA or runtime capabilities; the foundation is resolved automatically and is never an include target. The descriptor represents this with `component_role` (`foundation`, `artifact`, `capability`, or `lifecycle`), while canonical definitions remain in the provider glossary.
