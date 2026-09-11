# Repository topology: Hub-and-Orphan architecture

## Overview

This document defines the architectural specification and publication model for
the **Hub-and-Orphan** repository pattern (`topology.hub-and-orphan`), formalizing
repository topology as an orthogonal component role within `TakashiSasaki/templates`.

Repository topology governs the branching structure, projection rules, submodule
boundaries, and cross-authority integration paths across independent semantic domains.

## The Hub-and-Orphan pattern

The Hub-and-Orphan repository topology decouples independent domain authorities
into disconnected orphan git branches while maintaining a unified discovery hub:

```
                  ┌─────────────────────────────────┐
                  │            main hub             │
                  │   Unified discovery & portals   │
                  │   agent.json / site projection  │
                  └───────┬──────────────┬──────────┘
                          │              │
       projection imports │              │ projection imports
                          ▼              ▼
     ┌─────────────────────────┐    ┌─────────────────────────┐
     │   composition branch    │    │      policy branch      │
     │   Independent orphan    │    │   Independent orphan    │
     │   Schemas, components,  │    │   Operating policies,   │
     │   recipes, foundations  │    │   profiles, procedures  │
     └─────────────────────────┘    └─────────────────────────┘
```

### 1. Disconnected orphan authority branches

Each primary domain authority exists on its own root-level orphan git branch:
- **`composition`**: Owns component schemas, artifact definitions, capability selection, recipes, and resolution invariants.
- **`policy`**: Owns coding-agent operating policies, profiles, verification procedures, and change orchestration skills.
- **`site`**: Owns documentation assembly, cross-authority publication, web portal, agent discovery integration, and localization.

Orphan branches share no git ancestry with one another or with historical default branches. Each branch maintains independent versioning, test suites, and git commit graphs.

### 2. Central discovery hub (`main`)

The central default branch (`main`) serves as the discovery hub and assembly surface:
- It aggregates the published outputs and interfaces from each domain authority.
- It exposes root-level discovery metadata (including `agent.json` and `.well-known/agent.json`).
- It projects authority contents into mount paths corresponding strictly to the authority names.

### 3. Submodule and projection rule

When authority branches are projected or mounted as git submodules or projection directories:
- **`branch == mountPath`**: The mount path in the hub directory tree MUST match the authoritative branch name exactly (e.g. `composition` mounted at `/composition`, `policy` mounted at `/policy`).
- **Leaf-only namespaces**: Domain authorities must maintain leaf-only namespaces to prevent path collisions when projected into the central hub.

### 4. Strict authority-to-hub synchronization

The synchronization direction between authority branches and the central hub is strictly unidirectional:
- **Authority to Hub**: Changes originate within authority branches (`composition`, `policy`, `site`) via isolated pull requests and verification workflows. Once reviewed and accepted, qualified revisions are published to the hub.
- **Prohibition of Direct Hub Mutation**: Direct modification of authority component files, policy rules, or schema definitions directly on the `main` hub branch is prohibited. Any change to authority-owned assets on `main` without provenance from the respective authority branch is considered an integrity violation.

## Discovery and agent.json integration

The Site authority materializes discovery metadata (`agent.json` and `assets/agent.json`) consuming verified revisions of `composition` and `policy`:
- **`publication-sources.json`**: Records the exact git commit SHAs of the upstream orphan branches accepted for publication.
- **Agent bootstrap generator**: Reads the pinned commit SHAs, validates authority signatures and schemas, and renders the unified bootstrap document.
- **Hub discovery**: Agents accessing the repository can discover the complete set of capabilities, recipes, and topologies starting from `agent.json` at the repository root.
