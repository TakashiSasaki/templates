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

For agent-review-and-merge, stacked progression does not prescribe one review-acquisition method. Each member may establish its own completed independent exact-head review, or one completed review may cover multiple members through explicit cumulative coverage satisfying the canonical stacked-review bindings. A tip review or approval event alone does not cover lower members. After applicable review evidence is established, guarded bottom-up merge remains possible with applicability re-evaluated as bases move.

For human-handoff, construct and validate the ordered stack, do not initiate a new review request, do not merge or close any member, and stop at HANDOFF_READY with the whole stack open and unmerged.

When a lower member is later merged, retarget or re-evaluate later members as required. Do not mechanically discard every unaffected evidence item, and do not reuse evidence when a changed binding or applicability is unknown.
