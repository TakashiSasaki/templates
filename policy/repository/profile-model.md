---
id: skill-source.preserve-profile-model
severity: mandatory
overridable: false
order: 1020
---
# Preserve the profile-aware Skill scaffold

The distribution is one profile-aware scaffold, not one directory per profile.

`template-scaffold` is reserved for the uncustomized template. `instruction-only` is the sole exclusive profile. `knowledge-augmented`, `asset-driven`, `script-assisted`, `packaged-cli`, `mcp-enabled`, `browser-interface`, and `headless-service` are selectively composable, and a combination retains the union of its required contracts.

Do not impose a runtime, CLI, MCP, browser, service, or deployment layer on a Skill that does not need it.

Changes to profile semantics must keep the applicable template contracts, validators, positive and negative fixtures, combined fixtures, consumer documentation, distribution manifest, and publication material synchronized.
