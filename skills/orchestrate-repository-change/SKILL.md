<!--
agent-policy-generated: true
source-skill: orchestrate-repository-change
DO NOT EDIT DIRECTLY
-->
---
name: orchestrate-repository-change
description: Orchestrate repository changes with bounded live-state reads, coherent mutation batches, staged validation, useful wait-time work, and selective evidence invalidation without weakening acceptance criteria.
---

# Orchestrate a repository change

Use this skill for implementation work that spans repository inspection, one or more mutations, validation, asynchronous CI or review, remediation, and completion. It is an execution-efficiency procedure, not a new source of semantic acceptance policy.

Repository code, schemas, validators, tests, workflows, release rules, project policy, and explicit task requirements remain authoritative. If any instruction below conflicts with those sources, follow the authoritative requirement rather than optimizing for fewer calls or fewer revisions.

## Strategy-neutral workflow dispatcher

This Skill is a strategy-neutral dispatcher for repository-change execution. It connects canonical normative acceptance requirements to a selected progression strategy and a selected completion strategy; it does not replace the policy, contract, schema, validator, CI, review, or merge authorities that establish those requirements.

Keep the two selections independent:

- progression: serial-pr or stacked-pr;
- completion: agent-review-and-merge or human-handoff.

Select each dimension in this order:

1. explicit task instruction;
2. applicable repository-local policy;
3. repository-declared default;
4. agent selection only when the preceding authorities explicitly permit it.

Do not infer a workflow selection from a policy profile, agent provider, or enabled Skill. Policy profiles select shared normative rules; they are not operating-mode profiles. Do not create profiles for serial-pr, stacked-pr, human-handoff, agent providers, or other workflow combinations merely to encode this selection.

Progression controls construction ordering; completion controls the stopping boundary. When serial-pr is selected, implement and validate one coherent member at a time. Under agent-review-and-merge, establish the required exact-head review and merge evidence, complete the guarded merge, and only then begin the next member. Under human-handoff, stop after authorized validation at HANDOFF_READY without initiating merge-acceptance review or merging merely because serial progression was selected.

When stacked-pr is selected, review latency does not block construction of later members when no known material defect invalidates the prerequisite. Implement and validate member 1, create its PR, implement and validate member 2 on member 1, create its dependent PR, and continue for later members. Under agent-review-and-merge, a stacked member ordinarily relies on its own completed independent exact-head review; multiple members may instead use explicit cumulative coverage when every canonical stacked-review binding is satisfied. Stacked progression does not require cumulative review. A whole-stack architecture/dependency/completeness audit is not per-member merge evidence unless those cumulative bindings are established. Under human-handoff, leave the validated whole stack open and unmerged without acceptance-review acquisition by default; an explicit task instruction may authorize one final whole-stack audit that remains separate from merge evidence.

When agent-review-and-merge is selected, review and merge completion remain separate acceptance boundaries and require the applicable exact-head or cumulative evidence and guarded merge procedure.

When human-handoff is selected, stop at HANDOFF_READY after the authorized implementation and validation work. Do not initiate merge-acceptance review through reviewer assignment, provider invocation, requested-reviewer state, or another review-request mechanism by default. An explicit task instruction may authorize one final whole-stack architecture/dependency/completeness audit after the complete stack is stable enough for handoff; treat that audit separately from per-member merge evidence, do not turn it into a retry loop, and do not infer merge authorization from it. Existing review evidence may still be observed, inspected, or reported. Do not merge, close the PR, create a no-op commit to trigger automation, or mutate solely to obtain approval. Report implementation and validation accurately, report per-member review as not requested or outstanding unless pre-existing evidence truthfully establishes another observed state, report any final audit separately, report merge authorization as not established, and leave the PR open and unmerged. Human handoff is a normal completion boundary, not a review waiver or merge authorization.

Use the focused procedures in references/pr-workflow-selection.md, references/serial-pr-workflow.md, references/stacked-pr-workflow.md, and references/human-handoff.md for the selected path.

For the repository-change operational state model, read [Work ledger](references/work-ledger.md). It defines provider-side resumable checkpoints without creating acceptance authority.

## Resumable execution loop

Use [Work ledger](references/work-ledger.md) as the operational index throughout the selected workflow:

1. discover the canonical provider checkpoint or reconstruct it from live facts;
2. refresh materially stale bindings needed for the next safe action, checking whether an interrupted mutation or review request already succeeded;
3. determine the next safe action under the selected progression/completion modes and actual dependencies;
4. perform useful authorized work, including dependency-safe descendant implementation while CI is pending;
5. checkpoint material transitions on the canonical surface, referencing finding details in the existing review-finding ledger; and
6. validate/qualify when the applicable boundary requires it, then continue or hand off.

Recover ordered members, their bases and exact heads before resuming a stack. Preserve completed semantic work when a head moves while marking affected exact-head evidence stale. Record asynchronous waiting conditions and the safe action they unblock. A missing or inaccessible durable checkpoint does not establish completed work: reconstruct what can be verified and report remaining uncertainty.

At completion, use the checkpoint and its linked evidence to reconstruct the required report. Follow references/human-handoff.md for HANDOFF_READY and the dedicated merge gate for agent-review-and-merge. Recheck the existing complete known-finding and live-identity gates before any authorized review acquisition. If the task requires immediate stop after the request, persist the preflight checkpoint first and let the request record be the acquisition event; do not perform a post-request provider write.

## 1. Establish the minimum sufficient snapshot

Before mutating, identify the facts that determine the next safe action:

- authoritative branch, revision, or artifact;
- requested outcome, effective scope, preserved invariants, and non-goals;
- files or components likely to change;
- applicable validation and evidence-producing workflows;
- already-valid evidence that may be reusable;
- external or asynchronous dependencies that can invalidate the plan.

Read enough live state to remove material uncertainty. Do not repeatedly fetch unchanged state merely for reassurance. Do not impose a fixed numeric limit on tool calls: a necessary read is preferable to an incorrect assumption.

When independent reads do not depend on one another and the execution surface supports concurrency, batch or parallelize them. Keep dependency-ordered reads sequential when later inputs depend on earlier results.

## 2. Plan coherent mutation units

Group compatible edits that share the same authority, semantic purpose, validation boundary, and rollback unit. Prefer one coherent mutation over avoidable one-finding-at-a-time churn.

Do not combine unrelated work merely to reduce commit, pull-request, or tool-call counts. Keep work separate when changes have different authorities, materially different risks, conflicting decisions, independent merge value, or clearer validation as distinct units.

Do not create no-op, cosmetic, or speculative mutations to demonstrate progress, retrigger automation, or refresh evidence unless current repository authority explicitly requires such a recovery action.

## 3. Validate from focused to broad unless parallelism is cheaper

After a coherent mutation is ready, run the cheapest focused checks that can falsify the change quickly, then broader validation required by repository authority.

This is an ordering heuristic, not a mandatory serial pipeline. If independent validation can safely run in parallel and doing so shortens the critical path without hiding failures, parallel execution is preferred.

Never skip a required expensive check merely because a cheaper check passed. Never add redundant validation solely to make an already-valid result feel newer.

## 4. Freeze revision-bound candidates

Distinguish construction heads and provisional candidates from qualification heads under `pull-request.defer-revision-bound-qualification-until-required`. Naturally triggered CI does not by itself freeze a provisional candidate or block authorized implementation. When an applicable boundary requires final qualification, stabilize prerequisite identities and freeze the intended candidate heads. Keep those qualification heads stable unless a justified head-changing repair, scope correction, conflict resolution, or other necessary mutation is ready. Record the frontier and affected evidence bindings in the Work ledger.

A known material defect blocks acceptance immediately even while the candidate revision remains unchanged for investigation. Candidate stability is an efficiency mechanism, not evidence that the candidate is acceptable.

For pull-request merge acceptance, defer to the repository's pull-request policy and any dedicated merge-gate procedure. This skill does not redefine exact-head review, CI, thread-closure, mergeability, or guarded-merge requirements.

## 5. Use asynchronous wait time for bounded read-only work and dependency-safe construction

While CI, review, publication, deployment, or another external result is in flight, continue useful work that does not invalidate the candidate under evaluation. CI waiting must not stop dependency-safe implementation on later members; record the dependency and provisional state in the Work ledger. For a frozen qualification candidate, suitable work includes:

- bounded read-only self-audit of the current candidate;
- reproducing or falsifying suspected defects;
- identifying missing regression coverage;
- preparing repair designs without applying them;
- checking authority and invariant boundaries;
- inventorying the next independent task when it does not change the current candidate.

Do not turn wait time into an unbounded search for hypothetical defects. Stop a read-only audit when the agreed scope and relevant invariants have been evaluated or when additional investigation has no concrete trigger.

## 6. Aggregate known actionable findings before mutating

Combine currently known, compatible head-changing repairs from self-audit, CI, and review into a coherent repair batch when doing so preserves clarity and timely remediation.

Do not wait an arbitrary interval for hypothetical future findings, broaden scope to fill a batch, or delay a ready repair when delay creates a concrete safety, operational, publication, or data-integrity risk. Apply urgent justified repairs immediately.

After a repair batch creates a new candidate, do not deliberately expose a sequence of partial intermediate candidates to the same expensive revision-bound evidence cycle when the remaining known compatible repairs could have been completed first.

## 7. Invalidate evidence by binding, not by anxiety

For every accepted evidence item, know what facts it is bound to: revision, scope, target/base state, configuration, environment, workflow definition, or other applicability conditions.

When state changes, invalidate only evidence whose binding changed or became unknown. Reuse unaffected evidence when current authority permits reuse. A changed revision commonly invalidates revision-bound CI and review; it does not automatically invalidate every target-branch, environment, or policy fact.

If a binding is uncertain, resolve that uncertainty before relying on the evidence. Selective invalidation must never become an excuse to reuse stale evidence.

## 8. Prefer guarded writes over redundant pre-write polling

When the provider or execution surface supports compare-and-swap, expected revision, ETag, immutable-head, version, generation, or equivalent write preconditions, use them to close races at mutation time.

A guarded write does not eliminate semantic validation or live-state revalidation required by repository authority, including any required commit-boundary revalidation. It can eliminate only an additional read whose sole purpose is to detect the same race already covered by the write precondition and whose omission does not remove a required authority check.

If a guarded write is rejected, do not retry blindly. Refresh the state relevant to the rejection, determine which prior assumptions or evidence were invalidated, and continue from that point.

## 9. Complete at the declared boundary

After the final mutation or acceptance operation, verify the minimum facts needed to establish that the requested operation actually succeeded. Keep later release, publication, deployment, adoption, or downstream readiness as separate boundaries unless the task explicitly includes them.

Do not expand completion criteria because additional checks feel safer. Do not omit explicitly required completion criteria because they are expensive.

## 10. Report the execution evidence

At completion or handoff, report:

- starting authoritative revision and final candidate/result revision;
- effective scope and mutation units;
- validation and asynchronous evidence used;
- findings that required mutation and how they were batched or separated;
- evidence invalidated and evidence legitimately reused;
- guarded-write or race-handling decisions, when applicable;
- unresolved blockers, residual risks, and the exact completion or stop boundary.

Efficiency is evaluated by preserved correctness with less avoidable round-trip, mutation, and evidence churn. Fewer calls, commits, reviews, or CI runs are not goals when they reduce evidence quality or blur authority boundaries.
