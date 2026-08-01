# Toolchain release and full-SHA lifecycle

The mutable `policy` branch is the development source. It is not an executable release reference. The stable executable revision is recorded in `release/toolchain.json` and must be a full lowercase Git commit SHA from the `policy` history.

## Release state

`release/toolchain.json` is the branch-local source of truth for the stable channel. It records:

- the executable repository and full commit SHA;
- the agent-policy configuration schema version;
- the adoption-state schema version;
- the bootstrap-manifest schema version;
- the generated lock format version.

The descriptor is validated by `schemas/toolchain-release.schema.json`. It cannot contain `policy`, `main`, a tag, a short SHA, `LOCAL-DEVELOPMENT`, or another mutable reference.

The integrated bootstrap manifest must contain exactly the same `toolchain` object as the stable release descriptor. Product configuration, adoption state, generated lock files, and rendered consumer workflows all carry that same repository and revision when they are created for the stable release.

## Candidate and promotion commits

A commit cannot contain its own SHA. Stable release movement therefore uses two distinct states:

1. A candidate commit contains the intended toolchain code, schemas, templates, dependency locks, tests, and documentation. Its CI must pass before promotion.
2. A later promotion change updates `release/toolchain.json` and `skills/bootstrap-agent-policy/bootstrap-manifest.yml` to the candidate commit SHA.

The promotion commit is not the released executable revision. The candidate is a strict ancestor of the promotion state. This avoids recursive self-reference while preserving an auditable relationship between reviewed code and its distributed pin.

A rollback uses the same mechanism and points both files to an earlier reviewed `policy` ancestor. Do not force-move a tag or replace the pin with a branch name.

## Verification

`python scripts/verify-release-state.py` checks the repository-local contracts. Policy CI additionally supplies the fetched PR-head or `policy` source history:

```bash
python scripts/verify-release-state.py \
  --git-ref refs/remotes/origin/policy-source
```

The verifier requires:

- a schema-valid stable release descriptor;
- exact equality between the stable release and bootstrap toolchain pins;
- matching toolchain definitions in the configuration and adoption-state schemas;
- matching declared schema and lock versions;
- generated configuration, adoption state, lock data, and consumer workflow output that use one full SHA;
- a stable revision that is a strict ancestor of the reviewed source history;
- the executable package, action, schemas, and workflow template at the pinned revision;
- `TakashiSasaki/templates` and branch `policy` identity in the pinned revision.

CI fetches only the current pull-request head history or the `policy` history for this check. It does not fetch `main`, `site`, or `webapp`.

## Consumer update boundary

Promoting the stable release does not rewrite existing product repositories. A consumer update is a separate reviewed operation that changes its `.agent-policy.yml` revision and then regenerates the lock, agent instructions, generated skills, and consumer workflow from the same new SHA.

During adoption preparation, `.agent-policy/adoption.json` must match the configuration toolchain exactly. Finalization refuses a mismatched adoption state. Consumer repositories must never combine a manifest pin from one release with generated artifacts or a workflow from another release.

`LOCAL-DEVELOPMENT` remains available only for repository-local development and tests. It is not valid in the stable release descriptor or bootstrap manifest.
