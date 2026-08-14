# Universal regression-prevention policy

This page collects recurring regressions observed when coding agents are used across multiple repositories and the countermeasures that proved effective without depending on a specific language, framework, product, or UI implementation.

`policy/core/` contains only short normative rules intended to appear directly in generated agent instructions. This page is non-normative explanatory material covering the rationale for those rules, their applicability boundaries, and their relationship to machine enforcement.

## Adoption criteria

A principle belongs in universal policy only when it normally satisfies all of these conditions:

1. The same failure pattern has been observed in multiple repositories or different categories of change.
2. The rule applies to general software changes without assuming a specific technology stack.
3. It can be expressed concisely as an instruction an agent can execute.
4. Compliance can be checked through evidence such as diffs, tests, generated differences, the current revision, or the state of the mutation target.
5. It closes a concrete failure path rather than encouraging broad exploration or unrelated work.

## Principles included in the core profile

### Establish the change contract first

Naming only the files or subsystem to change leaves preserved behavior, non-goals, and acceptance evidence implicit and makes it easier for an agent to expand scope for implementation convenience. Before editing, identify:

- requested outcome;
- allowed change surface;
- preserved behavior and invariants;
- explicit non-goals; and
- acceptance evidence.

Treat unspecified existing behavior as preserved unless the requested change necessarily requires altering it. This is represented by the combination of `changes.define-contract` and `changes.minimize-scope`.

### Do not move the acceptance baseline during execution

Even after defining a change contract, retroactively expanding scope, non-goals, completion criteria, required evidence, or stopping conditions during implementation or audit destroys completion stability and can invalidate earlier evidence. `changes.preserve-acceptance-baseline` freezes the baseline after work starts and treats rebaselining as an explicit owner decision.

When a rebaseline is necessary, record at least:

- the baseline item being changed;
- why it is changing;
- the effect on work already completed;
- whether earlier verification remains valid; and
- the new stopping condition.

An audit may discover new requirements, but those requirements must not automatically be applied retroactively to the current work. Defer them to another work unit or rebaseline explicitly.

### Do not resolve semantic ambiguity by guessing

Agents can decide small implementation details, but choices that alter observable behavior, data meaning, compatibility, architecture, risk, or scope are owner decisions. `decisions.escalate-semantic-ambiguity` requires more than asking a bare question: identify the viable options, trade-offs, impact, recommendation, and decision required, then stop the dependent change.

This rule does not require confirmation for every minor implementation detail. It gates only choices that change the meaning or contract of the result.

### Capture discovered failures as regression tests

In addition to preserving existing tests, a reproducible defect fix should add a test that fails before the fix and passes after it. Capturing the actual discovered counterexample provides more direct protection against recurrence than merely increasing the number of tests.

When reproduction is environment-dependent or nondeterministic, do not report inability to reproduce as success. Report the hazardous condition, the defense added, and the alternative verification that was executed.

### Distinguish executing verification from passing verification

Starting a command, having a workflow configured, or having a review rule present does not mean the current change has been verified. Verification results should distinguish at least:

- passed;
- failed;
- pending;
- skipped;
- not triggered;
- stale for the current revision;
- blocked by the environment; and
- inspected or inferred only.

Also confirm that the required verification actually covers the change surface. Do not use an aggregate command or green CI status as a substitute for tests that were omitted, workflows excluded by path filters, or results produced for an older commit.

### Do not substitute one evidence layer for another

`verification.separate-evidence-layers` binds a verification result both to the exact revision or artifact and to the layer that produced it. At minimum, distinguish:

- repository-local checks;
- environment-dependent checks;
- remote CI; and
- independent audit.

For example, a passing local validator does not prove that remote CI ran, and passing remote CI does not prove independent-audit acceptance. Schema validation, filesystem validation, transfer hashes, and semantic acceptance are also distinct claims.

### Keep canonical sources and derived artifacts synchronized

Generated files, duplicated configuration, compiled assets, manifests, fixtures, and published documentation can become stale after their canonical inputs change. For related changes, use the repository-defined generation or synchronization procedure and verify that no missing or unexpected difference remains.

Do not rely solely on human or agent attention for synchronization. When possible, enforce it with generator check modes, post-regeneration diffs, hashes, schema validation, or CI exact-match checks.

### Revalidate state immediately before destructive actions

For deletion, overwrite, migration, deployment, publication, force updates, and similar mutations, state observed at task start may no longer be valid at execution time. Immediately before the operation, revalidate at least target identity, scope, revision, protection state, and conflicting use.

Prefer dry runs, minimum scope, and idempotent operations when possible. Do not authorize a destructive operation by inferring global current state from an earlier search result or a local intermediate result.

### Limit rollback to changes owned by the current operation

In multi-stage mutations, cleanup that deletes a file created by another process or a file that existed before the task is itself a regression. `safety.limit-rollback-to-owned-changes` requires preflight before the first write, live-state revalidation at the commit boundary, and tracking of paths created or changed by the current operation.

Rollback only changes whose ownership by the current operation is known. Do not delete or overwrite files created concurrently, files that predated the operation, or referents not modified by the current operation under the label of cleanup.

### Preserve external contracts and truthful reporting

Public APIs, storage formats, configuration formats, CLIs, migration paths, and other external contracts are preserved unless an incompatible change is explicitly authorized. Reporting must also distinguish implemented, generated, executed, verified, and inferred states; unverified work must not be reported as complete.

## Items separated into optional profiles

Receiving external archives, historical source, vendor bundles, generated artifacts, and similar material requires additional policy about provenance, digests, archive paths, declared intent, exact-byte staging, and dependency closure. These concerns do not apply to every change and therefore belong in the `external-artifact-intake` profile.

See [External artifact intake policy profile](external-artifact-intake.md) for the concrete rules and validation order. Product-specific manifest schemas, source allowlists, destination mappings, and activation gates remain in product-repository policy and validators.

## Natural-language policy and machine enforcement

Natural-language policy is a shared contract for agent judgment, but merely documenting a rule does not make it an integration gate. Where possible, mechanize requirements in this order:

1. repository-specific tests or validators;
2. generator check modes and diff checks;
3. CI status for the current commit;
4. required checks or required reviews; and
5. precondition checks immediately before mutation.

`agent-policy` itself validates consistency between generated instructions and lock state. Product-specific invariants and acceptance tests remain enforced by product-repository tests and CI.

## Items not included in core

The following practices can be useful, but their applicability depends on a technical domain and they are therefore not universal core policy at this time:

- rechecking a request ID or selected object after each `await` in asynchronous UI code;
- not waiting for an auxiliary display feature before basic functionality;
- a specific choice between fail-open and fail-closed behavior;
- mandatory CODEOWNERS or specific reviewers;
- universally running every platform, package, and test suite;
- universally requiring fuzzing, formal methods, or a particular coverage percentage; and
- universally requiring a specific archive format, hash algorithm, or signature format.

These are better expressed in frontend, workflow, database, release, security, artifact-intake, or other domain profiles, or as product-repository-specific policy.

## Minimal task-specific contract

Separate from permanent policy, an individual task can specialize the core rules by stating:

```text
Outcome:
Allowed changes:
Preserved invariants:
Non-goals:
Acceptance evidence:
Destructive or externally visible actions:
Stop condition:
```

Do not accumulate this task contract into permanent policy. Keep it in an issue, pull request, work instruction, or temporary task document.
