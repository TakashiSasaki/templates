# Operationalize a generated repository

This guide describes how to turn the framework-neutral Webapp template into one product repository with explicit implementation, release, and operational ownership. It complements [TEMPLATE.md](../TEMPLATE.md) and does not select a framework, package manager, backend, authentication provider, redirect destination, browser matrix, CI provider, artifact store, or deployment platform.

The template contracts describe externally observable behavior. The generated repository must provide the concrete implementation, machine-readable implementation evidence, and revision-bound release evidence that satisfy those declarations.

## 1. Freeze the template baseline

Start from one known `webapp` revision and record that revision in the generated repository's setup notes or change log. Copy the template-owned contracts, schemas, validators, migrations, tests, and validation instructions as one coherent baseline.

Do not combine the unrelated `webapp` and `policy` histories merely to share files. Do not copy framework starters, deployment workflows, or coding-agent policy from an unrelated branch as if they were part of this template.

Before customization, choose and provision the contract-validation path before invoking it.

If the generated repository retains the shipped Python validators:

- retain `requirements-dev.lock` or an intentionally updated equivalent lock for validator dependencies;
- create a separate isolated validator environment from that lock;
- run both entry points for `validate_contracts`, `validate_contract_evolution`, `validate_implementation_evidence`, and `validate_release_evidence` with that environment's interpreter;
- use the release validator without `--expected-revision` only while `contracts/release-evidence.json` remains in template mode;
- pass the exact candidate revision to both release validator entry points after product release evidence is materialized;
- run the retained validator regression suite;
- keep the clean-room generated-repository classes as template-maintainer-only coverage: they automatically skip after the source implementation-evidence document switches to `mode: product`, while their scope regressions remain active; and
- keep the validator environment separate from the product environment and follow the repository's documented clean-environment procedure.

The product lockfile does not provision the shipped validators, and globally installed Python packages are not an acceptable substitute for the reviewed validator environment.

If the generated repository replaces the shipped validators with an equivalent verified integration, record that integration's isolated dependencies, command, revision input, and evidence instead. On every clean runner, that path must create and provision its isolated validation environment from the recorded lock or toolchain-specific dependency definition, perform the toolchain-appropriate dependency verification, and only then invoke the equivalent validation. Do not invoke the shipped Python entry points in that path.

## 2. Select one product toolchain

Make the product choices that the template intentionally leaves open:

- one application framework or browser-platform-only implementation;
- one package manager and authoritative lockfile;
- one client-side, server-side, or hybrid rendering model;
- one backend and API topology;
- one authentication and authorization design;
- one persistence model;
- one CI execution environment;
- one deployment target;
- one observability approach;
- one supported browser matrix;
- one offline and installability scope; and
- one release-result retention and approval procedure.

Record the authoritative build, test, lint, validation, and deployment commands. Remove competing manifests, lockfiles, framework starters, and deployment configurations rather than retaining them as unresolved alternatives.

The template-maintainer Python environment validates the template contracts. It is not automatically the product runtime. A product may retain, replace, or separately invoke the validators, but the contract semantics, implementation proof, and revision-bound release evidence must remain explicit.

## 3. Customize the contract set

Replace the example declarations in `contracts/` with product-specific values while preserving the manifest as the active inventory, retired-history inventory, and evolution source of truth.

For each change:

1. Keep every active product-domain contract document and schema registered in `contracts/manifest.json`; preserve the validator's exclusion of the bootstrap artifacts `contracts/manifest.json` and `schemas/contract-manifest.schema.json` themselves from the active domain-contract registry.
2. Keep each active document `$schema` and `schemaVersion` consistent with the manifest.
3. Preserve a contiguous `versionHistory` from version 1 through the current manifest, active contract, or retirement version.
4. Assign one stable `migrationSlug` to every family. Do not derive historical migration ownership from the current document path, and preserve the slug when a document or schema moves.
5. Classify each transition after version 1 as `additive` or `breaking` and register `docs/migrations/<migration-slug>-vN-to-vN+1.md`.
6. Preserve stable contract and entity identifiers unless a breaking migration accounts for every reference, implementation boundary, test, evidence record, deployment consequence, release consequence, and rollback implication.
7. When retiring a non-core family, add a `retiredContracts` tombstone before removing its active entry and live document and schema files. Preserve the stable ID, final live paths, migration slug, last live version, next breaking retirement version, complete history, purpose, consumer migration, deployment sequence, and rollback procedure.
8. Remove every artifact under `docs/migrations/` that is not registered by an active, retired, or bootstrap history, regardless of filename extension.
9. Declare every externally observable application surface and canonical route.
10. Declare each route's unauthenticated and forbidden access-failure behavior from its authentication requirement and owning surface authorization mode.
11. For `render-state`, list the corresponding `unauthorized` or `forbidden` UI state; for `redirect` or `not-applicable`, remove that state reference.
12. Keep route-to-surface and route-to-UI-state references valid, ensure every declared surface is owned by at least one canonical route, and classify each UI state as `route` or `global`.
13. Ensure every route-scoped state is listed by at least one canonical route and remove global state identifiers from every route declaration.
14. Define aliases and canonical paths without collisions.
15. Describe authentication return behavior and deep-link expectations for protected routes.
16. Declare loading, empty, partial, error, offline, and access states that users can observe.
17. Declare viewport lower bounds and input capabilities independently.
18. Synchronize `contracts/implementation-evidence.json` whenever an entity or transition is added, renamed, removed, versioned, or retired.
19. Regenerate product release evidence whenever authoritative command text, gate composition, or the candidate revision changes.
20. Synchronize the schema, example document or tombstone, manifest history, migration, validators, positive and negative tests, architecture guidance, implementation evidence, release evidence, and release documentation for every versioned change.

A route's access-failure declaration distinguishes rendering an access state from redirecting away from the route. `authenticationReturn` separately declares whether successful authentication returns to the original route. The generated repository owns redirect destinations, identity-provider integration, authorization recovery, and trusted enforcement.

A route-scoped state belongs to the observable presentation owned by one or more canonical routes. A global state belongs to an application shell, router, top-level error boundary, or another presentation boundary outside canonical route ownership. Scope does not choose a framework, routing library, state store, rendering model, or component structure.

A contract version changes when accepted instances or declaration semantics change. A transition is additive only when every document valid under the preceding version remains valid with unchanged meaning and obligations. Treat required fields, tighter constraints, new mandatory cross-contract relationships, closed-enum changes, semantic changes, stable-identifier renames or removals, and contract-family retirement as breaking. Prose clarification and validator or test refactoring do not increment a domain version when accepted instances and meaning remain unchanged. See [`architecture/contract-evolution.md`](architecture/contract-evolution.md).

A document or schema move does not authorize rewriting old migration filenames. Preserve the family's `migrationSlug` and add the move as a breaking transition when public paths change. A retired tombstone remains after the live files are removed, so its final migration and earlier history remain registered and reviewable.

Repositories migrating a version 1 contract manifest must follow [`migrations/contract-manifest-v1-to-v2.md`](migrations/contract-manifest-v1-to-v2.md). Repositories migrating a version 1 route document must follow [`migrations/routes-v1-to-v2.md`](migrations/routes-v1-to-v2.md). Repositories migrating a version 1 UI-state document must follow [`migrations/ui-states-v1-to-v2.md`](migrations/ui-states-v1-to-v2.md).

A new contract family belongs in this set only when its semantics are framework-neutral, externally observable or cross-cutting across products, generated product repositories can provide one authoritative declaration, and local cross-file validation can reject its failure cases. Otherwise, keep the concern product-owned and document it in the generated repository. A new family starts at version 1 with `changeType: initial` and one stable migration slug; do not create a migration from a nonexistent earlier version.

## 4. Connect implementation to contracts

`contracts/implementation-evidence.json` is the authoritative mapping. Do not replace it with an unvalidated prose table.

The template ships `mode: template`. Each record identifies a required implementation boundary and the positive and negative evidence a generated repository must provide without claiming that the template contains product code.

After selecting the product toolchain:

1. change the implementation-evidence document to `mode: product`;
2. give every implementation boundary a concrete repository locator;
3. register stable IDs for authoritative product commands;
4. register release gates and the commands they execute;
5. replace every required proof with verified evidence, including its kind, locator, command, and expected observable result; and
6. ensure every proof command is executed by at least one release gate selected by that record.

At minimum, the implementation must make evidence available for:

| Contract concern | Product evidence |
| --- | --- |
| Surfaces | rendered entry points, audience checks, trusted authentication and authorization enforcement, data-classification handling, and dependency behavior |
| Routes | canonical navigation, aliases or redirects, browser history, deep links, access-failure rendering or redirects, authentication return, document titles, and focus targets |
| UI states | deterministic rendering, route or global ownership, announcements, focus, and recovery actions |
| Viewports | responsive behavior at declared lower bounds, zoom, reflow, scrolling, and orientation requirements |
| Input capabilities | workflow completion with each declared input mode independently of viewport width |
| Evolution | previous and current versions, stable migration slug, change-classification review, identifier and path mapping, active-to-retired transition when applicable, migration execution, backward-compatibility evidence, deployment sequencing, and rollback evidence |

Route names and directory names are not authorization. Enforce access decisions in trusted server or application boundaries, and test that an authenticated principal cannot cross an authorization boundary by changing a path, identifier, or client-side state.

## 5. Build implementation evidence

Add product-owned tests that exercise the real implementation path. Each verified proof records:

- the kind of evidence;
- the repository-local test, fixture, inspection, or migration locator;
- the authoritative command that executes it;
- the expected observable result; and
- whether the proof is positive or negative.

Every target requires at least one positive and one negative proof in both template and product mode. Negative evidence for access-controlled surfaces and routes, degraded/error/connectivity/access states, and breaking transitions must directly exercise the corresponding security, recovery, compatibility, or rollback boundary. Negative evidence for other targets proves invalid ownership, unsupported interaction, clipping, unintended state, or an equivalent failure condition.

Examples include unauthenticated access to public and protected routes, forbidden access to role-protected routes, rendered access states, access redirects and their destinations, direct navigation to a deep link, an authentication return to the original route, every declared route-scoped state through at least one owning route, every declared global state through its top-level owner, rejection of global states from route declarations, alias collision prevention, keyboard navigation, zoom, narrow and wide layouts, offline or partial failure, and recovery actions.

For a contract transition, test the previous valid representation, the migrated representation, invalid incomplete migrations, stable-identifier and path mappings, implementation behavior before and after rollout, and rollback to a compatible deployed revision. An additive classification requires evidence that preceding-version instances retain their meaning. A breaking classification requires explicit consumer and deployment migration evidence.

For retirement, test the final live contract, the breaking retirement migration, removal of live files from the active registry, retention of the tombstone and all historical migrations, consumer behavior after removal, and restoration or forward-fix behavior. A rollback that would discard history relied on by a consumer is not valid; coordinate the consumer rollback or forward-fix instead.

The current-contract validator proves that active declarations are structurally and cross-contract valid. The evolution validator proves that active and retired version chains, stable migration ownership, retirement invariants, and the migration-artifact inventory are complete. The implementation-evidence validator proves target coverage and command/gate reference closure. None of these validators execute product tests or prove that the selected semantic classification and evidence quality are correct; those proofs remain in command results, review, and release evidence.

## 6. Build revision-bound release evidence

`contracts/release-evidence.json` is the authoritative completed release record. The template ships in `mode: template` and claims no candidate revision or execution result.

After product commands have executed for an immutable candidate revision:

1. change the release-evidence document in the release workspace to `mode: product`;
2. record the exact lowercase 40-hex candidate revision in `subject.revision`;
3. record one result for every authoritative command executed by any registered release gate;
4. calculate SHA-256 over the exact UTF-8 command text currently declared in implementation evidence and store it as `commandDigest`;
5. record pass/fail status, exit code, UTC start and completion times, and a reviewable result locator;
6. record one result for every registered release gate;
7. record execution provenance and its reviewable locator;
8. record the release decision only after the commands have completed; and
9. validate both release-evidence entry points with the exact expected revision.

Example validation:

```sh
python scripts/validate_release_evidence.py --expected-revision "$CANDIDATE_SHA"
python -m scripts.validate_release_evidence --expected-revision "$CANDIDATE_SHA"
```

The release orchestrator must supply `CANDIDATE_SHA` explicitly. The validator does not infer a provider-specific environment variable and does not invoke Git.

Do not require a committed file to name its own commit. That produces a circular self-reference because changing the file changes the commit. Materialize release evidence in an ephemeral checkout, generated artifact, release workspace, or another immutable evidence bundle associated with the candidate revision. Product policy determines retention, attestation, signatures, and human approval requirements.

Regenerate the record whenever the revision, authoritative command text, or release-gate composition changes. Stable command IDs do not authorize reuse after command text changes because the validator recomputes each SHA-256 digest.

See [`architecture/release-evidence.md`](architecture/release-evidence.md).

### Clean-room generated-repository proof

Template maintainers exercise the implementation transition in `tests/test_generated_repository_conformance.py` and the release transition in `tests/test_generated_release_evidence_conformance.py`.

The implementation regression creates a temporary copy of the template without `.git`, local virtual environments, or cache residue; explicitly settles copied example values as product declarations; converts only the copied implementation-evidence document to product mode; materializes repository-local boundary and proof locators; and selects a release gate that executes the authoritative fixture proof command.

The harness directly invokes the reviewed fixture script with a fixed argument vector. It does not interpret command text from the evidence document and does not provide a reusable arbitrary-command executor. After all 52 current positive and negative implementation outcomes pass, it executes the first six validator entry points from the generated repository root.

The release regression materializes one exact revision, complete command and gate results, current command digests, provenance, chronology, and approval. It invokes both copied release validator entry points with the expected revision. Negative cases reject revision mismatch and command-definition drift.

For invalid implementation copies, the harness invokes the copied standalone implementation-evidence validator and asserts its nonzero exit plus the expected stderr diagnostic. The false-proof case directly invokes the copied reviewed product proof. Together the generated tests cover all eight validator entry points while keeping template source responsibility and generated product responsibility distinct. See [`architecture/generated-repository-conformance.md`](architecture/generated-repository-conformance.md).

## 7. Integrate validation into CI

Run validation from a clean, documented environment and keep commands reproducible:

1. create the product's isolated environment;
2. install the product lockfile without undeclared dependency inputs;
3. if the shipped validators are retained, create their separate isolated validator environment, install `requirements-dev.lock` or the reviewed equivalent, verify the installed distribution set, run `pip check`, invoke the six non-release entry points, and run retained validator regressions;
4. execute every authoritative command referenced by implementation evidence directly through reviewed product workflow code, not through a generic command-string executor;
5. collect complete command and gate results for the exact candidate revision;
6. materialize product-mode release evidence and invoke both release validator entry points with that exact revision;
7. require the approved release-evidence result before publication or deployment;
8. run product unit, integration, accessibility, migration, retirement, end-to-end, build, type, lint, and security checks not already represented by authoritative commands; and
9. publish diagnostics and retained evidence without exposing secrets.

A template-mode repository can run all eight validator entry points without a revision because the release-evidence document claims no result. A product-mode release record requires the explicit revision argument.

Keep contract validation separate from product runtime startup and deployment. A product command may start the real application, but a validator-only job should not silently depend on a local developer process, undeclared service, production credentials, or provider-specific mutable ref.

## 8. Define release and deployment ownership

The generated repository owns CI configuration, deployment configuration, environment management, migrations, retirement, rollback, observability, evidence retention, and release approval. Before treating it as operational, document:

- how the candidate and deployed revisions are identified;
- how release evidence is associated with the candidate revision without circular self-reference;
- how long command, gate, artifact, and approval evidence is retained;
- which manifest and active contract schema versions the revision serves;
- which retired-family tombstones and migrations it preserves;
- how additive and breaking transitions are reviewed and released;
- how every backward-incompatible change is migrated;
- how stable identifiers and migration slugs are preserved or translated across a breaking transition;
- how a retiring family is removed from producers and consumers in a safe order;
- how health and readiness differ from user-facing error states;
- how secrets, logs, diagnostics, and evidence locators are redacted;
- how rollback preserves or restores contract compatibility without deleting required history;
- which gates block release;
- who or what records the approved decision; and
- where reviewers can inspect implementation boundaries, proof expectations, command results, gate results, and deployment outcomes.

The Webapp template does not enable a deployment target, select a CI provider, or choose a production topology. Those decisions must be explicit in the generated repository and validated by its own workflow.

## Completion checklist

A generated repository is ready for independent product review when:

- one product toolchain and one authoritative lockfile are selected;
- example contracts have been replaced or explicitly retained as product declarations;
- the closed manifest, active schemas, active document metadata, stable migration slugs, active and retired histories, tombstones, and migration-artifact inventory agree;
- all externally observable surfaces and canonical routes are declared, and every surface is owned by at least one canonical route;
- every route has access-failure behavior consistent with authentication and authorization declarations, and access-state references match that behavior;
- every UI state has an intentional route or global scope, every route-scoped state has a route owner, and no global state is listed by a route;
- all observable states, viewports, and input capabilities are declared;
- every declaration and registered transition has exactly one implementation-evidence target;
- implementation evidence uses `mode: product`;
- every implementation record has a verified boundary, verified positive evidence, verified negative evidence, authoritative commands, and selected release gates;
- every proof command is executed by at least one selected release gate;
- stable identifiers and migration slugs are preserved or covered by explicit breaking migrations;
- retired families have no live registered files but retain complete tombstones, migrations, deployment evidence, and rollback implications;
- trusted authentication and authorization enforcement is tested;
- release evidence is materialized for the exact candidate revision after authoritative commands finish;
- every registered gate and every command executed by those gates has one passing result;
- every command result digest matches the current command definition;
- command, decision, and generation timestamps are chronologically closed;
- the release decision is approved;
- the isolated validator distribution set and dependency graph verify successfully;
- all eight validator entry points pass, with the exact revision supplied for product release evidence;
- the retained regression suite passes with template-maintainer-only clean-room classes skipped in product source mode;
- product evidence commands pass in CI;
- build, deployment, migration, retirement, rollback, observability, evidence retention, and release ownership are documented; and
- template-only guidance and unused alternatives have been removed.
