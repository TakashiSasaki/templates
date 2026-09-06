<!-- agent-policy-generated: true -->
# Serial pull-request workflow

## Resumable member checkpoint

Apply [Work ledger](work-ledger.md) to the current member, its exact base/head evidence, completed mutation units and next safe action. Reconstruct provider state before retrying an interrupted mutation, review request or guarded merge. Under agent-review-and-merge, use the existing merge gate to qualify, disposition findings and verify the merge before advancing; the checkpoint cannot authorize it. Under human-handoff, retain the open member and required report evidence on the durable surface, following the selected stop boundary.

Use this procedure when serial-pr is selected. Serial progression controls construction ordering only. The selected completion strategy decides whether the current member proceeds into review/merge or stops after validation with an open pull request.

For every coherent change member:

1. establish the effective scope and applicable acceptance requirements;
2. implement the member;
3. run focused and required validation; and
4. create or ensure an open pull request for the exact validated member without initiating review acquisition. When opening or marking a pull request ready would automatically invoke review, keep or create the pull request in a non-review-triggering state such as draft until the selected completion procedure authorizes review acquisition.

Then apply the selected completion strategy:

### agent-review-and-merge

5. expose the current member to required CI and establish completed independent exact-head review evidence;
6. verify or falsify findings and apply justified remediation;
7. revalidate the current head and applicable merge evidence;
8. complete the guarded merge procedure before merging; and
9. begin the next member only after that member's merge boundary is complete.

### human-handoff

5. do not initiate a new review request;
6. do not merge or close the pull request;
7. report the observed review state truthfully: use NOT_REQUESTED or OUTSTANDING when no applicable pre-existing evidence establishes another state, and preserve REVIEW_COMPLETE when applicable pre-existing evidence already establishes completed review;
8. report merge authorization as NOT_ESTABLISHED; and
9. stop at HANDOFF_READY with the validated member pull request open and unmerged.

A later continuation may acquire review and merge evidence under the then-applicable authority. Human handoff does not waive those later requirements. A missing review, unresolved CI discovery, stale evidence, unknown base drift, or failed merge guard remains blocking when agent-review-and-merge is selected and the pull-request merge policy applies.
