# Contract completeness

The Webapp template treats contract completeness as two separate questions:

1. Is every contract artifact in the repository known to the validator?
2. Does the current set cover the framework-neutral concerns that the template has intentionally accepted?

`contracts/manifest.json` answers the first question. Architectural review answers the second.

## Closed inventory

The manifest records each domain contract's stable identifier, document path, schema path, document schema version, and purpose. The validator derives its contract registry from this file rather than from a parallel Python list.

Validation fails when:

- a JSON document exists under `contracts/` but is not registered;
- a JSON Schema exists under `schemas/` but is not registered;
- a registered document or schema is missing or is a symbolic link;
- identifiers, document paths, or schema paths are duplicated;
- a manifest path escapes the repository-owned directories;
- a document's `$schema` or `schemaVersion` disagrees with the manifest.

The manifest document and `schemas/contract-manifest.schema.json` are bootstrap metadata and are excluded from the domain-contract inventory.

## Current domain coverage

| Contract | Covered concern |
|---|---|
| `surfaces` | Browser-facing surface boundaries, audiences, authentication and authorization shape, data classifications, stability, diagnostics, and startup dependencies |
| `routes` | Canonical pathnames, aliases, surface ownership, authentication return behavior, deep linking, browser history intent, supported states, document-title requirements, and focus targets |
| `ui_states` | Reusable visible-state categories, recovery-action identifiers, announcements, and focus strategies |
| `viewports` | Responsive lower bounds, input capabilities, zoom support, horizontal-scrolling policy, and orientation independence |

Cross-contract validation currently checks identifiers, references, surface dependency cycles, route collisions, authentication consistency, visible text, and viewport continuity.

## Deliberately product-owned

The template does not create machine-readable placeholders for choices whose values depend on the generated product repository:

- framework and rendering model;
- package manager and authoritative commands;
- backend, API, persistence, and deployment topology;
- authentication provider and trusted authorization implementation;
- browser support matrix;
- observability platform;
- concrete offline and installability behavior;
- implementation evidence and release procedures.

A future contract may describe one of these concerns only after the reusable semantics are clear and the template can validate them without selecting a competing implementation.

## Criteria for another contract family

Add another domain contract only when all of the following are true:

- the concern is externally observable or constrains Web-application design across frameworks;
- its semantics are not merely coding-agent policy or repository governance;
- a generated product repository can provide one authoritative declaration;
- cross-file references and failure cases can be validated locally;
- the contract does not require placeholder frameworks, providers, manifests, or deployment files;
- ownership and migration consequences can be documented.

The manifest must be updated in the same change as a new, renamed, removed, or versioned contract family.
