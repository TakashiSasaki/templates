# Contract completeness

The Webapp template treats contract completeness as three separate questions:

1. Is every contract artifact in the repository known to the validator?
2. Is every contract version transition known to the evolution validator and backed by one migration document?
3. Does the current set cover the framework-neutral concerns that the template has intentionally accepted?

`contracts/manifest.json` answers the first two questions. Architectural review answers the third.

## Closed inventory

The manifest records each domain contract's stable identifier, document path, schema path, current document schema version, complete version history, and purpose. It also records the manifest bootstrap format's own version history. The validator derives its contract registry from this file rather than from a parallel Python list.

Validation fails when:

- a JSON document exists under `contracts/` but is not registered;
- a JSON Schema exists under `schemas/` but is not registered;
- a registered document or schema is missing or is a symbolic link;
- identifiers, document paths, or schema paths are duplicated;
- a manifest path escapes the repository-owned directories;
- a document's `$schema` or `schemaVersion` disagrees with the manifest;
- a version history is not contiguous from version 1 through the current version;
- a migration path does not match its owning contract and transition;
- a registered migration is missing, symbolic, or non-regular;
- a migration is registered more than once; or
- a Markdown file under `docs/migrations/` is not registered by a version history.

The manifest document and `schemas/contract-manifest.schema.json` are bootstrap metadata and are excluded from the domain-contract inventory, but their format is independently versioned in the manifest's top-level history.

## Current domain coverage

| Contract | Covered concern |
|---|---|
| `surfaces` | Browser-facing surface boundaries, audiences, authentication and authorization shape, data classifications, stability, diagnostics, and startup dependencies |
| `routes` | Canonical pathnames, aliases, surface ownership, unauthenticated and forbidden access-failure behavior, authentication return behavior, deep linking, browser history intent, supported states, document-title requirements, and focus targets |
| `ui_states` | Reusable visible-state categories, route or global presentation ownership, recovery-action identifiers, announcements, and focus strategies |
| `viewports` | Responsive lower bounds, input capabilities, zoom support, horizontal-scrolling policy, and orientation independence |

Every declared browser-facing surface must be owned by at least one canonical route. Multiple canonical routes may share one surface when they expose the same audience, authentication, authorization, data, stability, and diagnostic boundary.

Every route declares whether unauthenticated and forbidden access failures render a route-scoped state, redirect, or are inapplicable. Applicability follows route authentication and the owning surface's authorization mode. Rendered failures require the corresponding route state, while redirected or inapplicable failures prohibit that state reference. This describes observable presentation behavior without selecting an identity provider, redirect destination, router, or authorization implementation.

Every route-scoped UI state must be listed by at least one canonical route. Multiple routes may share one route-scoped state. Global states are owned by an application shell, router, or another top-level presentation boundary and must not be listed by a route. This ownership distinction is framework-neutral and does not prescribe a routing library, state store, rendering model, or component structure.

Cross-contract validation currently checks identifiers, references, surface-to-route coverage, access-failure applicability and state consistency, UI-state scope and route coverage, surface dependency cycles, route collisions, authentication consistency, visible text, and viewport continuity. Evolution validation separately checks complete version histories and the closed migration-document inventory.

## Deliberately product-owned

The template does not create machine-readable placeholders for choices whose values depend on the generated product repository:

- framework and rendering model;
- package manager and authoritative commands;
- backend, API, persistence, and deployment topology;
- authentication provider, redirect destinations, and trusted authorization implementation;
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

A new family begins at version 1 with `changeType: initial`. The manifest must be updated in the same change as a new, renamed, removed, or versioned contract family. Later transitions follow [`contract-evolution.md`](contract-evolution.md) and must synchronize the schema, example contract, manifest history, deterministic migration, validators, tests, guidance, and evidence expectations.
