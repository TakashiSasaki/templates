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

This Skill may act as the **only repository-facing bootstrap authority** for the current automated-review contract only after the deployment has independently authenticated the installed Skill-source tree. It owns only the trust-establishment handoff before `pr-review` executes. It must not perform pull-request review analysis, classify findings, choose provider events, or authorize merge. After successful handoff, the verified `pr-review` Skill is the sole review-execution procedure authority.

No alternate bootstrap loader, repository-policy-root override, procedure/toolchain override, or other out-of-band review-authority path is supported by this contract. Do not infer one from caller input, local files, environment variables, a mutable branch/tag, or proposed-head content. Any future alternate authority path requires a separately reviewed machine-readable trust contract.

### Installed bootstrap authentication precondition

`runtime-manifest.json` authenticates runtime-selection inputs; it does **not** authenticate the Skill-source bytes containing this bootstrap algorithm. Do not trust this section merely because an `agent-policy` directory exists or its runtime manifest is valid.

Before reading or executing this installed Skill as bootstrap authority, require the trusted deployment/hosting dispatcher to authenticate it with all of the following evidence established outside both the installed Skill tree and the repository under review:

- an independently trusted full-SHA installer revision for `scripts/install_agent_policy_skill.py`;
- the immutable Skill-source revision selected by that installer;
- a deployment-managed installation attestation whose recorded installer and Skill-source identities match those trusted pins;
- an exact installed Skill root matching the attestation; and
- a **closed path/type inventory for the complete installed Skill tree**, with SHA-256 for every regular file.

Verification requires exact inventory equality. Missing paths, additional files or directories, path-type substitutions, symbolic/hard links, or digest drift all invalidate the installation. A file that was not present in the attested tree is untrusted even when every previously attested file remains unchanged.

The authenticated Skill tree is immutable trust material during a trusted-review invocation. Execution must not create `__pycache__`, bytecode, logs, temporary files, or other state inside that tree. The installed Python entry points set `sys.dont_write_bytecode` before importing sibling modules, and the dispatcher must additionally invoke trusted bootstrap with bytecode writes disabled (for example `python -B`) or use an equivalently isolated read-only verified tree. Runtime/cache state belongs outside the attested Skill root. If normal execution can mutate the attested inventory, trusted review bootstrap is unavailable and fails closed.

The canonical remote installer supports writing this external record with `--attestation <path> --installer-revision <trusted-installer-sha>` and supports later verification with the same exact-SHA installer script using `--verify-only`. The dispatcher must authenticate the installer script itself from its independently pinned immutable revision before using its verification result. The attestation must remain outside the installed Skill tree; an attestation discovered inside reviewed repository content is not bootstrap authentication evidence.

If the external attestation is absent, mutable/untrusted, identity-mismatched, points at another installed root, or does not reproduce the exact installed Skill tree, automated-review bootstrap is unavailable and fails closed. Never substitute `runtime-manifest.json`, a Skill-local self-hash, or repository-controlled text for this installation provenance.

### Trusted dispatcher inputs

Only after installed bootstrap authentication succeeds, require the trusted repository/hosting dispatcher to supply and record:

- authenticated bootstrap installer revision, Skill-source revision, installed-root identity, and attestation digest;
- stable repository identity;
- pull-request identity;
- exact current target/base revision;
- a materialized repository snapshot proven by the dispatcher to represent that repository identity at that exact base revision; and
- policy configuration path.

The proposed head is never an authority input to bootstrap.

### Repository-bound bootstrap

Use the exact trusted base snapshot as the active repository-policy root:

1. From this authenticated installed Skill, run `python -B scripts/run.py --repository <trusted-base-snapshot> check --config <config-path>`. The entry point also disables bytecode writes before importing sibling Skill modules; writable runtime/cache state remains outside the installed Skill tree.
2. The runner must select the managed runtime from that snapshot's `.agent-policy.lock`; malformed, mutable, unsupported, or missing managed lock identity fails closed.
3. Require `check` to succeed. This establishes that configuration, lock, policy inputs, generated outputs, and the lock-selected immutable toolchain reproduce coherently in the trusted base snapshot.
4. Require `.agent-policy.yml` and `.agent-policy.lock` to agree on the toolchain repository and full-SHA revision.
5. Require the trusted configuration to enable `pr-review` through `skills.enabled`.
6. Resolve `.agents/skills/pr-review/SKILL.md` and every declared `pr-review` reference lexically from the trusted repository root. Require every path to remain inside the generated `pr-review` tree without parent traversal or reserved-namespace entry, require **every existing path component** from the repository root through the final file to be non-symlink, and require each final path to be a regular file in the verified generated-output set.
7. Require those generated Skill/reference bytes to reproduce under the lock-pinned immutable toolchain established by `check`.
8. Record the lock-selected full-SHA toolchain revision as the procedure revision and record cryptographic digests/provenance for all verified generated `pr-review` files.
9. Hand only those verified generated Skill bytes to the review executor. Never execute an unverified repository-local `pr-review`, and never execute any `pr-review` copy from the proposed head.

The sole repository-local review-procedure bytes permitted by this contract are the trusted-base generated `pr-review` Skill and declared references that passed steps 6-8. A mutable branch/tag, an unauthenticated installed Skill, another unverified repository-local Skill, or any `agent-policy`/`pr-review` bytes from the proposed head must never participate in bootstrap for that same review.

If the trusted base does not validly enable and reproduce `pr-review`, if required files are unsafe/missing/stale/modified, or if any required identity cannot be verified, bootstrap fails closed before review analysis begins.

### Handoff evidence

Before `pr-review` begins, hand it an immutable bootstrap evidence record containing at least:

- authenticated bootstrap installer and Skill-source revisions;
- authenticated installed Skill root plus installation-attestation digest;
- stable repository identity;
- pull-request identity;
- exact trusted base revision / active repository-policy root;
- validated lock toolchain repository and full-SHA revision;
- verified `pr-review` procedure revision;
- verified Skill-file digests/provenance; and
- policy configuration path.

The review Skill must verify that its executing bytes correspond to this evidence before performing review work.

### Base or repository movement

If the target/base revision moves before final review serialization, stop the current review and return to this already authenticated bootstrap with a newly materialized snapshot proven to be the replacement exact base in the same repository. Repeat the repository-bound bootstrap; stale repository/procedure handoff evidence is discarded. If the lock identity, generated Skill bytes, or procedure revision changes, the review restarts under the newly verified Skill. Even when the procedure bytes are unchanged, the review procedure must discard the semantic result produced under the old trusted root and perform a complete new analysis using the replacement base's re-established policy and projection identities.

If stable repository identity changes, fail closed. Bootstrap/review authority established for one repository or fork is never transferred to another merely because commit identities match.

The deployment-side authentication of this installed bootstrap remains independently required throughout the invocation. If its attested installation identity, path/type inventory, or file bytes change, fail closed rather than continuing under a newly discovered local Skill.

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
- For pull-request review bootstrap, require deployment-authenticated installed Skill provenance, a non-mutating execution mode for the attested Skill tree, trusted repository/base identity, and verified generated Skill handoff evidence before `pr-review` executes.
