# Contract completeness

The Webapp template treats contract completeness as five separate questions:

1. Is every active contract artifact in the repository known to the current-contract validator?
2. Is every active or retired contract transition known to the evolution validator and backed by one migration artifact?
3. Does every accepted declaration and transition have one implementation-evidence target?
4. Does one completed release record bind the current command and gate definitions to an exact candidate revision?
5. Does the current set cover the framework-neutral concerns that the template has intentionally accepted?

`contracts/manifest.json` answers the first two questions. `contracts/implementation-evidence.json` answers the third. `contracts/release-evidence.json` answers the fourth. Architectural review answers the fifth.

## Closed inventory

The manifest records each active domain contract's stable identifier, document path, schema path, stable migration slug, current document schema version, complete version history, and purpose. A retired non-core family moves to `retiredContracts`, which retains its identity, final live paths, stable migration slug, last live version, breaking retirement version, complete history, and purpose without retaining live contract or schema files. The manifest also records the bootstrap format's own version history.

The current-contract validator derives its active registry from `contracts`; the evolution validator reads both `contracts` and `retiredContracts`; the implementation-evidence validator reads the current declarations and every recorded transition; the release-evidence validator reads the authoritative product commands and release gates and binds their completed results to one explicitly supplied revision.

Validation fails when:

- a JSON document exists under `contracts/` but is not registered by an active entry;
- a JSON Schema exists under `schemas/` but is not registered by an active entry;
- a registered active document or schema is missing or is a symbolic link;
- identities, document paths, schema paths, or migration slugs are duplicated across active and retired entries;
- a manifest path escapes the repository-owned directories;
- an active document's `$schema` or `schemaVersion` disagrees with the manifest;
- a version history is not contiguous from version 1 through the current or retirement version;
- a retired version is not exactly one greater than the last live document version;
- a retirement history does not end in a breaking transition;
- a migration path does not match its owning stable slug and transition;
- a registered migration is missing, unreadable, visually empty, symbolic, or non-regular;
- a migration is registered more than once;
- any artifact under `docs/migrations/`, regardless of extension, is not registered by a version history;
- an implementation-evidence target is missing, duplicated, or unknown;
- an implementation proof references an unknown command or release gate;
- a product-mode proof command is not executed by a selected release gate;
- template implementation-evidence mode claims product implementation locations, verified results, commands, or gates;
- product release evidence is validated without an explicit immutable revision;
- the release subject does not match that expected revision;
- a release command or gate result is missing, duplicated, or unknown;
- release evidence was produced for an older authoritative command definition;
- a required command or gate failed, a command exit code is nonzero, or the release decision is not approved;
- release chronology places completion before start, approval before command completion, or evidence generation before approval; or
- template release-evidence mode claims a product revision, provenance, decision, command result, or gate result.

The manifest document and `schemas/contract-manifest.schema.json` are bootstrap metadata and are excluded from the active domain-contract registry, but their format is independently versioned in the manifest's top-level history.

## Current domain coverage

| Contract | Covered concern |
|---|---|
| `surfaces` | Browser-facing surface boundaries, audiences, authentication and authorization shape, data classifications, stability, diagnostics, and startup dependencies |
| `routes` | Canonical pathnames, aliases, surface ownership, unauthenticated and forbidden access-failure behavior, authentication return behavior, deep linking, browser history intent, supported states, document-title requirements, and focus targets |
| `ui_states` | Reusable visible-state categories, route or global presentation ownership, recovery-action identifiers, announcements, and focus strategies |
| `viewports` | Responsive lower bounds, input capabilities, zoom support, horizontal-scrolling policy, and orientation independence |
| `implementation_evidence` | Implementation ownership, positive and negative proofs, authoritative commands, release-gate definitions, and coverage of every current declaration and registered transition |
| `release_evidence` | Exact candidate revision, command-definition digests, completed command and gate results, execution provenance, chronological closure, and release approval |

Every declared browser-facing surface must be owned by at least one canonical route. Multiple canonical routes may share one surface when they expose the same audience, authentication, authorization, data, stability, and diagnostic boundary.

Every route declares whether unauthenticated and forbidden access failures render a route-scoped state, redirect, or are inapplicable. Applicability follows route authentication and the owning surface's authorization mode. Rendered failures require the corresponding route state, while redirected or inapplicable failures prohibit that state reference. This describes observable presentation behavior without selecting an identity provider, redirect destination, router, or authorization implementation.

Every route-scoped UI state must be listed by at least one canonical route. Multiple routes may share one route-scoped state. Global states are owned by an application shell, router, or another top-level presentation boundary and must not be listed by a route. This ownership distinction is framework-neutral and does not prescribe a routing library, state store, rendering model, or component structure.

Every surface, route, UI state, viewport, input capability, and post-version-1 transition has exactly one implementation-evidence target. The template records requirements without pretending to have product code. Generated repositories replace the requirement inventory with verified boundaries, proofs, commands, and release gates.

Product release evidence is a completed record for one exact revision. It covers every registered release gate and every command executed by those gates, binds each result to the current command text by SHA-256, and closes the sequence from execution through approval. It does not execute commands or select a CI provider.

Current-contract validation checks identifiers, references, surface-to-route coverage, access-failure applicability and state consistency, UI-state scope and route coverage, surface dependency cycles, route collisions, authentication consistency, visible text, and viewport continuity. Evolution validation checks active and retired histories, stable migration ownership, retirement invariants, and the closed migration-artifact inventory. Implementation-evidence validation checks coverage and release-reference closure. Release-evidence validation checks revision, result, digest, outcome, and chronology closure.

## Deliberately product-owned

The template does not create implementation values whose selection depends on the generated product repository:

- framework and rendering model;
- package manager and authoritative product commands;
- concrete implementation locators;
- backend, API, persistence, and deployment topology;
- authentication provider, redirect destinations, and trusted authorization implementation;
- browser support matrix;
- observability platform;
- concrete offline and installability behavior;
- actual product tests and expected results;
- CI-provider identifiers and artifact-retention policy;
- the release candidate revision, run locator, and approval procedure; and
- deployment execution and post-deployment verification.

The implementation-evidence contract defines the reusable shape for repository-local implementation values. The release-evidence contract defines the reusable shape for completed release results. Template mode does not claim either; product mode requires concrete values.

## Criteria for another contract family

Add another domain contract only when all of the following are true:

- the concern is externally observable or constrains Web-application design across frameworks;
- its semantics are not merely coding-agent policy or repository governance;
- a generated product repository can provide one authoritative declaration;
- cross-file references and failure cases can be validated locally;
- the contract does not require placeholder frameworks, providers, manifests, or deployment files;
- ownership, evidence, retirement, and migration consequences can be documented.

A new family begins at version 1 with `changeType: initial` and one stable migration slug. The manifest must be updated in the same change as a new, moved, retired, or versioned contract family. Its accepted entities or transitions must also be added to implementation-evidence coverage when they represent an implementation target. Later transitions follow [`contract-evolution.md`](contract-evolution.md) and must synchronize the schema, example contract or tombstone, manifest history, deterministic migration, validators, tests, guidance, implementation evidence, release evidence when command or gate definitions change, deployment sequencing, and rollback expectations.
