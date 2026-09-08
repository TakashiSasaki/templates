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

For the repository-change operational state model, read [Work ledger](references/work-ledger.md). Before resuming or checkpointing, **select the adopted Work-ledger storage strategy** from explicit task instruction, applicable repository-local policy, or another authoritative consumer adoption decision. Use an explicitly adopted isolated repository-tracked strategy according to [Isolated repository-tracked Work ledger](references/repository-tracked-work-ledger.md); otherwise provider-side PR/Issue checkpoints remain the default. Do not infer repository-tracked adoption merely because that optional procedure exists. The selected backend is operational state only and does not create acceptance authority.

## Resumable execution loop

Use [Work ledger](references/work-ledger.md) as the operational index throughout the selected workflow:

1. discover the adopted Work-ledger storage strategy and its canonical checkpoint: use the explicitly adopted repository-tracked operational ref when one is authoritative for the consumer, otherwise use the canonical provider-side checkpoint or reconstruct it from live facts;
2. refresh materially stale bindings needed for the next safe action, checking whether an interrupted mutation or review request already succeeded; when the selected backend is a shared repository-tracked ref, always resolve the live operational-ref head and bind checkpoint selection/loading to that immutable head before using recovered state, including under serialized ownership;
3. determine the next safe action under the selected progression/completion modes and actual dependencies;
4. before executing a recovered non-idempotent external action on behalf of a shared repository-tracked backend, establish exclusive action ownership through authoritative serialized action ownership or an atomic/CAS checkpoint transition that claims that specific action; a worker that loses the claim must reload and must not execute the action;
5. perform useful authorized work, including dependency-safe descendant implementation while CI is pending;
6. checkpoint material transitions on the selected canonical operational surface, referencing finding details in the existing review-finding ledger; and
7. validate/qualify when the applicable boundary requires it, then continue or hand off.

Recover ordered members, their bases and exact heads before resuming a stack. Preserve completed semantic work when a head moves while marking affected exact-head evidence stale. Record asynchronous waiting conditions and the safe action they unblock. A missing or inaccessible durable checkpoint does not establish completed work: reconstruct what can be verified and report remaining uncertainty. Initial live operational-ref binding is mandatory even for a serialized writer. If concurrent writers remain possible after that binding and it moves during recovery, discard the stale recovery decision and restart checkpoint recovery from the new live head before following `next_safe_action` or performing an external mutation. Serialization may eliminate only later movement checks after a current live binding and action ownership are established; it never proves an unverified local ref is current.

At completion, use the checkpoint and its linked evidence to reconstruct the required report. Follow references/human-handoff.md for HANDOFF_READY and the dedicated merge gate for agent-review-and-merge. Recheck the existing complete known-finding and live-identity gates before any authorized review acquisition. If the task requires immediate stop after the request, persist the preflight checkpoint first and let the request record be the acquisition event; do not perform a post-request provider write. For a repository-tracked backend, that preflight checkpoint must also claim the specific non-idempotent request unless authoritative serialized action ownership already covers it.

## Anti-stall diagnostic control

`policy/core/repository-change-anti-stall.md` is the normative authority for material progress, bounded attempts, invalidated paths, diagnostic budgets, strategy switching, progress reporting, waiting semantics, and artifact-neutral durable-resume behavior. This Skill projects that policy into the repository-change execution loop and Work ledger; it does not redefine its acceptance semantics.

For each diagnostic objective:

1. state the evidence gap and current hypothesis before broad capability discovery;
2. use capability-first, bounded tool discovery to find the minimum action that can reduce that gap;
3. after a diagnostic attempt, decide whether there was material progress: new evidence, hypothesis support/rejection, narrower failure scope, repository/validation/review state change, qualification-frontier movement, or a materially more specific next safe action;
4. when no material state changed, increment the global no-material-progress budget and any applicable narrower strategy budget instead of treating the tool call as progress;
5. remember invalidated paths with their reason, applicability, and evidenced retry condition; do not retry them in the same context merely because another endpoint spelling may exist; and
6. when the current strategy budget is exhausted, switch diagnostic strategy to a materially different evidence source, reproduction method, or hypothesis.

A strategy is ordinarily identified by the deliberately selected objective, evidence source, diagnostic method, and hypothesis. Track observed failure mode per attempt for classification and retry decisions, but do not treat a changed outcome as a new strategy or reset its attempt count. As a guardrail, two equivalent failures require reassessment; a third identical retrieval is prohibited unless the failure classification or execution context supplies concrete new retry evidence. Cheap deterministic correction, credible transient failure, authentication repair, unavailable capability, unavailable evidence, and semantic failure require different handling; do not encode the guardrail as a universal fixed retry count.

The global no-material-progress budget advances even for successful calls that only reproduce already-known information. Perform a stall check after about three no-progress tool calls while the same evidence gap persists, or sooner when tool-name discovery dominates productive work. Two semantically equivalent progress reports without material progress are also a stagnation signal. These numbers trigger reassessment rather than define a stall: the controlling question is whether the knowledge, repository, validation, review, qualification, or next-action state changed.

At a diagnostic-budget boundary, switch diagnostic strategy before giving up. Only classify the objective as `blocked` when no alternate authorized, in-scope strategy remains that can materially reduce the evidence gap. A change from raw CI logs to check annotations, focused source-delta reproduction, generated-artifact inspection, workflow-source analysis, or bounded bisect can be a real strategy switch; searching another API name for the same unavailable raw log ordinarily is not.

Keep external dependency state distinct from agent diagnostic state:

- `external_wait`: a required dependency such as CI, review, deployment, or publication is validated as legitimately pending and has a concrete resume condition; provider progress may be opaque or unchanged;
- `diagnostic_stall`: agent activity continues while the same evidence gap persists without material progress;
- `blocked`: alternate authorized in-scope strategies are exhausted or unavailable;
- `productive_parallel_work`: authorized work performed during an external wait that directly advances the declared completion frontier.

An unchanged provider `pending` or `in_progress` status can remain `external_wait` when dependency identity and resume condition are valid. Track a separate stale/timeout/failure transition for waits that cease to be legitimate; opaque progress alone is not agent stall.

During `external_wait`, productive_parallel_work may include downstream stacked-branch construction, PR-body synchronization, review-debt audit, exact-head applicability audit, deterministic test preparation, and known documentation synchronization. Do not justify unrelated cleanup, optional features, architecture exploration, or scope expansion as wait-time work.

Progress reporting is knowledge-delta reporting. Prefer: what changed, what was learned, what remains unknown, why the strategy changed, and what comes next. Do not emit repeated variants of “checking logs” or “continuing diagnosis” when the underlying strategy and evidence gap have not changed.

On resume, restore the Work ledger's invalidated and exhausted paths before diagnostic retry. Resume from the recorded progress frontier and next safe action; do not restart the investigation by default. Refresh only stale facts whose current binding matters to the next action. For an adopted shared repository-tracked backend, the operational-ref head is a mandatory read-side concurrency binding: always resolve it live before checkpoint selection/loading, including under serialized ownership. Before a recovered non-idempotent external action, require serialized action ownership or an atomic/CAS action claim; checkpoint-write CAS after the action is too late to prevent duplicate effects.

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

While CI, review, publication, deployment, or another external result is in flight, continue useful work that does not invalidate the candidate under evaluation. CI waiting must not stop dependency-safe implementation on later members; record the dependency and provisional state in the Work ledger. Treat a validated pending dependency with a concrete resume condition as `external_wait` even when the provider exposes only an unchanged `pending` or `in_progress` status. Track a separate stale/timeout/failure condition for the dependency instead of converting opaque progress into `diagnostic_stall`. Limit parallel activity to `productive_parallel_work` that advances the declared completion frontier. For a frozen qualification candidate, suitable work includes:

- bounded read-only self-audit of the current candidate;
- reproducing or falsifying suspected defects;
- identifying missing regression coverage;
- preparing repair designs without applying them;
- checking authority and invariant boundaries;
- inventorying the next independent task when it does not change the current candidate.

Do not turn wait time into an unbounded search for hypothetical defects. Stop a read-only audit when the agreed scope and relevant invariants have been evaluated or when additional investigation has no concrete trigger. Do not expand into unrelated cleanup, optional features, or unrelated architecture work merely because an external dependency is pending.

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

A guarded write does not eliminate semantic validation or live-state revalidation required by repository authority, including any required commit-boundary revalidation. It can eliminate only an additional read whose sole purpose is to detect the same race already covered by the write precondition and whose omission does not remove a required authority check. Guarded checkpoint writes also do not establish action ownership for an already-executed non-idempotent external effect; claim such an action before execution or use authoritative serialization that covers the action itself.

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
