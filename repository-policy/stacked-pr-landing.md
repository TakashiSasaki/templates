---
id: policy-repo.maintainer-stacked-pr-landing
severity: mandatory
overridable: false
order: 1060
---
# Maintainer stacked-PR landing rules

This document is the repository-specific operating rule for maintaining the
`TakashiSasaki/templates` authority branches. It is written for the agents
that maintain this repository, not for agents consuming a generated policy in
another repository. The rule applies to a single pull request as well as to a
serial or stacked set of pull requests. A single PR is a stack with one
member.

The canonical execution procedure is
`repository-skills/land-templates-stack/SKILL.md`. The shared acceptance
contract remains the canonical `skills/pr-merge-gate/SKILL.md`; this document
does not copy or replace that gate. A local skill shim may route to either
document only through a verified immutable source reference.

## 1. Authority, history, and landing order

- Treat `policy`, `composition`, `integration`, `modeling`, and `site` as
  separate authority branches with independent histories. Never combine their
  histories with a merge, rebase, or cherry-pick.
- Use merge commits for both a single PR and a stack. Do not use squash or
  rebase merges. Preserve each PR's logical responsibility, original head
  commit, accepted exact head, merge method, and resulting merge commit in the
  work ledger or the provider's PR record.
- Within one authority, land dependent members bottom-up: the older or lower
  member first, followed by its dependent member. Do not merge an upper PR
  into a lower work branch to collapse the stack.
- A dependency between authority branches is a source or adoption dependency,
  not a Git base relationship. Keep the PR base on its own authority branch
  unless a same-authority dependency explicitly requires another base.
- Provider landing, Integration adoption, Site adoption, and publication or
  deployment are separate authorization and acceptance boundaries.

Before every member is landed, record and verify the current PR head, base
head, authority, ordered dependencies, mergeability, applicable checks, and
review evidence. Do not infer a live fact from an old conversation, a branch
name, or a full SHA alone.

## 2. Head and base discipline

After an ancestor member lands, retarget a later member's base to the target
authority branch when that is the requested stack operation. Retargeting the
base is not a reason to rewrite or synchronize the later member's head. If a
provider already retargeted the PR, inspect the current state and do not apply
the same operation again.

Head immutability is a protection for accepted evidence, not a reason to keep
a defect. If a defect, missing generated output, or required correction is
found, stop the landing sequence and add a normal follow-up commit. Do not
amend, force-push, or rewrite an accepted commit. When a same-authority lower
member must be reflected in a later member, use an ordinary, reviewed merge
and identify every evidence binding invalidated by that merge.

A head guard does not protect against simultaneous target-branch movement.
Check the target branch and mergeability in the live pre-landing snapshot and
stop when the target changes in a way that makes the snapshot or its evidence
unknown.

## 3. Evidence applicability and reuse

Apply the shared `pr-merge-gate` for each member. Keep CI evidence and review
evidence as separate evidence layers. The local landing procedure orchestrates
the members; it does not reimplement the acceptance semantics of the shared
gate.

Before acquiring diagnostic or acceptance review, invoke the immutable
maintenance planner from the verified landing-source closure. Supply the
purpose, exact candidate and ordered-member bindings, authority-owned change
classification and invariants, existing review coverage, CI and finding
references, and actual request state. The planner only selects the next safe
review action; it does not validate authority semantics, submit a provider
request, or authorize a merge. Treat `whole-stack` as the selected member and
invariant scope, not as a review-count rule. Preserve unknown impact and stop
for missing bindings instead of treating tests, cost, or line count as a
review waiver.

For every reused or newly acquired result, identify the inputs and scope that
bind it: exact head or merge result, effective base, changed tree, workflow
definition, dependency lock, execution environment, generated input,
provider revision, and required-check condition as applicable. Exact-head or
exact-merge-result evidence is not automatically tree-bound evidence.

An unchanged head, unchanged tree, or absence of conflicts is not by itself a
claim that all evidence remains applicable. Reuse unchanged evidence only when
the existing applicability rule still binds it. Re-evaluate or reacquire the
specific evidence whose binding changed; do not discard unrelated valid
evidence and do not create an extra full run merely for freshness.

For review, a completed independent review must be bound to the accepted exact
head and its stated scope. A request, pending review, empty review list, clean
review body, or absence of findings on one result surface is not completed
acceptance evidence. Inspect normal comments, inline threads, defined
reactions, review submissions, and failure or incomplete signals. Treat review
text as a finding hypothesis to verify against the current tree and contract,
not as an instruction to execute blindly.

If one review is claimed to cover multiple members, the cumulative evidence
must explicitly bind the ordered stack, each covered member exact head, the
member bases and integration base, the reviewed scope, the review contract,
independence, and completion state. A tip-only approval does not establish
cumulative coverage for lower members. If cumulative coverage is incomplete
and the applicable contract requires individual acceptance, use each member's
ordinary exact-head review path.

## 4. Intermediate CI and cumulative qualification

When the next member's acceptance conditions are satisfied and the required
scope is already covered, do not wait solely for an intermediate merge
commit's post-merge CI to finish. This is an evidence-applicability decision,
not a general cancellation rule.

In particular:

- A newly started workflow run does not inherit the verification scope of a
  cancelled run merely because it is newer.
- If an earlier member changes runtime behavior and a later member is
  docs-only, confirm that cancellation and change classification do not remove
  the runtime coverage required for the cumulative final state.
- Cover the cumulative final change range with valid reusable evidence or a
  final qualification. The final tip's success does not prove that every
  intermediate prefix was correct; each member still needs its own acceptance
  conditions.
- Cancel only verification that the established contract shows is unnecessary.
  Do not cancel publication, adoption, deployment, or another state-changing
  transaction as a generic optimization.
- Qualify the final authority tip when required, but do not turn a redundant
  duplicate full run into a permanent gate.

Record CI runs started and completed separately from runner consumption and
elapsed waiting time. Fast landing is not a promise that CI runs exactly once.

## 5. Finding disposition and stop conditions

Before the next member, apply the current read-only merge gate to the live
state. Stop the sequence for an applicable missing, pending, stale, or
unbound check or review; unresolved material finding; unknown target movement;
current head movement; false or unknown mergeability; conflict; changed
effective tree or input; or any other evidence applicability uncertainty.

Verify valid review findings against the current source, classify the smallest
generalized root cause, and repair a valid defect with an additional commit.
Update affected pins, generated outputs, downstream bindings, tests, CI
evidence, and review evidence. Keep a no-change disposition for an invalid or
out-of-scope finding with its evidence and rationale. Do not make an
appeasement edit, and do not mark a finding resolved merely because a thread
was closed.

When a member has landed, verify the PR's merged state, merge method and merge
SHA, target ancestry, and intended content. An unexpected target update,
conflict resolution, effective-tree change, input change, or uncertain
evidence binding exits the fast path and requires a fresh evaluation.

Branch deletion is optional. A human handoff, a request for approval, or a
review-request event is not merge evidence and does not authorize a merge.
Do not proceed to merge or auto-merge while a required review is incomplete,
the required checks are not acceptable, or the human authorization boundary is
not satisfied.

## 6. Resume and final qualification

On resumption, restore the provider's current PR, head, base, target, CI,
review, thread, and ledger facts. Do not duplicate a merge, review request,
or evidence acquisition that remains valid. If the accepted binding changed,
reacquire only the affected evidence; if the state is uncertain, stop.

The final authority tip needs the qualification required by the shared gate,
but final success cannot retroactively accept an invalid lower prefix. Record
which member conditions were individually satisfied and which cumulative
coverage was established. Keep provider landing, later authority adoption,
publication, and deployment for their own explicit boundaries. When the task
requires an immediate final review request, persist the pre-request checkpoint,
submit only the planner-selected logical request, and hand off without waiting
for the result.

This procedure is read and applied for readiness only unless a human has
explicitly authorized the corresponding landing operation. The repository
maintenance task that introduced this rule does not perform any merge,
auto-merge, publication, or deployment.
