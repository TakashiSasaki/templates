<!-- agent-policy-generated: true -->
# Staged CI execution

This reference projects the canonical `pull-request.use-staged-ci-with-preflight` rule into repository-change execution. It does not redefine CI authority, applicability, exact-head qualification, review, or merge requirements. Repository workflows and canonical Policy remain authoritative.

## Inventory validation by role

Before relying on a validation plan, identify the repository-defined checks that can affect the current scope and classify their execution role from what they actually verify rather than from their display name:

- **CI preflight** — the cheapest deterministic checks that can reject an obviously invalid candidate before dependent expensive work;
- **core validation** — broadly applicable baseline correctness;
- **conditional integration** — integration, browser, cross-surface, materialization, compatibility, or similar checks whose applicability may vary by candidate; and
- **full qualification** — broad authority-defined acceptance required at a merge, release, publication, handoff, or equivalent qualification boundary.

A repository may collapse roles. Do not invent a preflight stage merely to satisfy this procedure, and do not call a substantial core or integration suite a preflight only because it runs first.

## Execution sequence

1. **Establish the candidate and validation inventory.** Bind the candidate/base facts needed by current workflow definitions and identify repository-required automatic checks before deciding what can be ordered or classified.
2. **Use CI preflight for early falsification when available.** Run or observe the cheapest deterministic gate first when the execution surface permits that ordering without weakening coverage. If it fails, treat the candidate as known-invalid and repair the failure before deliberately launching dependent expensive work.
3. **Complete core validation.** Passing preflight is not core evidence. Run or observe the broadly applicable baseline checks owned by repository authority.
4. **Classify conditional applicability.** For expensive integration classes, use only repository-authorized changed-surface, dependency-map, classifier, or equivalent rules. Bind applicability to the exact inputs required by Policy. Unknown or unsafe classification fails closed. `not-applicable` is not pass evidence.
5. **Run applicable conditional integration.** Do not skip an applicable browser, integration, compatibility, cross-authority, or materialization check because an earlier stage passed.
6. **Keep provisional work productive across stacked progression.** Naturally triggered CI on a provisional candidate does not freeze it. While validation is pending on an intermediate construction candidate, continue dependency-safe downstream implementation without waiting for expensive or full qualification CI. Do not deliberately propagate known material defects.
7. **Freeze at the authority boundary.** When merge acceptance, final whole-stack audit, release, publication, provenance, or another revision-bound operation requires a qualification head, stabilize prerequisites, establish the stack stability frontier, and freeze the intended candidate revision as the qualification candidate. Final review requests must only be issued against this stabilized qualification head.
8. **Complete exact-head qualification and keep review independent.** At the frozen boundary, require every applicable qualification check currently owned by repository authority, including full qualification when that boundary requires it. Earlier-stage success cannot substitute for missing later-stage evidence. If a candidate head moves or mutates, re-evaluate CI and review applicability independently: exact-head review evidence for the prior head is stale and must be reacquired under the repository's review policy, while CI/qualification evidence must be evaluated using its declared binding class. Exact-revision-bound and unknown CI evidence becomes stale on head movement; explicitly tree-and-context-bound qualification evidence may remain applicable across merge progression or history-only evolution only when the candidate tree and every required non-tree binding are positively re-established. This exception applies to CI/qualification evidence only; never reuse prior exact-head review merely because the tree is unchanged.
9. **Supersede stale expensive work on obsolete heads.** When a newer candidate makes an in-flight expensive run on an obsolete head incapable of satisfying any current evidence requirement, cancel or supersede that work when the CI provider safely permits it. Preserve evidence whose bindings remain valid and invalidate only the affected evidence.
10. **Evaluate qualification applicability across stacked landing.** When an ancestor member merges or candidate history evolves, perform an explicit qualification applicability check before scheduling new validation. Categorize existing qualification checks into `applicable`, `stale`, or `unknown` (fail-closed). Reuse applicable evidence, reacquire only what is required to restore qualification, and avoid blind full-suite reruns.

## Parallelism and automatic CI

### Prepare a repair for qualification

Apply `testing.require-adversarial-invariant-coverage` and the candidate-freeze rules with this bounded local sequence:

1. Identify the changed invariant and group known findings by root cause. Select only material sibling dimensions. For input/evidence binding, useful examples are source selection, file indirection, mutation timing, actual consumer process, and fresh versus reused or interrupted evidence; these are examples, not a universal matrix.
2. Check cheap environment and source prerequisites before dependent expensive work, including a real launch probe when applicable. Report expected and observed identities or prerequisites when diagnosis requires them.
3. Repair the owning member, run focused sibling regressions, exercise the actual canonical consumer entrypoint, and validate the relevant assembled-artifact contract when applicable. Do not substitute wrapper-call assertions for the consumer boundary.
4. Once no planned mutation remains within that repair scope, propagate the coherent repair through dependent members and publish the intended qualification candidate. Avoid repeatedly restacking and qualifying a partially repaired family. This does not prohibit provisional commits, required automatic CI, independent downstream work, or urgent repairs under canonical policy.
5. Acquire the required exact-head qualification and independently applicable review only at their authorized boundaries. After a parent lands, prefer base retargeting when the unchanged descendant tree is correct; reassess the effective diff and base-sensitive evidence instead of rewriting heads for appearance.

For source or environment failures, reuse existing canonical validators and retain their ownership. A cheap precheck changes detection order, not the authority or coverage of later acceptance.

The stage order expresses dependency and early-failure intent, not a requirement for a purely serial workflow. Independent checks may run in parallel when doing so shortens the critical path or is operationally cheaper. Repository-required automatic checks must not be suppressed merely to force staged execution; the repository workflow owns whether a check is unconditional, conditional, or explicitly triggered.

When the agent controls only observation rather than job scheduling, apply the model to diagnosis and decision order: inspect preflight/core failures first, do not wait on an expensive downstream result to repair a candidate already known invalid, and do not misreport skipped or still-running later stages as successful.

## Work-ledger projection

For validation evidence that materially affects the next safe action, record enough state to reconstruct:

- the validation role (`ci-preflight`, `core`, `conditional-integration`, or `full-qualification`) when the repository defines one;
- qualification candidate, qualification head, qualified tree identity, and evidence binding;
- applicability state (`applicable`, `stale`, or `unknown`), invalidation reason, and reuse decision;
- validation requiring reacquisition, and next safe landing action;
- workflow/check identity and run locator;
- run attempt, job/step identity and direct status/conclusion when needed for diagnosis or retry applicability, preserving any provider-supported retained-job provenance;
- observed result and whether the evidence is diagnostic or qualification-bound; and
- any supersession or invalidation condition.

Do not create a second acceptance authority in the Work ledger. The stage label is operational metadata; the workflow, canonical Policy, exact-head review requirements, and exact-head/evidence-binding rules remain authoritative. A ledger-derived next action may invoke the merge gate after qualification evidence is ready, but the ledger itself must never declare a member authorized to land.

Keep the observation compact: current head/base and effective scope, latest applicable review request/result locators, reviewed revision, inspected channels and retrieval limitations, and references to finding dispositions. Review submissions, ordinary comments, inline threads and their resolution, and applicable reactions have separate observation state. Apply `pull-request.discover-review-results-across-applicable-surfaces` before concluding that review is complete or has no findings. Refresh pending results according to the existing bounded external-wait procedure, not a new polling loop.
