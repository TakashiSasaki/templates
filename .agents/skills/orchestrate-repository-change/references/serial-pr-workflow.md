<!-- agent-policy-generated: true -->
# Serial pull-request workflow

Use this procedure when serial-pr is selected.

For each coherent change member:

1. establish the effective scope and applicable acceptance requirements;
2. implement the member;
3. run focused and required validation;
4. expose the member to required CI and independent exact-head review;
5. verify or falsify findings and apply justified remediation;
6. revalidate the current head and applicable merge evidence;
7. complete the guarded merge procedure before merging; and
8. begin the next member only after the selected merge boundary is complete.

This ordering is a progression strategy, not a replacement for canonical policy. A missing review, unresolved CI discovery, stale evidence, unknown base drift, or failed merge guard remains blocking when the pull-request policy applies.
