# Trusted `pr-review` bootstrap

This reference belongs to the immutable `agent-policy` Skill runtime. It establishes which `pr-review` Skill bytes may execute; it is not a pull-request review procedure and must not perform review analysis, classify findings, choose adapter events, or authorize merge.

Use this bootstrap only from an installed/trusted `agent-policy` Skill whose own runtime identity is pinned by its immutable `runtime-manifest.json` or by another independently authorized immutable bootstrap deployment. Never run a bootstrap copy discovered from the pull-request head under review.

## Inputs from the trusted dispatcher

Before repository policy or review Skill bytes are consulted, the trusted dispatcher supplies and records:

- stable repository identity from the repository/hosting system;
- pull-request identity;
- exact current target/base revision;
- a materialized repository snapshot proven by the dispatcher to be that exact base revision;
- policy configuration path;
- any requested immutable out-of-band repository-policy revision; and
- any requested immutable out-of-band procedure/toolchain revision.

The proposed head is never an authority input to this bootstrap.

## Prior-anchor authorization

The exact base snapshot is the prior repository trust anchor. Evaluate authorization for every requested policy-root or procedure/toolchain override against that base snapshot before consulting the candidate override. The candidate override and proposed head must not authorize themselves.

If the base repository contract does not explicitly authorize the requested override mechanism and immutable identity, fail closed. A policy-root override that is authorized becomes the active trusted repository-policy snapshot only after this check succeeds.

## Repository-bound procedure path

When no separately authorized procedure/toolchain override is supplied:

1. Materialize the active trusted repository-policy snapshot independently of the proposed head.
2. From this installed immutable `agent-policy` Skill, run `python scripts/run.py --repository <trusted-snapshot> check --config <config-path>`.
3. The runner must select the managed runtime from the snapshot's `.agent-policy.lock`; malformed, mutable, or unsupported lock identity fails closed.
4. Require `check` to succeed. Success establishes that the lock/configuration/toolchain selection is coherent and that generated outputs in the trusted snapshot reproduce under the lock-selected immutable toolchain.
5. Require the configuration-selected generated Skill files `.agents/skills/pr-review/SKILL.md` and its declared references to exist as regular non-symlink files under the trusted snapshot and to be present in the verified generated-output set. Their existence after successful check is the repository-bound evidence that `pr-review` was enabled and generated from the lock-pinned toolchain.
6. Record the lock-selected full-SHA toolchain revision as the procedure revision and record cryptographic digests of the verified generated `pr-review` files.
7. Hand only those verified generated Skill bytes to the review executor. Do not execute a repository-local or generated `pr-review` copy from the proposed head.

If any required generated `pr-review` file is missing, unsafe, stale, modified, outside the verified output set, or cannot be reproduced by `check`, bootstrap fails closed.

## Authorized out-of-band procedure path

A separately authorized immutable procedure/toolchain override may bypass repository `skills.enabled`, but it does not replace the active repository lock as the authority for semantic/adapter projection generation or validation.

The trusted dispatcher must materialize or retrieve `pr-review` directly from the exact authorized immutable toolchain revision and verify that provenance independently of the proposed head. Record the procedure revision and Skill-file digests. Do not substitute a mutable branch, tag, locally discovered Skill, or bytes from the candidate head.

The active trusted repository-policy snapshot still undergoes the repository-policy/configuration/lock checks required for semantic and adapter projection use.

## Handoff evidence

Before `pr-review` begins, hand it an immutable bootstrap evidence record containing at least:

- stable repository identity;
- pull-request identity;
- prior base authorization anchor;
- active trusted repository-policy revision;
- validated lock toolchain repository and full-SHA revision;
- verified `pr-review` procedure revision;
- verified Skill-file digests/provenance;
- any active policy/procedure override identities and their base authorization evidence; and
- policy configuration path.

`pr-review` must verify that its executing bytes correspond to this evidence before performing review work.

## Base movement

If the target/base revision moves at any point before final review serialization, return control to this bootstrap. Reauthorize every active override against the replacement exact base snapshot. Re-run the applicable trusted-snapshot checks. If authorization, active policy root, lock identity, procedure revision, or verified Skill bytes change, stale bootstrap evidence is discarded. A changed procedure revision requires a full restart under the newly verified Skill.

Bootstrap is complete only after the handoff evidence is internally consistent and no authority decision depends on proposed-head content.