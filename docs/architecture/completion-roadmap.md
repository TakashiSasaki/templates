# Webapp template completion roadmap

This roadmap tracks the remaining repository-level work needed to satisfy the Webapp template goal without selecting a framework, package manager, backend, authentication provider, CI provider, artifact store, or deployment platform.

It is not a product backlog. Product-specific implementation, browser support, infrastructure, deployment, observability, approvals, and evidence retention remain the responsibility of each generated repository.

## Completed foundation

The `webapp` history already provides:

- closed manifest registration for active and retired contract families;
- contiguous contract and bootstrap version histories;
- stable migration slugs and closed migration-artifact validation;
- browser-facing surface contracts;
- canonical route and access-failure contracts;
- route-scoped and global UI-state ownership;
- viewport, zoom, reflow, orientation, and input-capability declarations;
- universal positive and negative implementation-evidence obligations;
- product-mode implementation boundaries, authoritative commands, release-gate definitions, and gate closure;
- isolated and locked validation-toolchain bootstrap;
- standalone and module validator entry points;
- clean-room generated-repository implementation conformance; and
- current-head CI and Codex review discipline.

PR #60 completed Phase 1 by proving that a copied template can become a product-mode repository, execute a reviewed fixture proof, pass the retained implementation validators, and fail deterministically when implementation evidence is incomplete or inconsistent.

## In progress: revision-bound release evidence

The current phase adds contract family `release_evidence` version 1.

Completion criteria for this phase are:

- template mode contains no product release claims;
- product mode identifies one exact immutable candidate revision;
- every registered release gate has one result;
- every command executed by those gates has one result;
- command results are bound to current authoritative command text by SHA-256;
- failed commands, nonzero exit codes, failed gates, stale revisions, digest drift, invalid chronology, and non-approved decisions fail validation;
- standalone and module release validators pass in template and generated product modes;
- the complete CI surface consists of eight validator entry points;
- clean-room release conformance proves exact-revision and command-definition binding; and
- README, operationalization, architecture, and completion guidance agree.

## Remaining Phase 2: evidence-production conformance

The release contract validates a completed record; it intentionally does not execute arbitrary command strings. The next gap is proving that a generated repository can safely produce the record from actual reviewed command execution rather than from asserted pass values.

Recommended implementation:

1. add a template-maintainer-only clean-room release runner for the known fixture command only;
2. invoke the reviewed fixture proof through a fixed argument vector;
3. capture start time, completion time, exit code, command digest, and result locator from that invocation;
4. derive the fixture gate result from the captured command result;
5. emit product-mode release evidence for an explicitly supplied fixture revision;
6. validate the emitted record through both copied release validator entry points; and
7. add negative tests proving that a failed fixture command cannot produce an approved release.

Do not generalize this into a repository command dispatcher. Real products execute their selected commands directly in product-owned CI.

## Remaining Phase 3: release-artifact and handoff closure

After actual evidence production is proven, the template needs provider-neutral guidance and conformance for handing the completed record to release or deployment systems.

Required outcomes:

- define the minimum immutable evidence bundle: contract documents, candidate revision, command and gate results, provenance, decision, and reviewable locators;
- explain how to avoid self-referential committed evidence;
- distinguish candidate revision, merge-test revision, released revision, and deployed revision;
- define when a new record is mandatory after source, command, gate, or contract changes;
- define product-owned retention, signing, attestation, approval, and redaction boundaries;
- define release rejection, retry, supersession, and rollback evidence expectations; and
- add clean-room diagnostics for stale or superseded evidence where these can be verified locally without choosing a provider.

A new contract family is not automatically required. Extend `release_evidence` only if the accepted document structure or semantic obligations actually change.

## Remaining Phase 4: final template readiness audit

The final phase is a cross-repository consistency and usability audit rather than a feature expansion.

The audit must verify:

- every active contract, schema, validator, test, migration, and architecture document agrees on identifiers, versions, modes, and responsibilities;
- all examples are either explicit template requirements or explicit product declarations;
- all validator entry points are documented and exercised in CI and clean-room fixtures;
- template-maintainer-only tests skip safely in generated product repositories;
- no framework, package manager, backend, authentication provider, CI provider, or deployment platform has been selected implicitly;
- no generic arbitrary-command executor exists;
- no `policy`, `main`, or `site` content has entered the unrelated `webapp` history;
- generated-repository setup, implementation evidence, release evidence, migration, retirement, rollback, and completion checklists form one coherent workflow;
- intentionally product-owned concerns are clearly separated from missing template work; and
- current-head CI passes, Codex reports no unresolved valid findings, and all review threads are resolved.

## Completion decision

The `webapp` branch can be considered complete when Phases 2 through 4 are merged and no remaining gap requires a framework-neutral, repository-authoritative, locally verifiable contract or conformance check.

Further additions should then be driven by concrete generated-repository failures. They must satisfy the contract-family criteria in [`contract-completeness.md`](contract-completeness.md) rather than expanding the template speculatively.
