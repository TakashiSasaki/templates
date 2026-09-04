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

Do not deliberately propagate a known material defect into later members. A later member may depend on an earlier open PR, but the dependency must remain explicit. Cumulative review can cover multiple members only through the exact binding required by the canonical stacked-review coverage rule; a tip review or approval event alone does not cover lower members.

When a lower member is later merged, retarget or re-evaluate later members as required. Do not mechanically discard every unaffected evidence item, and do not reuse evidence when a changed binding or applicability is unknown.
