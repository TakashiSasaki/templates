# Webapp template completion roadmap

This roadmap tracks the repository-level work remaining after reviewed execution can produce release evidence bound to the actual immutable generated-product revision. It does not select a framework, package manager, backend, authentication provider, CI provider, artifact store, or deployment platform.

It is not a product backlog. Product-specific implementation, browser support, infrastructure, deployment, observability, approvals, and evidence retention remain the responsibility of each generated repository.

## Completed foundation

The `webapp` history provides:

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

## Completed release-evidence foundation

Contract family `release_evidence` version 1 adds:

- template mode with no product release claims;
- product mode identifying one exact immutable candidate revision;
- exactly one result for every registered release gate;
- exactly one result for every command executed by those gates;
- SHA-256 binding from each command result to current authoritative command text;
- rejection of failed commands, nonzero exit codes, failed gates, stale revisions, digest drift, invalid chronology, and non-approved decisions;
- standalone and module release validators;
- eight total validator entry points across contracts, evolution, implementation evidence, and release evidence;
- clean-room exact-revision and command-definition conformance; and
- synchronized README, template, operationalization, architecture, and validation guidance.

This foundation validates a completed release record. It intentionally does not execute arbitrary command strings or choose how a product stores, signs, approves, or deploys that record.

## Completed Phase 2: evidence-production conformance

The clean-room generated repository now proves that a completed release record can be produced from actual reviewed execution rather than asserted result values.

The template-maintainer-only fixture:

1. installs a release producer only in the temporary generated repository;
2. initializes a fresh Git repository and commits the complete generated-product state;
3. supplies the resulting immutable commit revision to the producer;
4. launches the producer in Python isolated mode before repository-local startup imports can run;
5. rejects non-isolated producer startup as defense in depth;
6. removes inherited Git inputs and disables system and global Git configuration;
7. verifies that the effective Git directory is the generated root `.git` and the effective top-level worktree is the generated repository root;
8. rejects local `core.worktree` redirection before trusting cleanliness results;
9. pins subsequent Git commands with explicit `--git-dir` and `--work-tree` arguments and disables fsmonitor, untracked-cache, ignore-stat, and sparse-checkout behavior;
10. verifies that `HEAD^{commit}` equals the supplied revision;
11. rejects tracked changes and ordinary untracked files;
12. separately rejects ignored untracked files through `git ls-files --others --ignored --exclude-standard`;
13. requires the exact reviewed command and release-gate registrations;
14. invokes the known proof script through the fixed isolated argument vector `[sys.executable, "-I", "product/prove_conformance.py"]`;
15. captures actual stdout, stderr, exit code, start time, and completion time;
16. calculates the digest of the exact authoritative command text;
17. derives gate status and release decision from the actual command result;
18. writes a repository-local result artifact and product-mode release evidence;
19. validates approved evidence through both copied release validator entry points; and
20. proves that a failed command committed as its own candidate revision produces a rejected decision and cannot satisfy release validation.

A mismatched revision, a tracked or ordinary untracked generated-tree change, an ignored revision-external file, a repository-local bytecode import opportunity, a redirected Git worktree, and command-registration drift are rejected before proof execution. The producer accepts no command text, executable, argument vector, environment, working directory, gate choice, or Git ref and is not a repository command dispatcher. Real products remain responsible for directly executing their selected reviewed commands and establishing equivalent interpreter, Git metadata, worktree, and revision-external-input boundaries in product-owned CI.

## Remaining Phase 3: release-artifact and handoff closure

The next gap is provider-neutral definition and conformance for handing completed evidence to release or deployment systems.

Required outcomes:

- define the minimum immutable evidence bundle: contract documents, candidate revision, command and gate results, provenance, decision, and reviewable locators;
- explain how to avoid self-referential committed evidence;
- distinguish candidate revision, merge-test revision, released revision, and deployed revision;
- define when a new record is mandatory after source, command, gate, contract, or evidence-policy changes;
- define product-owned retention, signing, attestation, approval, and redaction boundaries;
- define release rejection, retry, supersession, and rollback evidence expectations; and
- add clean-room diagnostics for stale, mismatched, or superseded bundles where these can be verified locally without choosing a provider.

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
- generated-repository setup, implementation evidence, actual evidence production, release handoff, migration, retirement, rollback, and completion checklists form one coherent workflow;
- intentionally product-owned concerns are clearly separated from missing template work; and
- current-head CI passes, Codex reports no unresolved valid findings, and all review threads are resolved.

## Completion decision

The `webapp` branch can be considered complete when Phases 3 and 4 are merged and no remaining gap requires a framework-neutral, repository-authoritative, locally verifiable contract or conformance check.

Further additions should then be driven by concrete generated-repository failures. They must satisfy the contract-family criteria in [`contract-completeness.md`](contract-completeness.md) rather than expanding the template speculatively.
