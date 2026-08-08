---
id: policy-repo.require-architecture-decisions
severity: mandatory
overridable: false
order: 1020
---
# Require architecture decisions for trust-contract changes

Changes to the policy configuration schema, rule merge or override semantics, lock-file format, or bootstrap trust model require an architecture decision record before the dependent implementation is treated as complete. Keep the decision, implementation, tests, and maintained documentation synchronized.
