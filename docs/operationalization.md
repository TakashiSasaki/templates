# Operationalize a generated repository

This guide describes how to turn the framework-neutral Webapp template into one product repository with explicit implementation, release, handoff, and operational ownership. It complements [TEMPLATE.md](../TEMPLATE.md) and does not select a framework, package manager, backend, authentication provider, redirect destination, browser matrix, CI provider, artifact store, signing format, or deployment platform.

The template contracts describe externally observable behavior. The generated repository must provide the concrete implementation, machine-readable implementation evidence, revision-bound release evidence, and digest-closed release bundle that satisfy those declarations.

## 1. Freeze the template baseline

Start from one known `webapp` revision and record that revision in the generated repository's setup notes or change log. Copy the template-owned contracts, schemas, validators, migrations, tests, and validation instructions as one coherent baseline.

Do not combine the unrelated `webapp` and `policy` histories merely to share files. Do not copy framework starters, deployment workflows, or coding-agent policy from an unrelated branch as if they were part of this template.

Before customization, choose and provision the contract-validation path before invoking it.

If the generated repository retains the shipped Python validators:

- retain `requirements-dev.lock` or an intentionally updated equivalent lock for validator dependencies;
- create a separate isolated validator environment from that lock;
- run both entry points for `validate_contracts`, `validate_contract_evolution`, `validate_implementation_evidence`, `validate_release_evidence`, and `validate_release_bundle` with that environment's interpreter;
- use the release-evidence and release-bundle validators without `--expected-revision` only while both documents remain in template mode;
- pass the exact candidate revision to both release-evidence and both release-bundle entry points after product records are materialized;
- run the retained validator regression suite;
- keep the clean-room generated-repository classes as template-maintainer-only coverage: they automatically skip after the source implementation-evidence document switches to `mode: product`, while their scope regressions remain active; and
- keep the validator environment separate from the product environment and follow the repository's documented clean-environment procedure.

The product lockfile does not provision the shipped validators, and globally installed Python packages are not an acceptable substitute for the reviewed validator environment.

If the generated repository replaces the shipped validators with an equivalent verified integration, record that integration's isolated dependencies, commands, revision input, byte-digest behavior, and evidence instead. On every clean runner, that path must create and provision its isolated validation environment from the recorded lock or toolchain-specific dependency definition, perform the toolchain-appropriate dependency verification, and only then invoke the equivalent validation. Do not invoke the shipped Python entry points in that path.

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
- one offline and installability scope;
- one release-result and bundle retention procedure;
- one release approval and handoff procedure; and
- one signing, attestation, redaction, rollback, and supersession policy where required.

Record the authoritative build, test, lint, validation, and deployment commands. Remove competing manifests, lockfiles, framework starters, and deployment configurations rather than retaining them as unresolved alternatives.

The template-maintainer Python environment validates the template contracts. It is not automatically the product runtime. A product may retain, replace, or separately invoke the validators, but the contract semantics, implementation proof, revision-bound release evidence, and exact handoff bytes must remain explicit.

## 3. Customize the contract set

Replace the example declarations in `contracts/` with product-specific values while preserving the manifest as the active inventory, retired-history inventory, and evolution source of truth.

For each change:

1. Keep every active product-domain contract document and schema registered in `contracts/manifest.json`; preserve the validator's exclusion of the bootstrap artifacts `contracts/manifest.json` and `schemas/contract-manifest.schema.json` themselves from the active domain-contract registry.
2. Keep each active document `$schema` and `schemaVersion` consistent with the manifest.
3. Preserve a contiguous `versionHistory` from version 1 through the current manifest, active contract, or retirement version.
4. Assign one stable `migrationSlug` to every family. Do not derive historical migration ownership from the current document path, and preserve the slug when a document or schema moves.
5. Classify each transition after version 1 as `additive` or `breaking` and register `docs/migrations/<migration-slug>-vN-to-vN+1.md`.
6. Preserve stable contract and entity identifiers unless a breaking migration accounts for every reference, implementation boundary, test, evidence record, deployment consequence, release consequence, bundle consequence, and rollback implication.
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
19. Regenerate product release evidence whenever authoritative command text, gate composition, result data, provenance, decision, or the candidate revision changes.
20. Regenerate the release bundle whenever any active contract byte, registered document path, active inventory entry, release-evidence byte, or candidate revision changes.
21. Synchronize the schema, example document or tombstone, manifest history, migration, validators, positive and negative tests, architecture guidance, implementation evidence, release evidence, release bundle, and release documentation for every versioned change.

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

Do not require a committed file to name its own commit. That produces a circular self-reference because changing the file changes the commit. Materialize release evidence in an ephemeral checkout, generated artifact, release workspace, or another immutable evidence workspace associated with the candidate revision. Product policy determines retention, attestation, signatures, and human approval requirements.

Regenerate the record whenever the revision, authoritative command text, release-gate composition, result, provenance, chronology, or decision changes. Stable command IDs do not authorize reuse after command text changes because the validator recomputes each SHA-256 digest.

See [`architecture/release-evidence.md`](architecture/release-evidence.md).

## 7. Build the digest-closed release bundle

`contracts/release-bundle.json` is the authoritative provider-neutral handoff manifest. The template ships in `mode: template` and claims no candidate revision, provenance, ready handoff, or artifact set.

After approved release evidence exists:

1. change the bundle document in the handoff workspace to `mode: product`;
2. record the same lowercase 40-hex candidate revision in `subject.revision`;
3. derive the expected artifact sequence from active `contracts/manifest.json` entries, excluding only `release_bundle` itself;
4. record each stable contract ID and its exact registered document path in manifest order;
5. compute SHA-256 from the exact current bytes of each listed document, including `contracts/release-evidence.json`;
6. record handoff generation provenance and a `ready` status only after release evidence is complete;
7. keep the bundle manifest outside its own `artifacts` array to avoid recursive content identity; and
8. validate both bundle entry points with the same exact candidate revision.

Example validation:

```sh
python scripts/validate_release_bundle.py --expected-revision "$CANDIDATE_SHA"
python -m scripts.validate_release_bundle --expected-revision "$CANDIDATE_SHA"
```

The manifest must be transferred with the listed files. A product-owned archive, signature, attestation, or release system may separately hash or protect the final bundle-manifest bytes after generation.

Do not conflate revision roles. The candidate revision is the source revision whose commands ran. A merge-test revision is a temporary revision used to test a proposed integration. A released revision is the source identity published by a release system. A deployed revision is the identity observed in an environment. Version 1 of `release_bundle` asserts only the candidate revision and does not claim release or deployment.

Any changed listed byte invalidates the old bundle. This includes formatting-only changes, locator changes, release-result changes, contract updates, manifest-path updates, and active-inventory changes. A retry creates new release evidence and a new bundle. A superseded ready bundle remains immutable in product-owned retention and is replaced as the current handoff; it is not rewritten. Rollback may reuse a retained bundle only when its exact candidate and bytes remain accepted by current policy, otherwise the rollback target requires new execution, release evidence, and a new bundle.

Redact before digest generation. Redacting a listed document after the bundle is written invalidates its digest. The redacted bytes must remain valid contract documents and must be used to generate a new bundle.

See [`architecture/release-bundle.md`](architecture/release-bundle.md).

### Clean-room generated-repository proof

Template maintainers exercise the complete transition in four template-maintainer-only suites:

- `tests/test_generated_repository_conformance.py` for product declarations, implementation boundaries, proof closure, and the first six validator forms;
- `tests/test_generated_release_evidence_conformance.py` for declarative release-record revision and command-digest semantics;
- `tests/test_generated_release_evidence_production.py` for isolated reviewed execution and actual release-evidence generation; and
- `tests/test_generated_release_bundle_production.py` for exact-byte bundle generation, retained records, retry, supersession, and rollback reuse.

The implementation regression creates a temporary copy of the template without `.git`, local virtual environments, or cache residue; explicitly settles copied example values as product declarations; converts only the copied implementation-evidence document to product mode; materializes repository-local boundary and proof locators; and selects a release gate that executes the authoritative fixture proof command.

The harness directly invokes reviewed fixture scripts through fixed argument vectors. It does not interpret command text from the evidence document and does not provide a reusable arbitrary-command executor. After all 52 current positive and negative implementation outcomes pass, it executes the six pre-release validator entry points from the generated repository root.

The release suites materialize or produce one exact revision, complete command and gate results, current command digests, provenance, chronology, and approval. They invoke both copied release-evidence validator entry points with the expected revision. Negative cases reject revision mismatch, command-definition drift, revision-external inputs, redirected worktrees, and actual proof failure.

The bundle suite requires approved release evidence, computes every artifact digest from exact current contract bytes in manifest order, writes an immutable retained record and a current bundle projection, and invokes both copied release-bundle validator entry points with the same expected revision. Negative and lifecycle cases reject stale contract and release-evidence bytes, different revisions, and rejected releases; they also prove append-only retry, repository-authoritative supersession, exact retained-record reactivation, and rejection of rollback reuse under changed current policy.

For invalid implementation copies, the harness invokes the copied standalone implementation-evidence validator and asserts its nonzero exit plus the expected stderr diagnostic. The false-proof case directly invokes the copied reviewed product proof. Across the four suites, generated product copies exercise all ten validator forms while keeping template source responsibility and generated product responsibility distinct. See [`architecture/generated-repository-conformance.md`](architecture/generated-repository-conformance.md).

## 8. Integrate validation into CI

Run validation from a clean, documented environment and keep commands reproducible:

1. create the product's isolated environment;
2. install the product lockfile without undeclared dependency inputs;
3. if the shipped validators are retained, create their separate isolated validator environment, install `requirements-dev.lock` or the reviewed equivalent, verify the installed distribution set, run `pip check`, invoke the six pre-release entry points, and run retained validator regressions;
4. execute every authoritative command referenced by implementation evidence directly through reviewed product workflow code, not through a generic command-string executor;
5. collect complete command and gate results for the exact candidate revision;
6. materialize product-mode release evidence and invoke both release-evidence validator entry points with that exact revision;
7. require approved release evidence before bundle generation;
8. compute the exact active-contract digests, materialize product-mode release bundle, and invoke both bundle validator entry points with the same revision;
9. require the valid ready bundle before release publication or deployment;
10. run product unit, integration, accessibility, migration, retirement, end-to-end, build, type, lint, and security checks not already represented by authoritative commands; and
11. publish diagnostics and retained evidence without exposing secrets.

A template-mode repository can run all ten validator entry points without a revision because neither release document claims a product result. A product-mode release record and bundle require the same explicit revision argument.

Keep contract validation separate from product runtime startup and deployment. A product command may start the real application, but a validator-only job should not silently depend on a local developer process, undeclared service, production credentials, provider-specific mutable ref, or remote artifact store.

## 9. Define release and deployment ownership

The generated repository owns CI configuration, deployment configuration, environment management, migrations, retirement, rollback, observability, evidence and bundle retention, signing, release approval, and release publication. Before treating it as operational, document:

- how candidate, merge-test, released, and deployed revisions are identified and related;
- how release evidence is associated with the candidate revision without a committed self-reference;
- how the bundle manifest and exact listed bytes are packaged, protected, retained, superseded, and retrieved;
- how long command, gate, contract, bundle, artifact, signature, and approval evidence is retained;
- which manifest and active contract schema versions the revision serves;
- which retired-family tombstones and migrations it preserves;
- how additive and breaking transitions are reviewed and released;
- how every backward-incompatible change is migrated;
- how stable identifiers and migration slugs are preserved or translated across a breaking transition;
- how a retiring family is removed from producers and consumers in a safe order;
- how retries and rejected runs avoid rewriting prior immutable evidence;
- how rollback reuse proves exact retained bytes and current-policy acceptance;
- how health and readiness differ from user-facing error states;
- how secrets, logs, diagnostics, evidence locators, and bundled documents are redacted before digest generation;
- how rollback preserves or restores contract compatibility without deleting required history;
- which gates block release;
- who or what records the approved decision and ready handoff; and
- where reviewers can inspect implementation boundaries, proof expectations, command results, gate results, bundle descriptors, release mappings, and deployment outcomes.

The Webapp template does not enable a deployment target, select a CI provider, choose an artifact store, or choose a production topology. Those decisions must be explicit in the generated repository and validated by its own workflow.

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
- a product-mode release bundle is materialized for the same candidate revision after release-evidence generation;
- the bundle contains every active contract except itself exactly once in manifest order;
- every bundle path and SHA-256 value matches the current registered document bytes;
- the bundle handoff status is ready;
- the isolated validator distribution set and dependency graph verify successfully;
- all ten validator entry points pass, with the same exact revision supplied for product release evidence and product release bundle;
- the retained regression suite passes with template-maintainer-only clean-room classes skipped in product source mode;
- product evidence commands pass in CI;
- build, release handoff, deployment, migration, retirement, rollback, supersession, observability, evidence retention, and release ownership are documented; and
- template-only guidance and unused alternatives have been removed.
