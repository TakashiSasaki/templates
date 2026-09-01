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
4. For automated pull-request review, establish trusted `pr-review` provenance through the bootstrap contract below before any review procedure executes.
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

## Trusted `pr-review` bootstrap

This installed immutable `agent-policy` Skill owns only the trust-establishment handoff that occurs before `pr-review` executes. It must not perform pull-request review analysis, classify findings, choose provider events, or authorize merge. After successful handoff, the verified `pr-review` Skill is the sole review-execution procedure authority.

Never run this bootstrap from an `agent-policy` Skill copy discovered in the pull-request head under review. The bootstrap authority must itself be this installed Skill with its immutable `runtime-manifest.json`, or another independently administered immutable bootstrap deployment explicitly authorized by repository contract.

### Trusted dispatcher inputs

Before repository policy or review Skill bytes are consulted, require the trusted repository/hosting dispatcher to supply and record:

- stable repository identity;
- pull-request identity;
- exact current target/base revision;
- a materialized repository snapshot proven by that dispatcher to be the exact base revision;
- policy configuration path;
- any requested immutable out-of-band repository-policy revision; and
- any requested immutable out-of-band procedure/toolchain revision.

The proposed head is never an authority input to bootstrap.

### Prior-anchor authorization

Use the exact base snapshot as the prior repository trust anchor. Evaluate authorization for every requested policy-root or procedure/toolchain override against that base snapshot **before** consulting the candidate override. The candidate override and proposed head must not authorize themselves.

If the base repository contract does not explicitly authorize the requested override mechanism and immutable identity, fail closed. An authorized repository-policy override becomes the active trusted repository-policy snapshot only after that authorization succeeds.

### Repository-bound procedure path

When no separately authorized procedure/toolchain override is supplied:

1. Materialize the active trusted repository-policy snapshot independently of the proposed head.
2. From this installed immutable Skill, run `python scripts/run.py --repository <trusted-snapshot> check --config <config-path>`.
3. The runner must select the managed runtime from that snapshot's `.agent-policy.lock`; malformed, mutable, or unsupported lock identity fails closed.
4. Require `check` to succeed. Success establishes that the managed lock/configuration/toolchain selection is coherent and that generated outputs in the trusted snapshot reproduce under the lock-selected immutable toolchain.
5. Require the generated `.agents/skills/pr-review/SKILL.md` and every declared `pr-review` reference to exist as regular non-symlink files under the trusted snapshot and to belong to the verified generated-output set. Their verified presence is the repository-bound evidence that `pr-review` was enabled and generated from the lock-pinned toolchain.
6. Record the lock-selected full-SHA toolchain revision as the procedure revision and record cryptographic digests of all verified generated `pr-review` files.
7. Hand only those verified generated Skill bytes to the review executor. Never execute a repository-local or generated `pr-review` copy from the proposed head.

If any required generated `pr-review` file is missing, unsafe, stale, modified, outside the verified generated-output set, or cannot be reproduced by `check`, bootstrap fails closed.

### Authorized out-of-band procedure path

A separately authorized immutable procedure/toolchain override may bypass repository `skills.enabled`, but it does not replace the active repository lock as the authority for semantic/adapter projection generation or validation.

The trusted dispatcher must materialize or retrieve `pr-review` directly from the exact authorized immutable toolchain revision and verify that provenance independently of the proposed head. Record the procedure revision and Skill-file digests. Do not substitute a mutable branch, tag, locally discovered Skill, or bytes from the candidate head.

The active trusted repository-policy snapshot still undergoes the repository-policy/configuration/lock verification required for semantic and adapter projection use.

### Handoff evidence

Before `pr-review` begins, hand it an immutable bootstrap evidence record containing at least:

- stable repository identity;
- pull-request identity;
- prior base authorization anchor;
- active trusted repository-policy revision;
- validated lock toolchain repository and full-SHA revision;
- verified `pr-review` procedure revision;
- verified Skill-file digests/provenance;
- every active policy/procedure override identity and its base authorization evidence; and
- policy configuration path.

The review Skill must verify that its executing bytes correspond to this evidence before performing review work.

### Base movement

If the target/base revision moves at any point before final review serialization, return control to this bootstrap. Reauthorize **every** active override against the replacement exact base snapshot, then repeat the applicable trusted-snapshot checks. If authorization, active policy root, lock identity, procedure revision, or verified Skill bytes change, discard stale bootstrap evidence. A changed procedure revision or Skill digest requires a full restart under the newly verified Skill.

Bootstrap is complete only after the handoff evidence is internally consistent and no authority decision depends on proposed-head content.

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
- For pull-request review bootstrap, require trusted repository/base identity and verified Skill handoff evidence before `pr-review` executes.