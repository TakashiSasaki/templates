---
id: webapp-source.preserve-artifact-contract-authority
severity: mandatory
overridable: false
order: 1000
---
# Keep Webapp artifact contracts outside shared policy

The `webapp` branch owns framework-neutral Web-application artifact contracts. `template/contracts/manifest.json`, the registered contract documents and schemas below `template/`, migration history, implementation-evidence contract, release-evidence contract, release-bundle contract, and their canonical validators under `template/scripts/` remain authoritative for the Webapp artifact.

Shared agent policy governs maintainer working behavior only. Do not copy Webapp artifact semantics into repository policy modules, and do not make policy rule IDs, profiles, generated policy artifacts, or the policy toolchain prerequisites for validating or using the Webapp contracts.

Keep policy configuration and generated maintainer instructions outside the copyable Webapp artifact boundary unless a separately reviewed artifact-contract change explicitly establishes such ownership.
