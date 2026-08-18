---
id: policy-repo.preserve-release-trust-model
severity: mandatory
overridable: false
order: 1030
---
# Preserve the immutable release trust model

Keep `release/toolchain.json` and `skills/agent-policy/runtime-manifest.json` synchronized to the same reviewed full toolchain commit SHA. Require the runtime manifest to bind that stable revision's `requirements-runtime.lock` by SHA-256. Never replace an executable identity with a mutable branch or tag.

Stable runtime movement uses a frozen reviewed candidate followed by a separate promotion change that records the candidate SHA and matching runtime-lock digest. Do not attempt self-referential promotion in which a commit must contain its own SHA. Update verifier dependencies only when the promoted candidate actually requires a different probe environment.

Keep `release/skill-installer.json` synchronized with the separately reviewed full-SHA installer script and the full-SHA `skills/agent-policy` source revision embedded by that installer. Publish remote installation commands only with the descriptor's full installer revision, never with `policy`, a tag, a short SHA, or another mutable reference. Installer publication likewise uses a reviewed candidate followed by a later promotion change so the published command never requires a commit to contain its own SHA.

Treat `release/skill-installer.json` and repository-level documentation that intentionally publishes the remote installer command as the installer-publication surface. The installed `skills/agent-policy/README.md` is a distributed consumer artifact, not an installer-publication authority; it must not embed a specific installer-script revision or skill-source revision because those identities may be superseded by a later promotion. It may describe the immutable-installation contract and direct readers to the release descriptor and current repository-level installation documentation.
