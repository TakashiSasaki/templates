<!-- agent-policy-generated: true -->
# Stacked pull-request workflow

## Resumable stack checkpoint

Apply [Work ledger](work-ledger.md) when constructing or resuming the stack. Preserve ordered PR/branch members, base and exact head bindings, semantic responsibility, cumulative scope, provisional state and the stability frontier on the **selected canonical operational surface**. Provider-side PR/Issue checkpointing remains the default; when the consumer or repository authority explicitly adopts the isolated repository-tracked backend, use that repository-tracked operational ref as the canonical stack checkpoint and do not maintain a competing provider-side canonical checkpoint. Checkpoint member creation, justified head/topology movement and qualification completion. CI waiting does not block dependency-safe later implementation. On resume, follow the selected backend's recovery/concurrency procedure, refresh affected provider bindings and consult the referenced review-finding ledger before choosing the next safe action; do not reset completed semantic repairs solely because their qualification head changed.

Use this procedure when stacked-pr is selected.

Construct an explicit dependency topology in which every member has one coherent semantic purpose, an understandable local diff, and an inspectable cumulative diff. For each member:

1. implement and validate the member on the exact head of its parent member;
2. create an open pull request whose base is the parent branch;
3. record the parent branch, local base, member head, and cumulative scope;
4. continue to the next member without waiting for review completion when no known material defect invalidates the prerequisite;
5. validate the next member against the cumulative parent state; and
6. qualify the whole ordered stack under the selected completion strategy.

Do not deliberately propagate a known material defect into later members. A later member may depend on an earlier open PR, but the dependency must remain explicit.

## Stability frontier

Track a practical stability frontier through the ordered stack. A member is at the stability frontier when, based on currently known work, no further head change is planned unless a new material defect, authority decision, scope correction, conflict, or other justified mutation appears. This is a planning state for controlling descendant churn. It does not mean the member is merged, reviewed, approved, immutable forever, or independently merge-ready.

Apply the canonical `pull-request.defer-revision-bound-qualification-until-required` rule while constructing the stack. A member's current exact Git commit is its construction head; that exact identity is required to preserve dependency topology, but its existence does not by itself make the member a final qualification head. A locally complete descendant may remain a provisional candidate while prerequisite identities or compatible remediation work are still expected to move. Preserve its logical member responsibility and semantic delta instead of repeatedly treating each transient descendant SHA as a new final acceptance candidate.

Review latency alone does not move the frontier backward and does not block dependency-safe implementation above it. If a lower member is still being validated or reviewed but no known defect prevents later work, construct later members on the current exact parent head and keep the dependency explicit. Do not create a cosmetic or mechanical lower-head rewrite merely to make a stable member appear fresh.

A known material upstream defect is different from review latency. Do not deliberately build later work on behavior already known to require semantic correction when that correction invalidates the prerequisite. When dependency-safe later implementation can proceed without embedding the defective assumption, it may continue, but preserve the unresolved dependency explicitly.

Before an applicable authority-defined review, merge, provenance, release, publication, or other revision-bound boundary requires final qualification, do not deliberately freeze provisional descendants or manufacture final immutable evidence merely because exact construction heads already exist. When a known upstream semantic repair will necessarily stale a downstream immutable identity, provenance value, generated projection, signed artifact, or other revision-bound materialization, defer that downstream **final materialization** until the upstream identity is stable enough to bind. This does not prohibit implementation of the downstream logic, tests, schemas, adapters, focused diagnostics, pull-request creation, or naturally triggered CI. It prevents knowingly manufacturing final immutable evidence that must immediately be replaced and prevents avoidable final qualification whose prerequisite binding is still intentionally provisional.

When a lower member later merges or its base identity changes, re-evaluate upper members according to actual bindings. If an upper head and its semantic diff remain valid without modification, do not mechanically rewrite the upper head solely to record the lower merge. If a changed base actually alters content, applicability, provenance, generated output, or required evidence, update only the affected members and invalidate only the evidence whose binding changed.

Before intentionally requesting a final revision-bound whole-stack review, move the intended stack to a final stability frontier: freeze the exact candidate heads that are intended to be reviewed as the stack's qualification heads and avoid further planned head mutation. A subsequent justified repair may move the frontier again, but the old review candidate then becomes stale according to its actual bindings.

## Candidate stabilization and review sequencing

Before intentionally starting expensive acceptance review for a member, stabilize that candidate as far as reasonably possible: complete the authorized implementation, disposition known self-audit findings, finish focused validation, establish required generated-projection coherence, batch known compatible head-changing repairs, resolve known material defects, and finish any upstream semantic repair or other prerequisite movement known to make downstream immutable materialization stale. This is not a timer, perfection requirement, PR-creation gate, or reason to wait for earlier CI/review. Continue useful dependent implementation while earlier members stabilize when safe, keep provisional descendants explicit, and do not deliberately review a knowingly intermediate downstream head.

Before intentionally requesting a final whole-stack review, freeze every stack member at its intended final candidate head as its qualification head and require all applicable required CI for those exact heads to have completed successfully. Then apply the canonical `pull-request.disposition-known-findings-before-review-reacquisition` rule to the complete logical finding backlog represented by `skills/pr-merge-gate/references/review-finding-ledger.md`. Every known material actionable finding must already have either a repair validated for the current proposed head or an evidence-backed no-change disposition validated against the current proposed head and applicable authority, and the required finding-level closure evidence must be recorded on an auditable review or pull-request surface. If any known material item lacks that validated outcome or closure evidence, do not invoke the whole-stack reviewer. CI completion does not block construction of later members; this sequencing applies to final revision-bound review acquisition after the stack is stabilized. Pending required CI blocks the final review request. Failed or cancelled required CI requires repair or explicit disposition and requalification before review. If any reviewed candidate head changes, reacquire the required CI for the affected exact heads before requesting the replacement final review, and re-evaluate the complete known-finding gate immediately before reviewer invocation.

Keep review roles distinct. Individual independent exact-head review is the ordinary merge-acceptance path for each current member. A final whole-stack review is primarily an architecture/dependency/completeness audit: inspect dependency edges, overlap or gaps, design consistency, final-state behavior, test sufficiency, and unintended scope. It is not lower-member merge evidence merely because it reviewed the stack tip. Cumulative multi-member acceptance review is optional and may be used only when every canonical stacked-review binding is explicit.

For agent-review-and-merge, if cumulative coverage is incomplete or the provider cannot clearly attest lower-member bindings, preserve useful audit findings and use individual exact-head review for uncovered members instead of repeatedly requesting cumulative clarification or review. A tip review or approval event alone does not cover lower members. After applicable review evidence is established, guarded bottom-up merge remains possible with applicability re-evaluated as bases move.

For human-handoff, construct and validate the ordered stack and do not acquire merge-acceptance review by default. If an explicit task instruction requires one final whole-stack architecture audit before handoff, issue only that authorized audit after the complete stack is stabilized, all applicable required CI for every exact final member head has completed successfully, and the same canonical complete-ledger reacquisition gate above has been satisfied. Recheck that gate immediately before reviewer invocation; if any known material finding lacks a current-head validated repair or evidence-backed no-change disposition plus required closure evidence, do not request the audit. Record that gate result as part of the audit-request evidence so the request is auditable. Do not treat the audit as per-member merge evidence, do not wait for its completion unless explicitly required, and do not use it to authorize a merge. Then stop at HANDOFF_READY with the whole stack open and unmerged.

## Stacked pull-request landing and qualification evidence reuse

When landing stacked pull requests base-to-tip, mechanical full CI reruns on each member after each merge introduce severe execution latency and wasteful pipeline re-execution. Orchestration implements the canonical policy principle:

> **Merge progression does not itself invalidate qualification evidence. A change to the qualified candidate state or to an evidence binding does.**

### Standard landing procedure

During sequential landing of an ordered stack, execute the following procedure for each member:

1. **Land current stack member**: Merge the current stack member using the authorized merge procedure.
2. **Refresh next member's live state**: Fetch and observe the live state of the next member.
3. **Verify member preconditions**: Check target base, current head, mergeability, effective candidate tree, and provider required-check policies.
4. **Compare existing qualification evidence bindings**: Inspect existing qualification runs and verify whether their candidate tree, environment, workflow, and context bindings match the current candidate.
5. **Evaluate applicability per evidence item**: Categorize each qualification check into `applicable`, `stale`, or `unknown`. An `unknown` outcome must fail closed and be treated as stale.
6. **Reuse applicable evidence**: Rely on existing applicable qualification evidence whose candidate tree and required bindings remain unchanged.
7. **Reacquire only stale / unknown evidence**: Selectively schedule or execute only the validations whose bindings or tree were invalidated or unknown.
8. **Progress to next member**: Once all required qualification conditions for the member are satisfied, proceed to landing or merge authorization, then repeat the sequence for the subsequent stack member.

### Anti-pattern to avoid

Do **not** adopt the blind full-suite rerun pattern:

```text
merge A
  -> rerun every CI on B
  -> wait
  -> merge B
  -> rerun every CI on C
  -> wait
  -> ...
```

Instead, apply selective qualification applicability evaluation:

```text
merge A
  -> refresh B
  -> evaluate existing evidence applicability
  -> rerun only invalidated qualification
  -> continue
```

When a lower member is later merged, retarget or re-evaluate later members as required. Do not mechanically discard every unaffected evidence item, do not rewrite an upper head solely because its lower base merged when applicability remains established, and do not reuse evidence when a changed binding or applicability is unknown.
