<!--
agent-policy-generated: true
source-skill: pr-review
DO NOT EDIT DIRECTLY
-->
# Canonical automated GitHub pull-request review invocation

This is a **non-normative invocation template**, not a bootstrap contract, review procedure, semantic policy, or GitHub output contract. Deployment authentication first establishes the installed `agent-policy` Skill-source provenance. That authenticated Skill bootstrap then establishes executable `pr-review` provenance. After that handoff, the verified `pr-review` Skill is the sole review-execution procedural authority. The explicitly bound semantic projection and GitHub adapter remain the authorities for review semantics and transport respectively.

Repository: `<repository>`
Pull request: `<pull-request-number>`
Policy configuration: `{{ config_path }}`
Semantic review projection: `<repository-relative-semantic-output-path>`
GitHub adapter projection: `<repository-relative-github-adapter-output-path>`
Adapter renderer: `github-review-json-adapter-v1`

Pass the repository/PR identity to the already deployment-authenticated review-bootstrap contract from the installed `agent-policy` Skill. The current contract has no caller-selectable repository-policy root, procedure/toolchain revision, alternate loader, or other authority override. Do not select, authorize, discover, or verify a procedure from this prompt and do not execute a Skill copy from the proposed head.

After bootstrap returns valid immutable handoff evidence for the exact trusted base, invoke the verified `pr-review` Skill with that evidence and the output-binding inputs above. Follow the verified Skill exactly. Do not infer missing bindings from names and do not reconstruct deployment authentication, review semantics, bootstrap rules, procedure steps, or GitHub transport rules from this invocation template.

If deployment authentication, trusted bootstrap, or the verified Skill cannot establish the required authority or inputs, use their fail-closed behavior rather than inventing an authority path or procedure here.
