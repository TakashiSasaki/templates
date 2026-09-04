<!-- agent-policy-generated: true -->
# Human-handoff completion

Use this procedure when human-handoff is selected.

Human handoff is a normal completion boundary after the authorized implementation and validation work is complete. It does not waive any later independent review requirement, establish merge authorization, or imply that the pull requests are merge-ready.

At this boundary:

- do not issue an automated review request;
- do not merge or close a pull request;
- do not create a no-op commit solely to trigger CI or review;
- do not make an approval-only mutation;
- report implementation and validation states separately;
- report independent review as NOT_REQUESTED or OUTSTANDING;
- report merge authorization as NOT_ESTABLISHED;
- report merge performed as NO; and
- leave every stack member open and unmerged.

Use HANDOFF_READY only when the handoff report includes exact branch, PR, base, head, stack membership, validation, CI observations, limitations, and remaining human actions. HANDOFF_READY is not REVIEW_COMPLETE, MERGE_READY, or MERGED.
