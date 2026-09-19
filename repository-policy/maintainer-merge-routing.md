---
id: policy-repo.maintainer-merge-routing
severity: mandatory
overridable: false
order: 1061
---
# Maintainer merge routing

This is the short discovery route for agents maintaining the `policy`
authority of `TakashiSasaki/templates`. It is not a product-repository
adoption instruction and it does not duplicate the landing rules.

Read the maintenance rule and its execution procedure from the same immutable
source snapshot before changing a maintenance PR:

- repository: `TakashiSasaki/templates`;
- revision: `04bf86977675bfc8f1082b8b8d6c70817f4eb9c2`;
- rule: `repository-policy/stacked-pr-landing.md`, blob
  `9761cdbcd21b0e8ba2f3eb2ffb306725a82f5eef`;
- landing Skill: `repository-skills/land-templates-stack/SKILL.md`, blob
  `06efa38681e374636bcabcbcb984be5ec43b47ee`;
- review scope planner: `repository-skills/land-templates-stack/scripts/plan_review_scope.py`, blob
  `16c0907a19e3f8d339fe81e29f7b204e791fc781`.

The Policy authority also exposes the thin local entry at
`.agents/skills/land-templates-stack/SKILL.md`; validate its adjacent
`source.json` before loading this procedure.

The Policy authority also exposes the thin local entry at
`.agents/skills/pr-merge-gate/SKILL.md`; validate its separate adjacent
`source.json` before loading the shared acceptance gate.

Resolve both paths with the declared revision and verify their blob identities;
do not read a same-named file from the consumer worktree, `policy` branch, or
an unverified local copy. If an object, path, SHA, or blob does not match,
stop as blocked.

The shared individual-PR acceptance gate is a separate immutable source,
even when stored in the same candidate commit:
`TakashiSasaki/templates@94eb84397d913f2ebb0e2c79d0b841ae580fbc31`,
`skills/pr-merge-gate/SKILL.md`, blob
`2ef890673600f0f4c30b53cef7c19a78d34cf5bc`. The Policy generation toolchain
is selected separately by `toolchain.revision` in `.agent-policy.yml`. Verify
that exact revision against `.agent-policy.lock`; the generated instruction
headers identify the selected toolchain. Do not substitute either maintainer
procedure revision for that configuration identity.

The route applies to a single PR and to a same-authority stack. Use the
canonical landing Skill to order members and invoke the shared gate; do not
merge, auto-merge, publish, deploy, or treat review and CI as interchangeable
evidence without the required human authorization boundary.
