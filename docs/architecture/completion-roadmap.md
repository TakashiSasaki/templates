# Webapp template completion roadmap

This roadmap tracks the repository-level work remaining after reviewed execution can produce release evidence and a digest-closed handoff bundle bound to the actual immutable generated-product revision. It does not select a framework, package manager, backend, authentication provider, CI provider, artifact store, or deployment platform.

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
- eight validator entry points at the release-evidence stage across contracts, evolution, implementation evidence, and release evidence;
- clean-room exact-revision and command-definition conformance; and
- synchronized README, template, operationalization, architecture, and validation guidance.

This foundation validates a completed release record. It intentionally does not execute arbitrary command strings or choose how a product stores, signs, approves, or deploys that record.

## Completed Phase 2: evidence-production conformance

The clean-room generated repository proves that a completed release record can be produced from actual reviewed execution rather than asserted result values.

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

## Completed Phase 3A: release-bundle contract foundation

PR #68 introduced the provider-neutral handoff manifest required after approved release evidence exists.

The `release_bundle` version 1 foundation defines:

- template mode with no candidate, provenance, handoff, or artifact claims;
- product mode for one explicit candidate revision;
- equality with both the validator's expected revision and `release_evidence.subject.revision`;
- one deterministic artifact descriptor for every active domain contract except the bundle manifest itself;
- exact contract identity, manifest path, manifest order, and SHA-256 binding to current file bytes;
- inclusion of release evidence as a digest-bound artifact;
- bundle generation after release-evidence generation;
- a provider-neutral `ready` handoff statement;
- explicit exclusion of self-digest recursion; and
- standalone and module validator entry points, bringing the retained validator surface to ten forms.

The architecture distinguishes candidate, merge-test, released, and deployed revision roles without pretending that pre-release repository validation proves release or deployment. It also defines mandatory regeneration, rejection, retry, supersession, rollback, signing, retention, approval, and redaction boundaries.

## Completed Phase 3B: bundle production and lifecycle conformance

PR #75 proves in the temporary generated-repository clean room that the bundle is generated from the exact approved artifact set rather than from asserted digest values.

The fixture:

1. installs a bundle producer only in the temporary generated repository before the candidate revision is committed;
2. requires Python isolated startup for the producer itself;
3. removes inherited Git inputs, disables system and global Git configuration, verifies the effective Git directory and worktree, and pins subsequent Git operations;
4. requires `HEAD^{commit}` to equal one explicit lowercase 40-hex candidate revision;
5. permits only the known release evidence, current bundle, release-run, bundle-index, and retained-record outputs after candidate verification;
6. requires valid approved release evidence for the same candidate revision;
7. reads the active contract registry in manifest order and calculates SHA-256 from each exact current document byte sequence;
8. excludes the bundle document itself to avoid recursive content identity;
9. writes one immutable repository-local bundle record and copies those exact bytes to `contracts/release-bundle.json` as the current handoff;
10. validates the generated bundle through both copied release-bundle entry points;
11. records one repository-authoritative `current` record and marks the previous current record `superseded` without rewriting retained bundle bytes;
12. makes each retry append a distinct record;
13. reactivates a retained record only when its exact retained bytes, candidate revision, index digest, and current validator policy still agree; and
14. restores the previous current bundle and leaves the index unchanged when retained-record activation is rejected.

The regression suite proves rejection of changed active-contract bytes, changed release-evidence bytes, a different candidate revision, and failed or rejected release execution. It also proves append-only retry, explicit supersession, exact rollback reuse, and mandatory new evidence when a retained bundle is stale under current policy.

The producer accepts no arbitrary command, path, executable, environment, provider, archive, signature, publication target, deployment target, or remote locator. Product repositories remain responsible for durable retention, signing or attestation, approval, encryption, redaction, publication, deployment, and environment observation.

## Completed Phase 4: final template readiness audit

PR #82 records the final cross-repository consistency and usability audit in [`final-readiness-audit.md`](final-readiness-audit.md) and adds a regression that keeps the audit evidence, CI validator surface, branch terminology, and completion state synchronized.

The audit verifies:

- every active contract, schema, validator, test, migration, and architecture document agrees on identifiers, versions, modes, and responsibilities;
- all examples are either explicit template requirements or explicit product declarations;
- all ten validator entry points are documented, exercised in CI, and exercised across the generated-repository clean-room fixtures;
- template-maintainer-only tests skip safely in generated product repositories;
- no framework, package manager, backend, authentication provider, CI provider, artifact store, or deployment platform has been selected implicitly;
- no generic arbitrary-command executor exists;
- the unrelated `skill`, `site`, and `policy` histories have no common ancestor with `webapp` and have not entered this branch;
- generated-repository setup, implementation evidence, actual evidence production, release-bundle handoff, migration, retirement, retry, supersession, rollback, and completion checklists form one coherent workflow;
- intentionally product-owned concerns are separated from missing template work; and
- current-head CI and fully resolved review remain required merge evidence recorded on the pull request.

The audit found and closed two repository-level completion gaps: the absence of one durable Phase 4 evidence record and the remaining old `main` branch name in this roadmap after the live branch was renamed to `skill`. It found no missing framework-neutral contract or conformance capability.

## Completion decision

With Phase 4 merged after successful current-head CI and resolved review, the `webapp` branch is complete for its stated framework-neutral template scope. No identified gap requires another repository-authoritative, locally verifiable contract or conformance check.

Further additions should be driven by concrete generated-repository failures. They must satisfy the contract-family criteria in [`contract-completeness.md`](contract-completeness.md) rather than expanding the template speculatively.
