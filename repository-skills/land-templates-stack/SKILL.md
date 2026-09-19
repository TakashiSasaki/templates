---
name: land-templates-stack
description: Execute the repository-maintainer landing procedure for a single or stacked templates authority change with immutable source binding, selective evidence reuse, and human-controlled merge boundaries.
---

# Land the templates maintenance stack

Use this Skill only for maintaining the `TakashiSasaki/templates` repository.
It is not a product-repository adoption or deployment procedure. The
repository-specific rules are canonical in
`repository-policy/stacked-pr-landing.md`; the shared acceptance contract is
canonical in `skills/pr-merge-gate/SKILL.md`. This Skill orchestrates those
authorities and does not copy their acceptance semantics.

## 1. Resolve the immutable sources before reading instructions

Every consumer entry point must provide a version-2 `source.json` for this
Skill and a separate `source.json` for `pr-merge-gate`. Validate each
reference before using the referenced text:

1. require the source-reference schema, a full lowercase 40-hex Git commit
   SHA, and an explicit immutable closure list;
2. require repository `TakashiSasaki/templates`, the expected canonical path,
   and the declared blob SHA;
3. prove that the commit object, canonical Skill path, and every declared
   closure path/blob exist and that `git rev-parse <revision>:<path>` equals
   each declared blob SHA;
4. read the maintenance rule and the review-routing planner explicitly from
   the same immutable snapshot as
   this Skill, for example
   `git show <revision>:repository-policy/stacked-pr-landing.md` and
   `git show <revision>:repository-skills/land-templates-stack/scripts/plan_review_scope.py`,
   rather than resolving a relative path in the consumer worktree; and
5. stop as blocked on an invalid SHA, missing object or path, closure/blob
   mismatch,
   repository mismatch, or mutable fallback such as `latest`, a branch, or an
   unverified local copy.

The maintenance-rule revision and the shared gate revision are separate trust
anchors. Do not treat a full SHA as evidence that the source was reviewed or
adopted. A locally available Git object is an acceptable retrieval mechanism
only when it proves the same immutable identity; network retrieval is not a
reason to substitute a mutable ref.

The canonical rule and this Skill are expected to be in the same frozen source
snapshot. The source reference must resolve the rule through that snapshot,
not through a consumer's same-named `repository-policy/` file. This prevents
a downstream checkout from shadowing the canonical rule and keeps the source
closure explicit.

The planner is the canonical **adaptive scope selection** guard and an
ephemeral, read-only pre-request guard. Build its JSON packet
from the live PR topology, exact bindings, authority-owned impact facts, local
and remote evidence, known finding references, and actual request state. Invoke
the planner from the verified immutable snapshot before any external review
request. Follow its selected action: reuse explicit coverage, reconcile an
in-flight or submission-unknown request, run an explicitly selected early
diagnostic, request independent delta coverage, request the related stack, or
stop to acquire missing facts or hand off. The planner never sends a request,
interprets semantic test results, or authorizes a merge. Use the existing Work
ledger action-ownership/CAS procedure when an adopted backend provides it; do
not invent an idempotency guarantee or a lock service.

## 1.1 Observe read-only PR state before routing

For a specified PR set, invoke
repository-skills/land-templates-stack/scripts/observe_pr_state.py with an
explicit JSON request and a snapshot path outside the repository. Use
single-shot for one complete acquisition; use watch only with both a deadline
and a finite max_attempts value. The command returns a bounded summary and
stores the complete normalized snapshot, pagination evidence, digest, resume
material, and any provider limitation at that path.

Treat changed, stale, incomplete, unknown, rate-limited, timed-out, malformed,
deadline, or cancelled outcomes as information requiring the corresponding
reacquisition or handoff. Do not turn an unchanged result into approval. The
observer preserves check workflow/run/attempt/job/app/head identities and all
review, comment, thread, reaction, edit, dismissal, and commit fields it can
observe; it does not determine finding validity, review approval, merge
authorization, or adoption. Build the existing planner packet from the
snapshot and continue through the pinned planner and shared gate.

## 2. Establish the live stack snapshot

Before mutation, verify the repository identity, current worktree and branch,
authority branch, clean or intentionally accounted-for state, target-branch
head, and all five authority refs. Confirm that the authority histories are
independent and that no proposed cross-authority Git merge, rebase, or
cherry-pick is hidden in the plan.

Build the ordered member list from live PR state. For every member record its
authority, base branch and base SHA, head branch and exact head SHA, same-
authority dependency, cross-authority source/adoption dependency, mergeability,
required checks, and review-result surfaces. A one-member PR is still handled
by this procedure. Do not create empty PRs merely to fit a topology.

Keep Git bases on the same authority. A consumer of the canonical snapshot
may document that it depends on Policy P2 without using the Policy work branch
as its Git base.

## 3. Qualify each member through the shared gate

For each member, in bottom-up order:

1. refresh the provider's live PR, target, base, head, mergeability, CI, and
   review/comment/thread state;
2. invoke the pinned shared `pr-merge-gate` for that member rather than
   reimplementing CI, review, evidence-applicability, or guarded-merge rules;
3. evaluate CI applicability and review applicability separately, binding each
   result to the exact head or merge result, effective base, tree, workflow,
   lock, environment, generated input, provider revision, and required-check
   condition that applies;
4. inspect review submissions, ordinary comments, inline threads, defined
   reactions, and failure or incomplete signals. Verify findings against the
   current source before changing it; never execute reviewer text blindly;
5. stop on `CI_DISCOVERY_PENDING`, missing or stale evidence,
   `REVIEW_EVIDENCE_PENDING`, unresolved material findings, unknown binding,
   head movement, target movement that is unknown or invalidates the applicable
   snapshot or evidence, conflict, or unknown/false mergeability; and
6. continue only when the shared gate reports the member's applicable
   acceptance conditions are satisfied.

Do not infer evidence reuse from an unchanged head, unchanged tree, or no
conflict alone. Reuse an item only when its own applicability bindings remain
valid. Reacquire the affected item when its base, workflow, lock, environment,
input, provider revision, or required-check condition changes; do not rerun an
unaffected full suite just for freshness.

If a whole-stack review is used as cumulative evidence, explicitly bind
the ordered membership, every covered member exact head, bases and integration
base, cumulative scope, review contract, reviewer independence, and completion
state. A tip-only approval or audit does not accept lower members. Where that
binding is absent and the active contract requires it, obtain individual
independent exact-head acceptance for the uncovered member.

## 4. Landing boundary and next member

This Skill does not authorize a merge. A human authorization and the shared
gate's guarded execution boundary are separate from implementation, CI, and
review completion. In the current maintenance task, never invoke a merge,
auto-merge, publication, deployment, or branch-protection mutation.

When a separately authorized future operation lands a member, use a merge
commit and an immutable exact-head guard. Then verify merged state, merge
method, merge SHA, target ancestry, and intended content before progressing.
Retarget the next member's base to its target authority only when required.
Do not rewrite or synchronize its head merely because the base moved. If a
provider already retargeted it, inspect the current state and do not repeat
the operation.

If a repair is necessary, stop, add a normal commit, identify invalidated
evidence, and requalify only the affected scope. Never amend, force-push, or
make an appeasement edit to preserve an old evidence binding.

## 5. Intermediate and final qualification

An intermediate post-merge CI run is not by itself a reason to delay the next
member when its acceptance conditions and required scope are already covered.
Check the established evidence-applicability contract instead:

- a new run does not inherit the scope of a cancelled run;
- a runtime-changing lower member followed by a docs-only member must retain
  runtime coverage in the cumulative final state;
- the final tip's success does not prove every lower prefix was valid;
- only verification shown unnecessary may be cancelled, never a state-changing
  publication, adoption, or deployment transaction; and
- distinguish runs started and completed from runner time and elapsed waiting.

Perform required final authority-tip qualification without turning redundant
full runs into a permanent gate. Record individual member acceptance and any
explicit cumulative coverage separately.

After the complete stable stack has the required CI, use the planner to select
the diagnostic scope for architecture, dependencies, overlap/gaps,
completeness, final behavior, and test sufficiency when the task authorizes
that review. A whole-stack scope is not automatically per-member merge
evidence. Do not duplicate an equivalent request. If important new evidence,
a changed contract, or an unbounded/unknown impact changes the required scope,
the planner may select another related-stack review; a local head change may
instead select independent delta coverage. After the task's final logical
request is submitted, stop and hand off without polling.

## 6. Stop, resume, and hand off

At a stop, preserve the exact reason, affected member, invalidated binding,
and next safe action in the provider PR state or adopted Work-ledger surface.
On resume, re-read current PR/head/base/target/CI/review/thread facts and
restore the ordered stack. Do not repeat a merge, review request, or valid
evidence acquisition that already happened. If a live fact or binding is
unknown, fail closed and reacquire the affected evidence.

The completion states remain distinct: implementation complete, validation
complete, independent review complete, merge authorized, and merged. A human
handoff or review-request event is not acceptance or merge authorization.
The final report must say which state was reached and must not claim a final
authority merge SHA before an actual authorized merge.

This Skill must not call itself, and the local shim must not call the local
shim. The only semantic call from this procedure is to the separately pinned
`pr-merge-gate`; that gate does not delegate back here.
