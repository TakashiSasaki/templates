---
id: policy-repo.preserve-release-trust-model
severity: mandatory
overridable: false
order: 1030
---
# Preserve the immutable release trust model

Keep `release/toolchain.json` and `skills/bootstrap-agent-policy/bootstrap-manifest.yml` synchronized to the same reviewed full toolchain commit SHA. Never replace that executable identity with a mutable branch or tag.

Stable movement uses a frozen reviewed candidate followed by a separate promotion change that records the candidate SHA. Do not attempt self-referential promotion in which a commit must contain its own SHA. Update verifier dependencies only when the promoted candidate actually requires a different probe environment.
