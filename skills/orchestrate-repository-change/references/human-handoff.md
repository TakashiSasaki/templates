<!-- agent-policy-generated: true -->
# Human-handoff completion

## Recoverable handoff

Use [Work ledger](work-ledger.md) and its evidence locators to reconstruct the HANDOFF_READY report: starting/current authority observations, exact member/base/head topology, scope, completed/deferred mutation units, stability/qualification state, validation and CI bindings, review acquisition role, finding-ledger reference, blockers and remaining human action. Refresh materially stale facts before claiming the boundary is met. The checkpoint is an index and cannot substitute for the required evidence.

For an authorized final diagnostic review with an immediate-stop instruction, persist the preflight Work ledger checkpoint before invoking the reviewer. Bind the request to that checkpoint and the intended exact heads. Successful submission itself is the durable acquisition event: stop immediately, report its locator and OUTSTANDING, and do not poll or issue a post-request checkpoint update. On a later authorized resume, reconcile the event before considering a retry. All existing complete-ledger disposition, closure and exact-head qualification gates below still apply.

Use this procedure when human-handoff is selected.

Human handoff is a normal completion boundary after the authorized implementation and validation work is complete. It does not waive any later independent review requirement, establish merge authorization, or imply that the pull requests are merge-ready.

At this boundary:

- do not initiate merge-acceptance review through reviewer assignment, provider invocation, requested-reviewer state, or any other review-request mechanism by default;
- an explicit task instruction may authorize one final whole-stack architecture/dependency/completeness audit before handoff; for a stacked workflow, request that audit only after every member is frozen at its intended final head, all applicable required CI for those exact heads has completed successfully, and the canonical `pull-request.disposition-known-findings-before-review-reacquisition` rule has been applied to the complete logical finding backlog from `skills/pr-merge-gate/references/review-finding-ledger.md`; every known material actionable finding must have a current-head validated repair or evidence-backed no-change disposition and the required finding-level closure evidence recorded on an auditable review or pull-request surface; recheck this complete-ledger gate immediately before reviewer invocation and do not request the audit while any known material finding lacks that validated outcome or closure evidence; such an audit is not per-member merge evidence unless all canonical cumulative bindings are independently established, and it must not create a review-retry loop or merge authorization;
- existing reviews may be observed, inspected, and reported without treating handoff as new acceptance-review acquisition;
- do not merge or close a pull request;
- do not create a no-op commit solely to trigger CI or review;
- do not make an approval-only mutation;
- report implementation and validation states separately;
- report per-member independent review as NOT_REQUESTED or OUTSTANDING unless pre-existing applicable evidence truthfully establishes another observed state;
- report any explicitly authorized whole-stack audit separately from merge-acceptance evidence;
- report merge authorization as NOT_ESTABLISHED;
- report merge performed as NO; and
- leave every applicable pull request or stack member open and unmerged.

Use HANDOFF_READY only when the handoff report includes exact branch, PR, base, head, stack membership when applicable, validation, CI observations, limitations, and remaining human actions. HANDOFF_READY does not by itself imply REVIEW_COMPLETE, MERGE_READY, or MERGED.
