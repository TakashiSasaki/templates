<!-- agent-policy-generated: true -->
# Repository-change Work ledger

## Purpose and authority

Maintain a current resumable checkpoint for a repository change: its objective, dependency topology, useful next action, asynchronous dependencies, and completion boundary. The Work ledger is an operational projection / resumable index, not a new source of semantic acceptance policy. Repository contracts, policy, validation, review and merge procedures retain their authority.

The Work ledger is repository-associated. A provider-side checkpoint is the default storage strategy; repository-tracked operational storage is optional and may be used only when the consumer or independent repository authority explicitly adopts an isolated strategy. GitHub commit SHAs, branch heads, pull requests, CI runs, reviews, review threads and merge state are canonical provider facts; ledger entries are observations of those facts. Other providers retain equivalent authority over their own objects. When an observation conflicts with live state, refresh the affected observation, not the provider fact to make it agree with the ledger. A ledger label such as `success`, `qualified` or `HANDOFF_READY` is not acceptance evidence.

Product current semantic state and validated lifecycle history remain owned by their product contracts and lifecycle authorities. The Work ledger neither replaces those artifacts nor establishes product acceptance. It is not a review-finding authority, a transcript, a mandatory schema, an automatic next-action engine, or permission to expand scope or merge.

## Storage and discovery

Prefer one canonical provider-side checkpoint surface per work scope unless the repository has explicitly adopted an isolated repository-tracked operational-state strategy:

1. an identifiable Work ledger comment on the stack tip PR;
2. a Work ledger comment on a standalone PR;
3. a tracking issue for pre-PR, multi-stack or long-running work; and
4. execution-local state as a high-frequency checkpoint supplement.

Use the supported equivalent on other providers. Identify the canonical surface in the PR body or tracking issue so another session can discover it. If the tip changes, move the checkpoint only when useful, leave a forwarding locator at the former surface, and mark it superseded. A multi-stack issue may index separate authority-local stacks; it must not imply shared branch history or duplicate their detailed checkpoints. If several purported canonical surfaces conflict, reconstruct from live facts and explicitly select one before relying on either. Do not silently overwrite another worker's update. Use an atomic provider version/compare-and-swap guard when available. A pre-write read and reconciliation alone do not protect against a concurrent write. Without a conditional update, use an established single writer with serialized handoff, or append immutable checkpoint comments that identify their predecessor and work scope. Competing successors are a conflict, not last-write-wins state: preserve both, reconcile from live facts, and designate the successor before relying on it. Never edit a shared pointer/comment concurrently without a guard; discover append-only successors from the thread instead. If exclusive ownership or reconciliation cannot be established, pause the conflicting write and report the limitation. This procedure does not require a new lock service or updater.

Do not mutate an implementation or qualification candidate solely to persist operational progress. In particular, do not commit `.work-ledger.json` or an equivalent progress file on a candidate branch merely to satisfy this procedure. Such a progress-only commit changes the candidate SHA, stales exact-head CI/review evidence, changes qualification bindings, and can demand another ledger update.

Repository-tracked operational storage is allowed only when independent repository authority explicitly adopts it and keeps it isolated from implementation/qualification candidates, product semantic state, formal lifecycle history, and generated/source authority. A dedicated operational branch or equivalent operational ref may hold the checkpoint without moving the qualified implementation head. Updating that operational ref must not establish acceptance, merge readiness, product state, or review-finding disposition. An agent must not create or assume such a branch, ref, directory, or file merely because this Policy supports the strategy; adoption must already be established by repository policy, task instruction, or an equivalent authoritative consumer decision.

Repository-tracked operational state is still an observation cache / resumability checkpoint, not provider truth. Its revision is operational identity, not candidate identity. The implementation head and operational checkpoint head must remain independently addressable so operational writes cannot invalidate implementation qualification. A repository-tracked strategy may recommend a machine-readable representation, but this procedure does not impose a mandatory JSON/YAML artifact or serialization schema.

When repository-tracked operational state is explicitly adopted, follow [Isolated repository-tracked Work ledger](repository-tracked-work-ledger.md) for adoption discovery, operational-ref isolation, current-checkpoint structure, compare-and-swap writes, minimal-frontier refresh, selective reconciliation, evidence reuse, interrupted-mutation recovery, and retention/security boundaries. Its branch names, paths, and serialization examples are non-mandatory.

If durable storage is unavailable, retain execution-local state and report the durability limitation at handoff. Do not claim a durable checkpoint was saved when a write failed; persistence requirements explicitly imposed by the task remain unsatisfied.

## Minimum logical state

Combine fields where natural; omit inapplicable dimensions with an explanation when omission could be mistaken for missing work. These are logical groups, not a serialization schema.

| Group | State needed to resume |
| --- | --- |
| Change contract | Objective, scope/non-goals, preserved behavior/invariants, required acceptance criteria and evidence, progression and completion modes; alternatively an authoritative change-contract locator carrying those requirements. |
| Authority snapshot | For each authority: provider host/namespace, stable repository ID when available plus current qualified locator, branch, starting revision, current observed revision and last live refresh. |
| Topology | Repository-qualified PR/branch members, stable PR ID when available, base, exact observed head, dependency, semantic responsibility and cumulative scope. Keep unrelated authority histories separate. |
| Mutation plan | Coherent mutation units, affected authority, planned/in-progress/complete/deferred state, owned paths/provider objects and completed effects; retain relevant preflight/commit-boundary observations for an interrupted unit. |
| Stability and qualification | Practical stability frontier, provisional candidates, intended qualification heads when required, and evidence binding status. |
| Evidence | Evidence layer (local, environment-dependent, remote CI, independent review), exact executed command or workflow/check identity, bound SHA or artifact, run/evidence locator and provenance, observed result, limitations and applicability conditions (including relevant base, scope, configuration or environment). |
| Review | Acquisition state and locator; distinguish whole-stack diagnostic audit from member/cumulative acceptance review. Reference the review-finding ledger and its known-material-findings status. |
| Diagnosis and progress | Current objective/failure scope, `evidence_gap`, `current_hypothesis`, compact `attempted_paths`, `invalidated_paths` with reason/applicability/`retry_condition`, current strategy, `strategy_attempt_count`, strategies already exhausted, `strategy_switch_reason`, `diagnostic_budget`, `progress_frontier`, `last_material_progress`, and current external-wait/stall/block state when relevant. |
| Dependencies | Blockers, asynchronous dependencies, the concrete waiting condition that releases each dependency, and any separately defined stale/timeout condition for opaque waits. |
| Resume | `next_safe_action`, stop boundary and remaining human action. |

Resolve the authoritative change-contract locator and recover its preserved invariants and required acceptance evidence before resuming dependent work or claiming completion. Observed Evidence results do not define the required acceptance baseline. If that contract is unavailable, mark the affected action blocked rather than reconstructing requirements from a green check.

Bind member identity to its repository namespace; a bare PR number, branch name or SHA is insufficient across repositories/forks. Re-resolve stable provider/repository/member IDs before mutating, including after a rename or transfer. Where a provider lacks stable IDs, retain its fully qualified locator and explicit identity evidence; if identity remains ambiguous, block the mutation rather than following an alias by assumption.

For an interrupted mutation, distinguish this operation's owned effects from pre-existing or concurrent changes. Record only material owned paths/objects and completed boundary state, not a command transcript. Reconcile actual effects before retry, cleanup or rollback; a general diff is not proof of ownership. If ownership or the completed boundary cannot be recovered, do not overwrite, delete or roll back uncertain changes. Record the unresolved unit and preserve unrelated state.

Use `unknown`, `pending` and `not applicable` distinctly. An uninspected review surface is not evidence of zero findings. A CI observation needs its run locator and exact head binding, not just `CI: success`. Record observation time when freshness matters; do not turn this into a timestamp for every operation.

## Anti-stall diagnostic state

The anti-stall fields are the Work-ledger projection of the artifact-neutral requirements in `policy/core/repository-change-anti-stall.md`; they do not create a second diagnostic transcript or policy authority.

Use `attempted_paths` as a **strategy-level summary** of evidence routes that matter for the next decision, not a record of every endpoint or call. Do not record call-by-call diagnostic history such as “call 1 / call 2 / call 3”. Keep only enough negative and positive capability state to prevent repeated dead-end exploration and to explain the current strategy.

For each `invalidated_paths` entry, retain:

- path/capability or evidence route;
- observed invalidation reason;
- `applicability` scope such as current runtime, session, connector capability set, or authorization context; and
- `retry_condition`: concrete evidence of a relevant state change that would justify another attempt.

An invalidated path is not eligible for retry merely because a new session began. On resume, **restore invalidated paths before retrying** any diagnostic route. Retry only when the recorded retry condition is satisfied by evidence such as a changed runtime, newly exposed connector capability, refreshed authorization, or independently observed network recovery.

Track `strategy_attempt_count` against the deliberately selected strategy identity: objective, evidence source, diagnostic method, and hypothesis. Track observed failure mode per attempt for classification and retry reasoning; a changed failure outcome does not create a new strategy or reset its attempt count. Preserve **strategies already exhausted** and `strategy_switch_reason` so a successor can see why another evidence source or reproduction method was chosen. Recommended numeric baselines belong to the anti-stall policy; the ledger records the current budget state rather than inventing its own thresholds.

`diagnostic_budget` must include the current global no-material-progress bound state required by Policy, plus any narrower counters useful to the active procedure. A successful call that only reproduces known information advances the no-material-progress budget even though no failure counter advances.

`progress_frontier` and `last_material_progress` summarize the latest knowledge/repository/validation/review/qualification change. Tool activity without a decision-relevant delta does not move either field. The current orchestration state, when useful, distinguishes `external_wait`, `diagnostic_stall`, `blocked`, and `productive_parallel_work` rather than collapsing them into “waiting”.

For `external_wait`, record why the dependency is legitimately pending and the concrete resume condition. The provider does not need to expose granular changing progress: an unchanged `pending` or `in_progress` status can remain an external wait when the dependency identity is valid and its release condition is concrete. Record a separate stale/timeout/failure condition when the wait can no longer be treated as legitimate; do not reinterpret opaque provider status as agent `diagnostic_stall` by itself.

**Resume is not a restart.** Restore the current objective, failure scope, `evidence_gap`, `current_hypothesis`, invalidated paths, current strategy, strategies already exhausted, last material progress, and `next_safe_action` before new exploration. Selectively refresh only stale live facts whose binding matters to that safe action. If the checkpoint cannot establish whether a strategy was exhausted or a path was invalidated, preserve the uncertainty rather than silently assuming a clean diagnostic slate.

## Refresh and stale bindings

On discovery or resume, reconstruct the checkpoint if absent; then refresh materially stale facts needed for the next action. Preserve the starting snapshot separately from current observations. Verify observed member/base/dependency identities from the provider before relying on reconstructed topology. If the previous action may have succeeded before interruption, inspect its effect before retrying; do not create duplicate PRs, mutations or review requests.

When an adopted repository-tracked checkpoint is available, use it to narrow discovery according to the two-phase resume procedure in [Isolated repository-tracked Work ledger](repository-tracked-work-ledger.md). Validate the minimal live frontier first; do not treat cached state as permission to skip provider identity, current head, or other bindings needed for the next safe action.

Evaluate each observation by actual binding:

- **Head movement:** exact-head CI/review evidence for the old SHA cannot qualify the new SHA. Preserve its historical locator, mark its qualification binding stale, and acquire new exact-head evidence when the selected boundary requires it. Semantic implementation or repair progress can remain complete while qualification becomes pending.
- **Base/topology movement:** reassess affected dependency edges, cumulative scope and base-bound evidence. An unchanged head does not prove unchanged applicability. Unaffected evidence may be reused only when its bindings remain established.
- **Unchanged facts:** retain established task scope, member responsibility and unaffected facts. Do not mechanically discard all state or re-enumerate unchanged provider objects after every commit.
- **Unknown binding:** refresh the relevant fact before relying on it. A cached green run, provider thread count or ledger label cannot fill an unknown acceptance binding.

A construction head is not automatically a qualification head. Follow `pull-request.defer-revision-bound-qualification-until-required` and the [stacked workflow](stacked-pr-workflow.md): continue dependency-safe implementation, focused diagnostics and naturally triggered CI on provisional candidates. Freeze intended qualification heads only at the applicable authority boundary. Moving the stability frontier is planning state, not approval or merge readiness.

## Review-finding relationship

Keep finding details in the existing review-finding ledger defined by the bundled [review-finding ledger](../../pr-merge-gate/references/review-finding-ledger.md). The renderer imports this reference and its [disposition procedure](../../pr-merge-gate/references/review-feedback-disposition.md) from the canonical `pr-merge-gate` reference sources at the same toolchain revision; generated copies are not separately authored authority. **The review finding ledger remains authoritative** for review finding identity, disposition and closure evidence. The Work ledger records only the ledger reference, known-material-findings status and effect on next action, qualification, review acquisition or handoff. Do not duplicate disposition, repair reasoning, current-head validation or closure evidence as a second finding authority. Resolve disagreement by consulting the finding record and its evidence; a summary count cannot override it.

Before a new authorized review acquisition, apply the existing complete known-finding disposition and closure gate, including body-only findings. A repaired item may still be qualification-pending. A work checkpoint cannot declare that item closed for the boundary without the finding ledger's required current-head evidence. An interrupted request with uncertain delivery must be checked on the provider before any retry.

## Material checkpoints and next safe action

Update the current resumable checkpoint after a material transition: scope change, member creation, semantic head mutation, topology/frontier change, validation/qualification completion, material finding discovery or closure, review acquisition, blocker change, diagnostic strategy change that alters the recoverable evidence plan, or handoff. Consolidate compatible observations into that checkpoint; do not append a transcript of fetches, polls or every command. Execution-local state may change more frequently without provider writes.

Determine the **next safe action** from the selected mode, actual dependencies, evidence applicability, and current diagnostic state. Pending CI/review does not stop dependency-safe implementation on later members. A known prerequisite defect must not be propagated. A validated pending dependency with a concrete resume condition is `external_wait`, including when provider progress is opaque. While waiting, perform only `productive_parallel_work` that directly advances the completion frontier. When no useful authorized work remains while a result is pending, record the waiting condition and resume action; do not manufacture work or claim completion.

When repeated activity does not move `last_material_progress` or `progress_frontier`, record `diagnostic_stall` and switch strategy under the anti-stall policy rather than continuing equivalent retrieval/discovery. Record `blocked` only after authorized, in-scope alternate strategies are exhausted or unavailable.

At the selected completion / handoff boundary, reconstruct the report from the current checkpoint and linked evidence using [human-handoff](human-handoff.md) or the applicable merge gate. HANDOFF_READY requires the authorized work and validation to be complete and the required report to be reconstructible; it does not mean review complete or merge authorized. Preserve limitations and remaining human action explicitly.

If an explicit instruction requires stopping immediately after a final review request, persist the preflight checkpoint first and use the review request itself as the durable acquisition event linked to that checkpoint. After successful submission, stop without polling, a post-request checkpoint write or further repository work. Report the returned request locator and review OUTSTANDING. On later resume, reconcile that event into the checkpoint; a failed or ambiguous request is not evidence of successful acquisition.
