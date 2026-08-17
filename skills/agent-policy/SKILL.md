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
5. If migration discovery finds zero or multiple supported primary instruction files, select one explicitly with `--primary-instructions` before applying.
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
- A valid runtime identity is reused from the persistent cache without network access.
- The first build for an identity installs the exact runtime lock with dependency resolution disabled, installs the pinned project with dependencies disabled, runs `pip check`, and verifies the installed distribution set.
- Runtime construction is staged and switched atomically; an invalid existing cache entry is not trusted.
- `AGENT_POLICY_RUNTIME_CACHE` may override the cache root for controlled environments and tests.

## Safety requirements

- Execute only `TakashiSasaki/templates` at a full lowercase 40-character commit SHA.
- Never execute a mutable branch or tag as the toolchain revision.
- Never auto-finalize migration adoption.
- Do not overwrite handwritten instruction files without review of the migration preview.
- Do not commit, push, create branches, or change repository settings unless separately requested.
- Treat `.agent-policy.lock` as authoritative for an already-managed repository; do not silently substitute the skill default when it is malformed.
