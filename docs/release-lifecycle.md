# Toolchain release and full-SHA lifecycle

The mutable `policy` branch is the development source. It is not an executable release reference. The stable executable revision is recorded in `release/toolchain.json` and must be a full lowercase Git commit SHA from the `policy` history.

## Release state

`release/toolchain.json` is the branch-local source of truth for the stable channel. It records:

- the executable repository and full commit SHA;
- the highest agent-policy configuration schema version supported by that stable executable;
- the adoption-state schema version;
- the bootstrap-manifest schema version;
- the generated lock format version;
- the exact dependency lock used to execute the pinned release probe.

The descriptor is validated by `schemas/toolchain-release.schema.json`. It cannot contain `policy`, `main`, a tag, a short SHA, `LOCAL-DEVELOPMENT`, or another mutable reference. Contract-version fields accept earlier positive versions because they describe the pinned stable executable, not necessarily the candidate checkout's current contracts.

A single-version schema can declare `schema_version` with `const`. A backward-compatible multi-version schema can declare the supported versions with `enum`. The release verifier interprets the highest positive integer in that declaration as the contract version recorded in `release/toolchain.json`. A verifier must explicitly understand that contract version before it can promote it; future schema versions are rejected until the verifier is extended.

The integrated bootstrap manifest must contain exactly the same `toolchain` object as the stable release descriptor. Product configuration, adoption state, generated lock files, and rendered consumer workflows all carry that same repository and revision when they are created for the stable release.

`release/verifier-requirements.lock` is independent of `requirements-ci.lock`. It records the complete exact dependency graph needed to import and exercise the stable revision. Candidate development may change its own CI dependencies without deleting dependencies still required by the previous stable revision.

## Candidate and promotion commits

A commit cannot contain its own SHA. Stable release movement therefore uses two distinct states:

1. A candidate commit contains the intended toolchain code, schemas, templates, dependency locks, tests, and documentation. Its CI must pass before promotion.
2. A later promotion change updates `release/toolchain.json` and `skills/bootstrap-agent-policy/bootstrap-manifest.yml` to the candidate commit SHA. If the candidate requires a different probe environment, the same promotion change updates `release/verifier-requirements.lock` to a fully resolved exact graph for that candidate.

The promotion commit is not the released executable revision. The candidate is a strict ancestor of the promotion state. This avoids recursive self-reference while preserving an auditable relationship between reviewed code and its distributed pin.

A rollback uses the same mechanism and points both pins to an earlier reviewed `policy` ancestor. It must also restore a verifier dependency graph compatible with that revision. Do not force-move a tag or replace the pin with a branch name.

## Verification

`python scripts/verify-release-state.py` checks the repository-local contracts. Policy CI additionally supplies the fetched pull-request head or current pushed-ref history:

```bash
python scripts/verify-release-state.py \
  --git-ref refs/remotes/origin/policy-source
```

The verifier extracts the tree named by the stable revision. It then creates a temporary virtual environment, installs only the exact packages in `release/verifier-requirements.lock` with dependency resolution disabled, runs `pip check`, and executes the pinned tree with that environment. The candidate checkout's site-packages are not visible to the pinned probe.

The pinned environment loads that revision's configuration and adoption schemas and executes that revision's manifest, adoption-state, lock, and consumer-workflow generators. Candidate-side source or dependency changes therefore do not rewrite or invalidate the descriptor for the previous stable executable.

For an agent-policy contract at schema version 2, the pinned probe additionally creates an isolated temporary repository with distinct `coding` and `review` contexts. It validates, renders, and checks both outputs using only the pinned tree. The probe requires the coding output to contain only its coding-local rule, while the review output must contain its review-local rule plus the shared review and security rules. This proves that the promoted full SHA actually implements semantic context separation rather than merely publishing a schema that describes it.

The verifier requires:

- a schema-valid stable release descriptor;
- exact equality between the stable release and bootstrap toolchain pins;
- an exact, duplicate-free stable verifier dependency graph;
- matching toolchain definitions in the pinned configuration and adoption-state schemas;
- pinned schema and generated-lock versions matching the descriptor;
- a recognized configuration schema-version declaration (`const` for a single version or a positive-integer `enum` for multiple versions);
- pinned generated configuration, adoption state, lock data, and consumer workflow output that use one full SHA;
- schema-v2 context validation/render/check behavior when contract version 2 is published;
- a stable revision that is a strict ancestor of the reviewed source history;
- the executable package, action, schemas, and workflow template at the pinned revision;
- the additional context-rendering modules and template when schema version 2 is published;
- `TakashiSasaki/templates` and branch `policy` identity in the pinned revision.

For a pull request, CI fetches the pull-request head. For a push, it fetches the current `github.ref`, allowing a candidate or promotion branch to validate its own ancestry before review. The workflow contains no fixed fetch of `main`, `site`, or `webapp`.

## Consumer update boundary

Promoting the stable release does not rewrite existing product repositories. A consumer update is a separate reviewed operation that changes its `.agent-policy.yml` revision and then regenerates the lock, agent instructions, generated skills, and consumer workflow from the same new SHA.

During adoption preparation, `.agent-policy/adoption.json` must match the configuration toolchain exactly. Finalization refuses a mismatched adoption state. Consumer repositories must never combine a manifest pin from one release with generated artifacts or a workflow from another release.

`LOCAL-DEVELOPMENT` remains available only for repository-local development and tests. It is not valid in the stable release descriptor or bootstrap manifest.
