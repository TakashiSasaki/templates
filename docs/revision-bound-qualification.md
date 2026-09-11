# Delaying revision-bound qualification

This page explains the execution model behind the canonical `pull-request.defer-revision-bound-qualification-until-required` rule. It is explanatory guidance, not a second semantic authority. The canonical pull-request policy, repository-local requirements, release trust rules, and explicit task instructions remain authoritative.

## Why the distinction matters

Git creates an immutable commit identity for every construction step, but not every commit should immediately become a final acceptance identity. In stacked work, a lower-member repair can mechanically change descendant SHAs even when the descendants' local semantic responsibilities remain valid. If every transient descendant is deliberately treated as a final review, provenance, publication, or merge candidate, the workflow repeatedly pays exact-head CI, review, restack, and evidence-reacquisition costs for identities already expected to move.

The optimization is therefore not to avoid immutable Git objects. It is to delay **authoritative revision-bound binding** until an applicable boundary actually needs it.

## Identity lifecycle

Use four concepts when reasoning about a changing candidate:

| Concept | Meaning | Typical evidence |
| --- | --- | --- |
| Construction head | Exact commit currently representing work in progress | diff inspection, focused tests, branch topology |
| Provisional candidate | Construction state whose semantic work can proceed but whose final revision is not intentionally frozen | focused diagnostics, finding ledger state, local invariants |
| Qualification head | Intended candidate deliberately frozen because a revision-bound acceptance boundary now applies | required exact-head CI, independent review, merge readiness |
| Publication identity | Immutable revision, digest, or artifact identity made authoritative for release, provenance, distribution, or another consumer | release descriptor, provenance record, signed/pinned artifact |

A candidate may move through these concepts without introducing new Git object types. The distinction is semantic: it describes what the current exact identity is being relied upon to prove.

## Construction phase

During dependency-safe construction, continue useful implementation and focused validation even when an upstream member is not yet permanently stable. A downstream pull request may have an exact current head and a complete local delta while still remaining provisional.

Appropriate construction-phase work includes:

- implementing downstream logic that does not embed a known-invalid upstream assumption;
- focused unit, invariant, schema, or regression tests;
- self-audit and review-finding disposition;
- pull-request creation and explicit stack topology;
- naturally triggered CI; and
- preserving semantic evidence whose actual bindings remain unchanged.

A successful automatic CI run on a provisional head is useful observable evidence, but it does not by itself mean the workflow intentionally entered or completed final qualification.

## Freeze point

Freeze the intended qualification identity when an applicable authority-defined boundary now requires exact-revision evidence. Common freeze points include:

- intentional merge-acceptance review;
- final whole-stack audit when explicitly required by the task;
- merge-readiness evaluation;
- provenance or generated material that embeds an upstream exact revision;
- release promotion;
- installer or artifact publication; and
- another externally authoritative revision-bound operation.

At that point, stabilize the actual prerequisite identities, freeze the intended head or ordered stack heads, and acquire every exact-revision check required by the applicable authority. Delayed qualification never replaces those requirements.

## Stacked pull requests

For an ordered stack `A -> B -> C`, suppose `A` still requires a semantic repair while `B` and `C` can continue dependency-safe implementation.

The preferred construction model is:

```text
A: repairing
B: provisional local delta complete
C: provisional local delta complete
```

After the known compatible work converges:

```text
A*: stable candidate
B*: rebased/restacked only as actually required
C*: rebased/restacked only as actually required
```

Only when the next authority boundary requires revision-bound evidence are `A*`, `B*`, and `C*` intentionally treated as qualification heads and subjected to the applicable full exact-head qualification.

An ancestry change does not justify discarding semantic reasoning that is still applicable. It does invalidate evidence that was explicitly bound to the former exact revision. Re-evaluate bindings selectively rather than treating the entire work history as one indivisible snapshot.

## Review findings

Separate a finding's semantic repair state from its qualification freshness. A repair can be understood, applied, and supported by focused diagnostics while the descendant remains provisional. If later ancestry movement changes the exact head without invalidating the repair, preserve the finding identity and semantic disposition, mark revision-bound evidence stale only where necessary, and complete exact-head qualification when the applicable review or merge boundary is reached.

Before intentionally reacquiring merge-acceptance review, the existing canonical known-finding rule still applies: every known material actionable finding needs the required current-head validated outcome and closure evidence. Delayed qualification does not permit an unresolved finding backlog to be hidden behind a provisional-state label.

## Release and publication

The policy repository's existing candidate/promotion model is the clearest example of delayed immutable materialization. Candidate source is implemented and reviewed first; a later promotion change records the already-known full candidate SHA in release descriptors. Installer publication likewise writes the immutable installer/source identity only after those candidate identities exist.

Do not generalize this into mutable publication references. Once a revision becomes part of an executable, release, provenance, or distribution contract, use the immutable identity required by that contract.

## Anti-patterns

Avoid these patterns when no authority boundary requires them:

- treating every pushed descendant SHA as a final whole-stack candidate;
- deliberately reacquiring full review between compatible known repairs;
- rematerializing provenance that is already known to become stale after an upstream repair;
- rewriting an upper head solely to make it look fresh after an unrelated lower merge; and
- converting diagnostic metrics such as CI count or candidate-head count into new acceptance gates.

The opposite error is also invalid: do not skip required full qualification merely because focused diagnostics passed.

## Safety and operational exceptions

Do not delay a justified repair when waiting would create a concrete security, operational, data-integrity, or publication-integrity risk. Candidate stabilization and mutation batching are efficiency disciplines; they never make a known-defective state acceptable.

Likewise, when an authority-defined freeze point has already been reached, use the required immutable binding immediately. The principle is "bind late enough to avoid predictable churn," not "avoid immutable identity."

## Practical decision rule

Before deliberately starting a revision-bound evidence cycle, ask two questions:

1. **Which authority-defined operation needs this exact identity now?**
2. **Are any known prerequisite mutations still expected to change that identity or the material derived from it?**

If no current boundary needs the immutable binding, keep the work provisional and continue focused validation. If a boundary does need it, stabilize the prerequisites, freeze the qualification head, and perform the required exact-revision qualification.

## Applicability classification

Required exact-head qualification does not mean every repository verification must execute for every candidate when repository authority has a safe way to prove that a verification is not applicable. Treat applicability classification as a separate evidence-producing step: bind the decision to the exact candidate and comparison inputs, the classifier or dependency-map definition, and the verification definition whose applicability is being decided.

A classified `not-applicable` result is not a successful test result. It means the repository has current evidence that the verification does not apply to that candidate. If the diff, classifier inputs, dependency relation, or classifier definition cannot be established safely, classify conservatively and run the verification. Changes to classification controls must not silently use the changing classifier to exempt themselves.

This distinction supports three useful execution modes without weakening acceptance:

- focused **diagnostic** validation during construction, which is optimized for rapid falsification;
- repository-defined **conditional automatic verification**, where a fail-closed applicability classifier can avoid work that provably does not apply; and
- complete **qualification** at the revision-bound boundary, consisting of every check that is applicable under the current repository definition.

Applicability decisions should be observable. Record the candidate/base bindings, classification mode, verification classes selected or omitted, and stable reasons for those decisions. These records are operational evidence and diagnostics, not new acceptance gates. An explicit repository-controlled full-verification checkpoint may override a selective result when broader qualification is desired.

For pull-request-driven repositories, avoid duplicate automatic qualification when the same candidate would otherwise be validated once for a feature-branch push and again for the pull-request event without any change in the candidate. A repository may reserve push-triggered full qualification for its authority branch while using pull-request-triggered qualification for proposed changes, provided required checks remain observable on the proposed exact head and direct authority-branch changes still receive the required verification.

## Qualification evidence applicability and reuse during stacked landing

When landing stacked pull requests base-to-tip sequentially, mechanical full CI reruns on each member after each merge introduce significant latency and resource waste. Policy establishes the canonical principle governing evidence validity during stacked landing:

> **Merge progression does not itself invalidate qualification evidence. A change to the qualified candidate state or to an evidence binding does.**

This principle ensures that existing verification evidence is rigorously evaluated for continued applicability to the current candidate. If evidence remains valid, it is reused; if it has become invalid, only the affected validations are reacquired.

### Qualification applicability check

Before scheduling new CI or validation runs during stacked landing, evaluate existing qualification evidence against the candidate. The applicability check compares at least:

1. **Qualification candidate**: the logical candidate revision and its role.
2. **Current head**: the current commit SHA of the proposed branch.
3. **Effective tree identity**: the Git tree SHA of the candidate worktree.
4. **Base evolution**: whether the target base moved and how the base was integrated.
5. **Validation-run bound identity**: the specific candidate identity, comparison inputs, and environment to which the validation run was bound.
6. **Exact-head and exact-tree bindings**: whether the check required exact-commit or exact-tree equivalence.
7. **Provider revision**: the revision of external or host provider integrations.
8. **Cross-authority revision**: the revision of referenced external authority repositories.
9. **Generated or materialized state**: whether generated outputs, projections, or schemas match the source definition.
10. **Dependency, lockfile, and toolchain identity**: whether dependency specifications, locked packages, or compiler/runtime toolchains changed.
11. **Validation workflow identity**: whether `.github/workflows/**` or underlying test scripts were modified.
12. **Repository required-check policy**: whether branch protection, rulesets, or required merge-result checks enforce mandatory fresh execution.

The applicability check produces one of three distinct outcomes:

| Outcome | Meaning | Action |
| --- | --- | --- |
| **`applicable`** | The effective candidate tree and all required evidence bindings are intact and unchanged. | Reuse the existing qualification evidence without re-executing CI. |
| **`stale`** | A tree change, conflict resolution, binding breach, or dependency/workflow modification invalidated the check. | Invalidate the affected evidence and selectively reacquire only the necessary validation. |
| **`unknown`** | Applicability cannot be verified with certainty or bindings are ambiguous. | **Fail closed**: treat evidence as stale and reacquire. Unknown is never treated as applicable (unknown must never be treated as applicable). |

### Conditions for evidence reuse

Existing qualification evidence may be reused when all of the following conditions are satisfied:

- The effective candidate tree is identical to the qualified candidate tree.
- No conflict resolution occurred during ancestor landing or rebase.
- Generated or materialized output is unchanged.
- Dependencies, lockfiles, and toolchain definitions are unchanged.
- The validation workflow identity is unchanged.
- Provider and cross-authority revisions are unchanged.
- Exact-head, exact-tree, and all other bindings required by the evidence continue to hold.
- Repository provider rulesets, branch protection, or required merge-result policies do not mandate a fresh check.

### Concrete invalidation triggers

Qualification evidence is marked `stale` upon any of the following events:

- **Conflict resolution**: any non-trivial or content-modifying merge or rebase resolution.
- **Effective tree change**: any difference in the resulting Git tree object.
- **Generated or materialized output change**: any delta in generated files, documentation builds, or lockfiles.
- **Dependency, lockfile, or toolchain change**: any modification to dependencies, package versions, or build environments.
- **Validation workflow change**: changes to the workflow or script definitions that generated the evidence.
- **Provider revision change**: updates to external provider plugins, actions, or hosting configurations.
- **Cross-authority revision change**: changes in referenced authority branches or submodules.
- **Breach of exact-head, exact-tree, or immutable bindings**: invalidation of explicit constraints demanded by the check.
- **Qualification input change**: any modification to inputs declared by the validation contract.

### History-only changes

History-only evolution—including ancestor pull-request landing, history-only rebases, tree-identical head movement, and commit-graph restructuring—does not automatically invalidate qualification evidence solely because the commit SHA changed. 

However, if an evidence item explicitly binds to an exact commit SHA (for example, a cryptographic commit signature check, commit-message linter, or provenance binding that embeds the commit hash), that binding semantics must be respected. Tree identity alone does not waive explicit exact-commit bindings.

### Selective invalidation vs full CI rerun

When evidence becomes stale, **running the full validation or CI suite is not the default**. 

The workflow must isolate the affected validation or binding and **rerun only what is required to restore qualification**. Unaffected validations whose bindings remain intact continue to be reused.

### Review evidence boundary

> **Reuse of qualification or CI evidence does not by itself imply reuse of review evidence. Review applicability continues to follow the repository's existing review policy.**

Qualification evidence and review evidence serve distinct governance roles. Even when CI evidence remains applicable across tree-identical history evolution, merge-acceptance review requirements remain governed by the repository's review policy (such as `pull-request.require-independent-exact-head-review` and `pull-request.bind-review-result-classification-to-applicable-cycle-and-revision`).

---

### Acceptance scenarios and examples

#### Case A — Ancestor merge, tree unchanged
In an ordered stack `A -> B -> C`, candidate `C` had full integrated qualification CI completed prior to landing. Member `A` is merged into the base branch. Member `B`'s base is updated to the newly landed `A`. The effective candidate tree of `B` and its required evidence bindings are unchanged.
- **Evaluation**: The ancestor merge alone does not invalidate `B`'s qualification evidence.
- **Expected action**: Do not rerun the full CI suite on `B`. Reuse applicable qualification evidence and proceed.

#### Case B — History changes, tree unchanged
A stack member undergoes a history-only rebase or parent commit advance, resulting in a new commit SHA. However, the Git tree identity and all relevant evidence bindings are identical.
- **Evaluation**: A commit SHA change alone does not trigger full requalification.
- **Expected action**: Reuse applicable qualification evidence whose tree and context bindings hold. If an exact-commit binding exists (e.g. commit linting), rerun only that specific check.

#### Case C — Conflict resolution
Following ancestor landing, updating the next stack member requires conflict resolution that modifies files in the candidate tree.
- **Evaluation**: The effective tree changed, invalidating previous qualification evidence bound to the prior tree.
- **Expected action**: Mark the affected qualification evidence as stale. Reacquire the affected validation runs.

#### Case D — Cross-authority or provider revision changes
A candidate's local source tree appears unchanged, but an external provider revision or cross-authority binding (e.g. toolchain revision or submodule pointer) changed.
- **Evaluation**: The cross-authority evidence binding is broken and marked stale.
- **Expected action**: Rerun the corresponding cross-authority integration validation without running unrelated unaffected suites.

#### Case E — Validation workflow changed
The pull request modifies `.github/workflows/ci.yml` or the classifier script that generates the evidence.
- **Evaluation**: Evidence generated by the previous workflow definition cannot be reused to qualify the new workflow.
- **Expected action**: Mark prior evidence stale and execute the updated validation workflow.

#### Case F — Repository provider requires fresh merge-result check
Repository branch protection or ruleset configuration enforces required status checks evaluated specifically on the fresh merge commit or head ref before merge authorization.
- **Evaluation**: Hosting platform enforcement takes precedence over policy reuse optimizations.
- **Expected action**: Execute the required checks mandated by the platform ruleset to satisfy the provider merge gate.
