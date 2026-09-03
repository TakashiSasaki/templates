<!-- agent-policy-generated: true -->
# Serial pull-request workflow

Use this procedure when serial-pr is selected. Serial progression controls construction ordering only. The selected completion strategy decides whether the current member proceeds into review/merge or stops after validation.

For every coherent change member:

1. establish the effective scope and applicable acceptance requirements;
2. implement the member; and
3. run focused and required validation.

Then apply the selected completion strategy:

### agent-review-and-merge

4. expose the current member to required CI and establish completed independent exact-head review evidence;
5. verify or falsify findings and apply justified remediation;
6. revalidate the current head and applicable merge evidence;
7. complete the guarded merge procedure before merging; and
8. begin the next member only after that member's merge boundary is complete.

### human-handoff

4. do not initiate a new review request;
5. do not merge or close the pull request;
6. report review as NOT_REQUESTED or OUTSTANDING and merge authorization as NOT_ESTABLISHED; and
7. stop at HANDOFF_READY with the validated member open and unmerged.

A later continuation may acquire review and merge evidence under the then-applicable authority. Human handoff does not waive those later requirements. A missing review, unresolved CI discovery, stale evidence, unknown base drift, or failed merge guard remains blocking when agent-review-and-merge is selected and the pull-request merge policy applies.
