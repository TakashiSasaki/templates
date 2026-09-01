<!--
agent-policy-generated: true
source-skill: pr-review
DO NOT EDIT DIRECTLY
-->
# Canonical automated GitHub pull-request review invocation

This is a **non-normative invocation template**, not a review procedure, semantic policy, or GitHub output contract. The installed `pr-review` Skill is the sole procedural authority. The explicitly bound semantic projection and GitHub adapter remain the authorities for review semantics and transport respectively.

Repository: `<repository>`
Pull request: `<pull-request-number>`
Policy configuration: `{{ config_path }}`
Semantic review projection: `<repository-relative-semantic-output-path>`
GitHub adapter projection: `<repository-relative-github-adapter-output-path>`
Trusted policy revision: `<optional-full-commit-sha; omit to use the exact current PR base revision>`

Invoke the installed `pr-review` Skill with these inputs and follow that Skill exactly. Do not infer missing output bindings from context names, do not use proposed-head policy material as the trusted authority for the same review, and do not reconstruct review semantics or GitHub transport rules from this invocation template.

If an input required by the Skill is missing or inconsistent, follow the Skill's fail-closed behavior rather than inventing a review procedure here.
