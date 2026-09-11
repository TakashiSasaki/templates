# Repository Topology: Hub-and-Orphan

This repository adopts the **Hub-and-Orphan** repository pattern as an explicit repository topology choice.

## Core Topology Invariants

1. **Hub Branch as Read-Only Discovery Projection**
   - The Hub branch (default: `main`) is an integration and discovery projection.
   - Direct mutations to component source files inside the Hub are strictly forbidden.
   - Autonomous agents and human developers discover repository structure by reading `contracts/repository-topology.json` from the Hub branch.

2. **Orphan Branches as Independent Component Authorities**
   - Each component history lives on its own isolated Git orphan branch with no shared commit history.
   - The orphan branch is the single source of truth and mutation authority for that component.

3. **Branch-Name Equals Mount-Path Rule**
   - For every orphan component, its Git branch name must exactly equal its mount path inside the Hub.
   - Example: an orphan branch named `docs` is mounted at `docs/` in the Hub.

4. **Leaf-Only Namespace Invariant**
   - Component mount paths must occupy disjoint leaf namespaces.
   - No component mount path may be an ancestor, parent, or sub-directory of another component mount path.

5. **Self-Referencing Submodule Projection**
   - The Hub mounts orphan branches as submodules pointing back to the consumer repository itself (`.` or remote origin).

6. **Authority-to-Hub Synchronization Direction**
   - Mutations must be committed to the component orphan branch authority first.
   - Once the orphan branch advances, the Hub branch updates its submodule pointer to the new commit.
   - Synchronization is strictly unidirectional: `authority -> Hub`.

## Machine-Readable Contract

The canonical topology declaration is defined in `contracts/repository-topology.json` and validated by `schemas/repository-topology.schema.json`.
