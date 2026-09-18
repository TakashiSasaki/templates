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
- revision: `5af977020fca701bcf6b7fb7ce12ca077b2d7220`;
- rule: `repository-policy/stacked-pr-landing.md`, blob
  `9dd1c5498dd9b37ef91afd65ad400fbdee13ee29`;
- landing Skill: `repository-skills/land-templates-stack/SKILL.md`, blob
  `902b6e543d467b47b2b91819bfab5574a85456c7`.

Resolve both paths with the declared revision and verify their blob identities;
do not read a same-named file from the consumer worktree, `policy` branch, or
an unverified local copy. If an object, path, SHA, or blob does not match,
stop as blocked.

The shared individual-PR acceptance gate is a separate immutable source:
`TakashiSasaki/templates@733c86941f8154f301a225054d88c6b8a477058a`,
`skills/pr-merge-gate/SKILL.md`, blob
`cb12e6aa296a0ba4e7871dc57b554ef867eeefed`. The Policy generation toolchain
pin remains separate at
`TakashiSasaki/templates@33a7ab809225c2a8b8dd2598ef04d0a39cf076a7`.

The route applies to a single PR and to a same-authority stack. Use the
canonical landing Skill to order members and invoke the shared gate; do not
merge, auto-merge, publish, deploy, or treat review and CI as interchangeable
evidence without the required human authorization boundary.
