---
id: pull-request.reuse-valid-exact-head-evidence
severity: mandatory
overridable: true
order: 975
---
# Reuse valid pull-request evidence until an applicable binding changes

Once scope, validation, review, or other acceptance evidence has been accepted for a defined proposed-head identity and applicability context, reuse that evidence while the facts that bind it remain unchanged.

Do not make repeated observations, extra review cycles, waiting periods, or redundant evidence collection mandatory solely because they are more conservative. Additional diagnostic work may be performed when concrete uncertainty exists, but it must not silently enlarge the acceptance baseline or become a new merge requirement unless current repository policy requires it.

Reacquire only the evidence affected by a concrete invalidation signal. Target-branch movement requires impact evaluation, but it does not by itself invalidate unrelated exact-head evidence whose applicability and semantic basis remain unchanged. Changes to scope, validation definitions, review state, or another evidence-binding condition invalidate the corresponding evidence. Elapsed time alone does not invalidate exact-head evidence unless current repository policy defines an explicit freshness limit.

During stacked pull-request progression and candidate landing, **merge progression does not itself invalidate qualification evidence. A change to the qualified candidate state or to an evidence binding does.** Merely because an ancestor member of a stack was merged, subsequent members' CI or qualification evidence must not be treated as stale solely for that reason. Before scheduling or executing new validation, perform an explicit **qualification applicability check** comparing the qualification candidate, current head, effective tree identity, base evolution, validation-run bound identity, exact-head and exact-tree bindings, provider revision, cross-authority revision, generated or materialized state, dependency, lockfile, and toolchain identity, validation workflow identity, and repository required-check policy.

An applicability check must distinguish at least three outcomes: **applicable**, **stale**, and **unknown**. If applicability is unknown or cannot be positively verified, keep evaluation fail-closed and treat the evidence as requiring reacquisition; unknown must never be treated as applicable.

Existing qualification evidence may be reused when:
- the effective candidate tree is identical;
- no conflict resolution occurred;
- generated or materialized output is unchanged;
- dependency, lockfile, and toolchain identities are unchanged;
- the validation workflow identity is unchanged;
- provider and cross-authority revisions are unchanged;
- exact-head, exact-tree, and all other bindings required by the evidence continue to hold; and
- repository hosting provider rulesets, branch protection, or required merge-result policies do not mandate a fresh check.

Qualification evidence is stale and must be reacquired upon concrete invalidation:
- conflict resolution;
- effective tree change;
- generated or materialized output change;
- dependency, lockfile, or toolchain change;
- validation workflow change;
- provider revision change;
- cross-authority revision change;
- breach or destruction of an exact-head, exact-tree, or immutable binding; or
- change in qualification input.

History-only evolution—such as ancestor pull-request landing, history-only rebase, tree-identical head movement, or commit-graph reorganization—does not automatically invalidate qualification evidence solely because the commit SHA changed. However, when evidence explicitly binds to an exact commit SHA, that binding semantics must be respected; an identical tree alone does not waive explicit exact-commit bindings.

When evidence becomes stale, running the full validation or CI suite is not the default. Selective invalidation requires identifying the affected validation or binding and rerun only what is required to restore qualification.

Reuse of qualification or CI evidence does not by itself imply reuse of review evidence. Review applicability continues to follow the repository's existing review policy, and merge-acceptance review requirements remain governed by their applicable review contract.

If the continued validity of relied-upon evidence cannot be established, fail closed and reacquire the affected evidence rather than inventing a broader gate.
