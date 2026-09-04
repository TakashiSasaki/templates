<!-- agent-policy-generated: true -->
# Human-handoff completion

Use this procedure when human-handoff is selected.

Human handoff is a normal completion boundary after the authorized implementation and validation work is complete. It does not waive any later independent review requirement, establish merge authorization, or imply that the pull requests are merge-ready.

At this boundary:

- do not initiate merge-acceptance review through reviewer assignment, provider invocation, requested-reviewer state, or any other review-request mechanism by default;
- an explicit task instruction may authorize one final whole-stack architecture/dependency/completeness audit before handoff; for a stacked workflow, request that audit only after every member is frozen at its intended final head and all applicable required CI for those exact heads has completed successfully; such an audit is not per-member merge evidence unless all canonical cumulative bindings are independently established, and it must not create a review-retry loop or merge authorization;
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
