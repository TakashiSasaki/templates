# Contract evolution

The Webapp template treats each machine-readable contract and the contract manifest as a versioned repository interface. This document defines when versions change, how changes are classified, which identifiers remain stable, and which artifacts must move together.

## Version ownership

`contracts/manifest.json` records the current schema version and complete version history for:

- the manifest bootstrap format itself; and
- every registered domain contract.

A new contract family starts at version 1 with `changeType: initial`. Every later version is a single contiguous transition classified as `additive` or `breaking` and names one migration document.

Versions are positive integers local to one contract family. They are not release numbers, package versions, deployment revisions, dates, or compatibility claims for unrelated contracts.

## When to increment a schema version

Increment a contract's `schemaVersion` when either of these changes:

1. the set of contract documents accepted by the schema or cross-contract validator; or
2. the meaning, ownership, or implementation obligation of an accepted declaration.

Examples that require a new version include adding a required property, narrowing a value domain, adding or removing a cross-file invariant, changing the meaning of an existing value, renaming or removing a stable identifier, or changing which implementation evidence a declaration requires.

Do not increment a domain contract version for a prose clarification, spelling correction, test refactor, validator refactor, diagnostic improvement, or implementation change that preserves both accepted instances and contract semantics. Increment the manifest bootstrap version only when the manifest's own accepted structure or semantics change.

## Change classification

### Initial

Version 1 is `initial`. It has no migration because there is no earlier version.

### Additive

A transition is `additive` only when every document valid under the immediately preceding version remains valid and preserves the same meaning and obligations under the new version.

Typical additive changes include adding a genuinely optional declaration with a defined absent-value meaning, or adding validation metadata that does not alter any existing declaration's interpretation.

Treat expansion of a closed enum as breaking by default. Existing consumers may perform exhaustive handling even when old instances remain structurally valid.

### Breaking

A transition is `breaking` when a previously valid document can become invalid, a previously invalid document becomes valid with materially different semantics, or an existing declaration's meaning or required implementation evidence changes.

Breaking changes include required properties, removed or renamed properties, closed-enum changes, tighter constraints, new mandatory cross-contract relationships, changed default or absent-value meaning, and stable-identifier renames or removals.

The validator can prove that a classification is present and its migration is registered. It cannot prove that maintainers selected the correct semantic classification; that remains an explicit review responsibility.

## Stable identifiers

The following values are public repository references once committed:

- contract identifiers in `contracts/manifest.json`;
- surface, route, UI-state, and viewport identifiers;
- contract document and schema paths registered by the manifest;
- recovery-action and role identifiers when product implementation or evidence refers to them.

Do not rename an identifier merely to improve wording. A rename or removal is a breaking transition and its migration must identify the old value, the replacement or removal rationale, every referring contract, implementation boundary, test, evidence record, and deployment consequence.

Adding a new identifier can be additive only when no existing identifier changes meaning and existing consumers are not required to handle the new identifier exhaustively.

## Migration inventory

Every transition from version `N` to `N+1` registers exactly one file:

```text
docs/migrations/<contract-slug>-vN-to-vN+1.md
```

The contract slug is the contract document filename without `.json`. The manifest bootstrap uses `contract-manifest`.

The evolution validator rejects:

- histories that do not contain contiguous versions from 1 through the current version;
- migration paths that do not match the owning contract and transition;
- missing, symbolic-link, or non-regular migration files;
- duplicate migration registrations; and
- Markdown files under `docs/migrations/` that are not registered by a version history.

A migration document must describe the compatibility impact, required document edits, identifier mappings, implementation and evidence changes, validation commands, deployment sequencing when relevant, and rollback implications.

## Synchronized change set

A versioned contract change is incomplete unless the same pull request synchronizes every affected artifact:

1. the JSON Schema;
2. the example contract document;
3. `contracts/manifest.json`, including current version and history;
4. the deterministic migration document;
5. structural and cross-contract validators;
6. positive and negative tests;
7. architecture and operational guidance;
8. implementation-evidence expectations; and
9. release, deployment, and rollback documentation when the generated product is affected.

Changes spanning multiple contract families increment and migrate each affected family independently. Do not increment unrelated contracts merely to keep version numbers aligned.

## Validation boundary

`validate_contracts` verifies current manifest structure, current documents, schemas, and cross-contract invariants. `validate_contract_evolution` verifies version chains and the closed migration-document inventory. Both script and module entry points are authoritative and run in CI.

These validators do not reconstruct historical Git revisions, automatically compare previous schemas, generate migrations, or prove product implementation compatibility. Reviewers must inspect the previous version, verify the selected change classification, and confirm that migration instructions and implementation evidence are complete.
