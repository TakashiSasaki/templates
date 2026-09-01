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
4. For automated pull-request review bootstrap, use the trust-establishment contract in `references/pr-review-bootstrap.md` from this installed immutable Skill before any `pr-review` procedure executes.
5. Do not bypass the skill runtime by installing or invoking a mutable `policy` branch.

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

## Automated review bootstrap

`references/pr-review-bootstrap.md` owns only the trust-establishment handoff that occurs before `pr-review` executes. It uses this installed immutable Skill and the existing managed-runtime `run.py`/`check` path to establish lock-selected toolchain provenance and verified generated Skill bytes from a trusted repository snapshot.

That bootstrap is not a second review procedure. It must not inspect the proposed change for findings, classify review evidence, choose provider events, or authorize merge. After successful handoff, the verified `pr-review` Skill is the sole review-execution procedure authority.

Never use an `agent-policy` or `pr-review` Skill copy discovered from the proposed pull-request head to establish the authority used to review that same head.

## Persistent runtime

- The default toolchain full SHA and runtime-lock SHA-256 are recorded in `runtime-manifest.json`.
- Managed repositories prefer the full SHA in `.agent-policy.lock`.
- Runtime identity includes repository, full revision, runtime-lock digest, Python major/minor, and platform.
- A valid runtime identity is reused from the persistent cache without network access or a cache-writability probe.
- Before a cache miss downloads or builds runtime material, the runner verifies that the selected cache root supports directory creation, file writes, cleanup, and same-filesystem atomic rename.
- The first build for an identity installs the exact runtime lock with dependency resolution disabled, installs the pinned project with dependencies disabled, runs `pip check`, and verifies the installed distribution set. Both pip installation steps disable pip's independent download cache.
- Runtime construction is staged and switched atomically; an invalid existing cache entry is not trusted.
- `AGENT_POLICY_RUNTIME_CACHE` may override the cache root for controlled environments and tests. If the platform default cache is unusable, the error names the failing path and tells the consumer to set this variable to a writable directory. No separate pip cache or XDG cache override is required.

## Safety requirements

- Execute only `TakashiSasaki/templates` at a full lowercase 40-character commit SHA.
- Never execute a mutable branch or tag as the toolchain revision.
- Never auto-finalize migration adoption.
- Do not overwrite handwritten instruction files without review of the migration preview.
- Do not commit, push, create branches, or change repository settings unless separately requested.
- Treat `.agent-policy.lock` as authoritative for an already-managed repository; do not silently substitute the skill default when it is malformed.
- For pull-request review bootstrap, require trusted base/repository identity and verified Skill handoff evidence before `pr-review` executes.