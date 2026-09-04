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

Keep review roles distinct. Individual independent exact-head review is the ordinary merge-acceptance path for each current member. A final whole-stack review is primarily an architecture/dependency/completeness audit: inspect dependency edges, overlap or gaps, design consistency, final-state behavior, test sufficiency, and unintended scope. It is not lower-member merge evidence merely because it reviewed the stack tip. Cumulative multi-member acceptance review is optional and may be used only when every canonical stacked-review binding is explicit.

For agent-review-and-merge, if cumulative coverage is incomplete or the provider cannot clearly attest lower-member bindings, preserve useful audit findings and use individual exact-head review for uncovered members instead of repeatedly requesting cumulative clarification or review. A tip review or approval event alone does not cover lower members. After applicable review evidence is established, guarded bottom-up merge remains possible with applicability re-evaluated as bases move.

For human-handoff, construct and validate the ordered stack and do not acquire merge-acceptance review by default. If an explicit task instruction requires one final whole-stack architecture audit before handoff, issue only that authorized audit after the complete stack is stable enough for handoff, do not treat it as per-member merge evidence, do not wait for its completion unless explicitly required, and do not use it to authorize a merge. Then stop at HANDOFF_READY with the whole stack open and unmerged.

When a lower member is later merged, retarget or re-evaluate later members as required. Do not mechanically discard every unaffected evidence item, do not rewrite an upper head solely because its lower base merged when applicability remains established, and do not reuse evidence when a changed binding or applicability is unknown.
