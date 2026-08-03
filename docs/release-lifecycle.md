# Toolchain release and full-SHA lifecycle

The mutable `policy` branch is the development source. It is not an executable release reference. The stable executable revision is recorded in `release/toolchain.json` and must be a full lowercase Git commit SHA from the `policy` history.

## Release state

`release/toolchain.json` is the branch-local source of truth for the stable channel. It records:

- the executable repository and full commit SHA;
- the agent-policy configuration schema version;
- the adoption-state schema version;
- the bootstrap-manifest schema version;
- the generated lock format version;
- the dependency lock used to execute the pinned release probe.

The descriptor is validated by `schemas/toolchain-release.schema.json`. It cannot contain `policy`, `main`, a tag, a short SHA, `LOCAL-DEVELOPMENT`, or another mutable reference. Contract-version fields accept earlier positive versions because they describe the pinned stable executable, not necessarily the candidate checkout's current contracts.

The integrated bootstrap manifest must contain exactly the same `toolchain` object as the stable release descriptor. Product configuration, adoption state, generated lock files, and rendered consumer workflows all carry that same repository and revision when they are created for the stable release.

`release/verifier-requirements.lock` is independent of `requirements-ci.lock`. It records the complete arbitrary-exact (`===`) dependency graph needed to import and exercise the stable revision. Candidate development may change its own CI dependencies without deleting dependencies still required by the previous stable revision. The verifier lock fixes exact distribution version strings but does not record artifact hashes or source URLs.

## Candidate and promotion commits

A commit cannot contain its own SHA. Stable release movement therefore uses two distinct states:

1. A candidate commit contains the intended toolchain code, schemas, templates, dependency locks, tests, and documentation. Its CI must pass before promotion.
2. A later promotion change updates `release/toolchain.json` and `skills/bootstrap-agent-policy/bootstrap-manifest.yml` to the candidate commit SHA. If the candidate requires a different probe environment, the same promotion change updates `release/verifier-requirements.lock` to a fully resolved arbitrary-exact graph for that candidate.

The promotion commit is not the released executable revision. The candidate is a strict ancestor of the promotion state. This avoids recursive self-reference while preserving an auditable relationship between reviewed code and its distributed pin.

A rollback uses the same mechanism and points both pins to an earlier reviewed `policy` ancestor. It must also restore a verifier dependency graph compatible with that revision. Do not force-move a tag or replace the pin with a branch name.

Changing only the verifier installation boundary without changing the stable executable revision is a candidate-toolchain maintenance change, not a promotion. Changing the packages needed by a new stable executable belongs to the later promotion change so that the release descriptor, bootstrap pin, and compatible probe graph remain one reviewed state.

## Verification

`python scripts/verify-release-state.py` checks the repository-local contracts. Policy CI additionally supplies the fetched pull-request head or current pushed-ref history:

```bash
python scripts/verify-release-state.py \
  --git-ref refs/remotes/origin/policy-source
```

The caller first neutralizes inherited Python and pip inputs. The verifier extracts the tree named by the stable revision, creates a fresh temporary virtual environment, validates the duplicate-free arbitrary-exact lock, installs only those packages with `pip --isolated --no-deps --only-binary=:all:`, runs `pip check`, and executes the pinned tree with that environment. The candidate checkout's site-packages are not visible to the pinned probe.

The pinned environment loads that revision's configuration and adoption schemas and executes that revision's manifest, adoption-state, lock, and consumer-workflow generators. Candidate-side source or dependency changes therefore do not rewrite or invalidate the descriptor for the previous stable executable.

The verifier requires:

- a schema-valid stable release descriptor;
- exact equality between the stable release and bootstrap toolchain pins;
- an arbitrary-exact, duplicate-free stable verifier dependency graph;
- installation isolated from unlisted pip environment inputs and dependency resolution;
- a valid installed dependency graph before pinned-tree execution;
- matching toolchain definitions in the pinned configuration and adoption-state schemas;
- pinned schema and generated-lock versions matching the descriptor;
- pinned generated configuration, adoption state, lock data, and consumer workflow output that use one full SHA;
- a stable revision that is a strict ancestor of the reviewed source history;
- the executable package, action, schemas, and workflow template at the pinned revision;
- `TakashiSasaki/templates` and branch `policy` identity in the pinned revision.

For a pull request, CI fetches the pull-request head. For a push, it fetches the current `github.ref`, allowing a candidate or promotion branch to validate its own ancestry before review. The workflow contains no fixed fetch of `main`, `site`, or `webapp`.

## Consumer update boundary

Promoting the stable release does not rewrite existing product repositories. A consumer update is a separate reviewed operation that changes its `.agent-policy.yml` revision and then regenerates the lock, agent instructions, generated skills, and consumer workflow from the same new SHA.

During adoption preparation, `.agent-policy/adoption.json` must match the configuration toolchain exactly. Finalization refuses a mismatched adoption state. Consumer repositories must never combine a manifest pin from one release with generated artifacts or a workflow from another release.

`LOCAL-DEVELOPMENT` remains available only for repository-local development and tests. It is not valid in the stable release descriptor or bootstrap manifest.
