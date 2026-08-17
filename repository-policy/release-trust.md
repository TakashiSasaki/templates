---
id: policy-repo.preserve-release-trust-model
severity: mandatory
overridable: false
order: 1030
---
# Preserve the immutable release trust model

Keep `release/toolchain.json` and `skills/agent-policy/runtime-manifest.json` synchronized to the same reviewed full toolchain commit SHA. Require the runtime manifest to bind that stable revision's `requirements-runtime.lock` by SHA-256. Never replace the executable identity with a mutable branch or tag.

Stable movement uses a frozen reviewed candidate followed by a separate promotion change that records the candidate SHA and matching runtime-lock digest. Do not attempt self-referential promotion in which a commit must contain its own SHA. Update verifier dependencies only when the promoted candidate actually requires a different probe environment.
