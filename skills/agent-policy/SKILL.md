---
name: agent-policy
description: Adopt or operate a repository with the immutable TakashiSasaki/templates agent-policy toolchain, using a persistent full-SHA runtime cache.
---

# Agent Policy

Use this as the single repository-facing entry point for the `agent-policy` toolkit.

## Choose the operation

1. Resolve the Git repository root before any mutation.
2. If the repository is not yet managed by agent-policy, use `python scripts/bootstrap.py --repository <root>` first.
3. If the repository already contains `.agent-policy.lock`, use `python scripts/run.py --repository <root> <agent-policy arguments>` for normal operations.
4. Do not bypass the skill runtime by installing or invoking a mutable `policy` branch.

## Unmanaged repository onboarding

1. Run `python scripts/bootstrap.py --repository <root>` without `--apply`.
2. Review the reported adoption state, discovered instruction sources, strategy, and primary-instruction selection.
3. For `unmanaged-empty`, the public operation is fresh adoption; the tool may use its hidden initialization primitive internally.
4. For `unmanaged-existing`, preserve handwritten instructions and use staged migration adoption.
5. If no supported instruction files are discovered during migration, create one supported instruction file and re-run bootstrap. If exactly one supported instruction file is discovered, bootstrap selects it automatically. If multiple supported instruction files are discovered, select one explicitly with `--primary-instructions` before applying.
6. Only after reviewing the dry run, rerun with `--apply` when mutation is intended.
7. Fresh adoption may complete directly to managed state and then validate/check.
8. Migration bootstrap may prepare and preview only. It must never finalize migration.
9. Migration finalization requires a separate explicit instruction and must be invoked through `scripts/run.py` against the repository-pinned toolchain.

## Managed repository operation

Use:

```text
python scripts/run.py --repository <root> <agent-policy command and arguments>
```

The runner reads `.agent-policy.lock` when present and requires its toolchain repository and revision to be supported and immutable. A malformed, mutable, or unsupported lock fails closed rather than falling back to the skill default.

## Persistent runtime

- The default toolchain full SHA and runtime-lock SHA-256 are recorded in `runtime-manifest.json`.
- Managed repositories prefer the full SHA in `.agent-policy.lock`.
- Runtime identity includes repository, full revision, runtime-lock digest, Python major/minor, and platform.
- A valid runtime identity is reused from the persistent cache without network access or a cache-writability probe.
- Before a cache miss downloads or builds runtime material, the runner verifies that the selected cache root supports directory creation, file writes, cleanup, and same-filesystem atomic rename.
- The first build for an identity installs the exact runtime lock with dependency resolution disabled, installs the pinned project with dependencies disabled, runs `pip check`, and verifies the installed distribution set. Both pip installation steps disable pip's independent download cache.
- Runtime construction is staged and switched atomically; an invalid existing cache entry is not trusted.
- `AGENT_POLICY_RUNTIME_CACHE` may override the cache root for controlled environments and tests. If the platform default cache is unusable, the error names the failing path and tells the consumer to set this variable to a writable directory. No separate pip cache or XDG cache override is required.

## Trusted `pr-review` bootstrap

This section is the repository-facing bootstrap authority for provider-neutral automated review. Bootstrap establishes provenance and immutable authority only; it must not perform finding analysis or decide the conceptual review conclusion.

1. Authenticate the installed `agent-policy` Skill using the deployment-managed installation attestation outside both the repository under review and the installed Skill tree. The attestation must bind the installer revision, immutable Skill-source revision, closed path/type inventory, and SHA-256 of every regular file.
2. Materialize an independent bootstrap run image from that attested Skill tree, establish the deployment's read-only/immutable boundary, and verify the already-frozen image against the attestation before executing trusted bootstrap logic.
3. Resolve the stable repository identity, pull-request identity, exact current base commit, and exact current base tree through the trusted hosting/repository boundary. The proposed head is never an authority input to bootstrap.
4. Use `scripts/review_base.py` from the verified bootstrap image to materialize the exact-base Git-object-backed snapshot outside the source object repository. Establish the deployment's immutable boundary and verify the already-frozen snapshot against the exact base commit/tree before reading policy authority from it.
5. Select the managed runtime only from that trusted snapshot's `.agent-policy.lock`. Create or obtain the deployment-managed runtime attestation, materialize an independent runtime image, freeze it, and verify it with `scripts/runtime_image.py` before executing managed policy checks.
6. Through that verified frozen runtime, run trusted-snapshot `validate` and `check` against the exact-base snapshot. `check` may use only its disposable writable staging copy; the trusted snapshot itself remains read-only authority.
7. Require the trusted configuration to enable `pr-review`. Require the caller to identify one enabled provider-neutral semantic output whose renderer is exactly `policy-context-md`; do not infer a semantic output from provider-specific names or renderers.
8. Through the same verified frozen runtime, materialize the review authority bundle from the trusted snapshot:

   ```text
   agent-policy --trusted-review-snapshot --repository <trusted-base-snapshot> review-bundle --config <config-path> --semantic-output <semantic-output-path> materialize --destination <external-bundle>
   ```

   The materialized bundle is not yet trusted. Establish the deployment's read-only/immutable boundary over the bundle, then verify it:

   ```text
   agent-policy --trusted-review-snapshot --repository <trusted-base-snapshot> review-bundle --config <config-path> --semantic-output <semantic-output-path> verify --bundle <external-bundle>
   ```

9. The verified bundle must contain the complete lock-authoritative generated `pr-review` Skill tree and the exact lock-authoritative provider-neutral semantic projection reproduced by trusted-base `check`. Missing/extra paths, byte drift, symlinks, hard links, type substitutions, stale lock bytes, or overlap with the trusted-base snapshot fail closed. No provider adapter or provider result serializer belongs to this authority bundle.
10. Record an immutable bootstrap handoff binding the stable repository identity, pull-request identity, exact base commit/tree, authenticated installation identity, frozen bootstrap image identity, frozen trusted-base snapshot identity, frozen runtime identity, verified procedure-bundle identity, and semantic-policy identity. Hand only the verified bundle and those identities to `pr-review`.

No alternate repository-local loader, mutable checkout, persistent runtime cache, proposed-head Skill, provider adapter, or caller-selected procedure revision may replace this path. If the base moves, discard the trusted authority closure and repeat the full bootstrap before any further analysis. Head-only movement does not redefine semantic authority, but the `pr-review` procedure must invalidate and recompute all affected head-bound evidence.

## Safety requirements

- Execute only `TakashiSasaki/templates` at a full lowercase 40-character commit SHA.
- Never execute a mutable branch or tag as the toolchain revision.
- Never auto-finalize migration adoption.
- Do not overwrite handwritten instruction files without review of the migration preview.
- Do not commit, push, create branches, or change repository settings unless separately requested.
- Treat `.agent-policy.lock` as authoritative for an already-managed repository; do not silently substitute the skill default when it is malformed.
