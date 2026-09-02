# Changelog

## Unreleased

- Establish the initial repository architecture.
- Add `init`, `validate`, `render`, and `check` commands.
- Add core and security baseline policies.
- Add a generated `validate-agent-policy` skill.
- Add universal regression-prevention policies for change contracts, derived artifacts, destructive actions, and verification evidence.
- Make generated agent instructions identify the pinned shared-policy source, repository-local policy inputs, and generated operational skills.
- Document bootstrap-safe validation with the exact toolchain revision and managed-repository CI operation.
- Preserve frozen acceptance baselines, escalate material semantic ambiguity, separate verification evidence layers, and limit rollback to changes owned by the current operation.
- Add the optional `external-artifact-intake` profile for provenance, validation order, declared intent, exact-byte staging, transport isolation, and minimal dependency closure.
- Add generated `intake-validated-artifact` and `audit-frozen-change` operational skills.
- Document Google AI Studio Build mode operation and add the optional `work-in-google-ai-studio` generated skill.
- Restrict built-in shared policy to application-type-independent agent operations.
- Use `TakashiSasaki/templates` as the executable and generated toolchain repository identity.
- Add a schema-validated stable release descriptor, two-step full-SHA promotion model, and CI synchronization verification across runtime manifest, schemas, locks, adoption state, and consumer workflows.
- Define full-SHA policy-toolkit readiness, audit evidence, and Pages ownership boundaries.
- Add the `github-review-json-v1` configuration-schema-v2 renderer for GitHub-oriented blocking-review JSON output.
- Replace that transitional GitHub result renderer with provider-neutral review semantic projection plus the generated `pr-review` procedure, then remove the zero-consumer legacy renderer/template surface.
- Add the optional `pull-request` profile for target-branch freshness and review-thread closure before merge.
- Document Policy profile selection, composition, and the complete branch-owned profile catalog for first-time readers.
- Add an exact runtime-only dependency lock, clean consumer-style installation verifier, and Ubuntu/Windows Python 3.11–3.14 runtime-distribution matrix for `agent-policy`.
- Replace the separate `bootstrap-agent-policy` trust seed with one `skills/agent-policy/` entry point for unmanaged adoption and managed operation, backed by a persistent full-SHA runtime cache.
- Publish a full-SHA one-line remote installer for the single `agent-policy` skill, with a separately schema-validated installer/skill-source descriptor and CI history verification.
