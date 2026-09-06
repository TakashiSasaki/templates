<!-- agent-policy-generated: true -->
# Repository-change Work ledger

## Purpose and authority

Maintain a current resumable checkpoint for a repository change: its objective, dependency topology, useful next action, asynchronous dependencies, and completion boundary. The Work ledger is an operational projection / resumable index, not a new source of semantic acceptance policy. Repository contracts, policy, validation, review and merge procedures retain their authority.

The Work ledger is repository-associated, but not repository-tracked by default. GitHub commit SHAs, branch heads, pull requests, CI runs, reviews, review threads and merge state are canonical provider facts; ledger entries are observations of those facts. Other providers retain equivalent authority over their own objects. When an observation conflicts with live state, refresh the affected observation, not the provider fact to make it agree with the ledger. A ledger label such as `success`, `qualified` or `HANDOFF_READY` is not acceptance evidence.

Product current semantic state and validated lifecycle history remain owned by their product contracts and lifecycle authorities. The Work ledger neither replaces those artifacts nor establishes product acceptance. It is not a review-finding authority, a transcript, a mandatory schema, an automatic next-action engine, or permission to expand scope or merge.

## Storage and discovery

Prefer one canonical provider-side checkpoint surface per work scope:

1. an identifiable Work ledger comment on the stack tip PR;
2. a Work ledger comment on a standalone PR;
3. a tracking issue for pre-PR, multi-stack or long-running work; and
4. execution-local state as a high-frequency checkpoint supplement.

Use the supported equivalent on other providers. Identify the canonical surface in the PR body or tracking issue so another session can discover it. If the tip changes, move the checkpoint only when useful, leave a forwarding locator at the former surface, and mark it superseded. A multi-stack issue may index separate authority-local stacks; it must not imply shared branch history or duplicate their detailed checkpoints. If several purported canonical surfaces conflict, reconstruct from live facts and explicitly select one before relying on either. Do not silently overwrite another worker's update. Use an atomic provider version/compare-and-swap guard when available. A pre-write read and reconciliation alone do not protect against a concurrent write. Without a conditional update, use an established single writer with serialized handoff, or append immutable checkpoint comments that identify their predecessor and work scope. Competing successors are a conflict, not last-write-wins state: preserve both, reconcile from live facts, and designate the successor before relying on it. Never edit a shared pointer/comment concurrently without a guard; discover append-only successors from the thread instead. If exclusive ownership or reconciliation cannot be established, pause the conflicting write and report the limitation. This procedure does not require a new lock service or updater.

Do not create a repository file solely to store operational progress. In particular, do not commit `.work-ledger.json` merely to satisfy this procedure. Repository files are appropriate when the information itself is authoritative product state, a contract, or formal lifecycle evidence, or when independent repository authority explicitly requires that storage. This is not a mandatory JSON/YAML artifact.

A progress-only commit changes the candidate SHA, stales exact-head CI/review evidence, changes qualification bindings, and can demand another ledger update. Provider-side checkpoints avoid this evidence churn without weakening immutable acceptance evidence. A committed illustrative example is procedure documentation, not a live runtime ledger.

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
| Dependencies | Blockers, asynchronous dependencies and the concrete waiting condition that releases each dependency. |
| Resume | Next safe action, stop boundary and remaining human action. |

Resolve the authoritative change-contract locator and recover its preserved invariants and required acceptance evidence before resuming dependent work or claiming completion. Observed Evidence results do not define the required acceptance baseline. If that contract is unavailable, mark the affected action blocked rather than reconstructing requirements from a green check.

Bind member identity to its repository namespace; a bare PR number, branch name or SHA is insufficient across repositories/forks. Re-resolve stable provider/repository/member IDs before mutating, including after a rename or transfer. Where a provider lacks stable IDs, retain its fully qualified locator and explicit identity evidence; if identity remains ambiguous, block the mutation rather than following an alias by assumption.

For an interrupted mutation, distinguish this operation's owned effects from pre-existing or concurrent changes. Record only material owned paths/objects and completed boundary state, not a command transcript. Reconcile actual effects before retry, cleanup or rollback; a general diff is not proof of ownership. If ownership or the completed boundary cannot be recovered, do not overwrite, delete or roll back uncertain changes. Record the unresolved unit and preserve unrelated state.

Use `unknown`, `pending` and `not applicable` distinctly. An uninspected review surface is not evidence of zero findings. A CI observation needs its run locator and exact head binding, not just `CI: success`. Record observation time when freshness matters; do not turn this into a timestamp for every operation.

## Refresh and stale bindings

On discovery or resume, reconstruct the checkpoint if absent; then refresh materially stale facts needed for the next action. Preserve the starting snapshot separately from current observations. Verify observed member/base/dependency identities from the provider before relying on reconstructed topology. If the previous action may have succeeded before interruption, inspect its effect before retrying; do not create duplicate PRs, mutations or review requests.

Evaluate each observation by actual binding:

- **Head movement:** exact-head CI/review evidence for the old SHA cannot qualify the new SHA. Preserve its historical locator, mark its qualification binding stale, and acquire new exact-head evidence when the selected boundary requires it. Semantic implementation or repair progress can remain complete while qualification becomes pending.
- **Base/topology movement:** reassess affected dependency edges, cumulative scope and base-bound evidence. An unchanged head does not prove unchanged applicability. Unaffected evidence may be reused only when its bindings remain established.
- **Unchanged facts:** retain established task scope, member responsibility and unaffected facts. Do not mechanically discard all state or re-enumerate unchanged provider objects after every commit.
- **Unknown binding:** refresh the relevant fact before relying on it. A cached green run, provider thread count or ledger label cannot fill an unknown acceptance binding.

A construction head is not automatically a qualification head. Follow `pull-request.defer-revision-bound-qualification-until-required` and the [stacked workflow](stacked-pr-workflow.md): continue dependency-safe implementation, focused diagnostics and naturally triggered CI on provisional candidates. Freeze intended qualification heads only at the applicable authority boundary. Moving the stability frontier is planning state, not approval or merge readiness.

## Review-finding relationship

Keep finding details in the existing review-finding ledger defined by the bundled [review-finding ledger](review-finding-ledger.md). The renderer imports this reference and its [disposition procedure](review-feedback-disposition.md) from the canonical `pr-merge-gate` reference sources at the same toolchain revision; generated copies are not separately authored authority. The Work ledger records only the ledger reference, known-material-findings status and effect on next action, qualification, review acquisition or handoff. Do not duplicate disposition, repair reasoning, current-head validation or closure evidence as a second finding authority. Resolve disagreement by consulting the finding record and its evidence; a summary count cannot override it.

Before a new authorized review acquisition, apply the existing complete known-finding disposition and closure gate, including body-only findings. A repaired item may still be qualification-pending. A work checkpoint cannot declare that item closed for the boundary without the finding ledger's required current-head evidence. An interrupted request with uncertain delivery must be checked on the provider before any retry.

## Material checkpoints and next safe action

Update the current resumable checkpoint after a material transition: scope change, member creation, semantic head mutation, topology/frontier change, validation/qualification completion, material finding discovery or closure, review acquisition, blocker change, or handoff. Consolidate compatible observations into that checkpoint; do not append a transcript of fetches, polls or every command. Execution-local state may change more frequently without provider writes.

Determine the **next safe action** from the selected mode, actual dependencies and evidence applicability. Pending CI/review does not stop dependency-safe implementation on later members. A known prerequisite defect must not be propagated. When no useful authorized work remains while a result is pending, record the waiting condition and resume action; do not manufacture work or claim completion.

At the selected completion / handoff boundary, reconstruct the report from the current checkpoint and linked evidence using [human-handoff](human-handoff.md) or the applicable merge gate. HANDOFF_READY requires the authorized work and validation to be complete and the required report to be reconstructible; it does not mean review complete or merge authorized. Preserve limitations and remaining human action explicitly.

If an explicit instruction requires stopping immediately after a final review request, persist the preflight checkpoint first and use the review request itself as the durable acquisition event linked to that checkpoint. After successful submission, stop without polling, a post-request checkpoint write or further repository work. Report the returned request locator and review OUTSTANDING. On later resume, reconcile that event into the checkpoint; a failed or ambiguous request is not evidence of successful acquisition.
