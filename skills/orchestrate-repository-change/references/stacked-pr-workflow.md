<!-- agent-policy-generated: true -->
# Stacked pull-request workflow

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

Review latency alone does not move the frontier backward and does not block dependency-safe implementation above it. If a lower member is still being validated or reviewed but no known defect prevents later work, construct later members on the current exact parent head and keep the dependency explicit. Do not create a cosmetic or mechanical lower-head rewrite merely to make a stable member appear fresh.

A known material upstream defect is different from review latency. Do not deliberately build later work on behavior already known to require semantic correction when that correction invalidates the prerequisite. When dependency-safe later implementation can proceed without embedding the defective assumption, it may continue, but preserve the unresolved dependency explicitly.

When a known upstream semantic repair will necessarily stale a downstream immutable identity, provenance value, generated projection, signed artifact, or other revision-bound materialization, defer that downstream **final materialization** until the upstream identity is stable enough to bind. This does not prohibit implementation of the downstream logic, tests, schemas, adapters, or other dependency-safe work. It prevents knowingly manufacturing final immutable evidence that must immediately be replaced.

When a lower member later merges or its base identity changes, re-evaluate upper members according to actual bindings. If an upper head and its semantic diff remain valid without modification, do not mechanically rewrite the upper head solely to record the lower merge. If a changed base actually alters content, applicability, provenance, generated output, or required evidence, update only the affected members and invalidate only the evidence whose binding changed.

Before intentionally requesting a final revision-bound whole-stack review, move the intended stack to a final stability frontier: freeze the exact candidate heads that are intended to be reviewed and avoid further planned head mutation. A subsequent justified repair may move the frontier again, but the old review candidate then becomes stale according to its actual bindings.

## Candidate stabilization and review sequencing

Before intentionally starting expensive acceptance review for a member, stabilize that candidate as far as reasonably possible: complete the authorized implementation, disposition known self-audit findings, finish focused validation, establish required generated-projection coherence, batch known compatible head-changing repairs, resolve known material defects, and finish any upstream semantic repair that is known to make downstream immutable identity materialization stale. This is not a timer, perfection requirement, PR-creation gate, or reason to wait for earlier CI/review. Continue useful dependent implementation while earlier members stabilize when safe, and do not deliberately review a knowingly intermediate downstream head.

Before intentionally requesting a final whole-stack review, freeze every stack member at its intended final candidate head and require all applicable required CI for those exact heads to have completed successfully. Then apply the canonical `pull-request.disposition-known-findings-before-review-reacquisition` rule to the complete logical finding backlog represented by `skills/pr-merge-gate/references/review-finding-ledger.md`. Every known material actionable finding must already have either a repair validated for the current proposed head or an evidence-backed no-change disposition validated against the current proposed head and applicable authority, and the required finding-level closure evidence must be recorded on an auditable review or pull-request surface. If any known material item lacks that validated outcome or closure evidence, do not invoke the whole-stack reviewer. CI completion does not block construction of later members; this sequencing applies to final revision-bound review acquisition after the stack is stabilized. Pending required CI blocks the final review request. Failed or cancelled required CI requires repair or explicit disposition and requalification before review. If any reviewed candidate head changes, reacquire the required CI for the affected exact heads before requesting the replacement final review, and re-evaluate the complete known-finding gate immediately before reviewer invocation.

Keep review roles distinct. Individual independent exact-head review is the ordinary merge-acceptance path for each current member. A final whole-stack review is primarily an architecture/dependency/completeness audit: inspect dependency edges, overlap or gaps, design consistency, final-state behavior, test sufficiency, and unintended scope. It is not lower-member merge evidence merely because it reviewed the stack tip. Cumulative multi-member acceptance review is optional and may be used only when every canonical stacked-review binding is explicit.

For agent-review-and-merge, if cumulative coverage is incomplete or the provider cannot clearly attest lower-member bindings, preserve useful audit findings and use individual exact-head review for uncovered members instead of repeatedly requesting cumulative clarification or review. A tip review or approval event alone does not cover lower members. After applicable review evidence is established, guarded bottom-up merge remains possible with applicability re-evaluated as bases move.

For human-handoff, construct and validate the ordered stack and do not acquire merge-acceptance review by default. If an explicit task instruction requires one final whole-stack architecture audit before handoff, issue only that authorized audit after the complete stack is stabilized, all applicable required CI for every exact final member head has completed successfully, and the same canonical complete-ledger reacquisition gate above has been satisfied. Recheck that gate immediately before reviewer invocation; if any known material finding lacks a current-head validated repair or evidence-backed no-change disposition plus required closure evidence, do not request the audit. Do not treat the audit as per-member merge evidence, do not wait for its completion unless explicitly required, and do not use it to authorize a merge. Then stop at HANDOFF_READY with the whole stack open and unmerged.

When a lower member is later merged, retarget or re-evaluate later members as required. Do not mechanically discard every unaffected evidence item, do not rewrite an upper head solely because its lower base merged when applicability remains established, and do not reuse evidence when a changed binding or applicability is unknown.
