---
id: skill-source.preserve-distribution-integrity
severity: mandatory
overridable: false
order: 1010
---
# Preserve the exact copyable distribution

`distribution-manifest.json` is authoritative for the closed copyable inventory below `template/`.

Consumer-facing validator implementations are canonical only under `template/.github/scripts/`. Source-maintainer CI and regression tests may invoke or import those implementations directly from `template/`, but must not maintain alternate implementation copies at the branch root. Change a downstream validator at its canonical `template/` path, then run both source distribution validation and copied-Skill validation.

Keep `template/` closed and independently usable after copying. Reject undeclared copied files, missing declared files, prohibited symbolic links or Git links, path traversal or `.git` path components, maintainer-only leakage, automatic content transformation, alternate root authorities for distributed validators, and runtime or validation dependence on the source checkout.

Do not pre-enroll the copyable Skill in the shared policy toolchain merely because the source repository consumes it. Source-maintainer `.agent-policy.yml`, `.agent-policy.lock`, `.agent-policy/` state, `policy/` inputs, and `check-agent-policy` workflow authority remain outside `template/`. The distributed `AGENTS.md` is a Skill artifact-development contract, not an inherited projection of source-maintainer policy. A concrete Skill repository may adopt shared policy explicitly after copying as a separate repository-maintenance decision.
