# Toolchain release and full-SHA lifecycle

The mutable `policy` branch is the development source. It is not an executable release reference. The stable executable revision is recorded in `release/toolchain.json` and must be a full lowercase Git commit SHA from the `policy` history.

## Release state

`release/toolchain.json` is the branch-local source of truth for the stable runtime channel. It records:

- the executable repository and full commit SHA;
- the highest agent-policy configuration schema version supported by that stable executable;
- the adoption-state schema version;
- the single-skill runtime-manifest schema version;
- the generated lock format version; and
- the exact dependency lock used to execute the pinned release probe.

The descriptor is validated by `schemas/toolchain-release.schema.json`. It cannot contain `policy`, `main`, a tag, a short SHA, `LOCAL-DEVELOPMENT`, or another mutable reference. Contract-version fields accept earlier positive versions because they describe the pinned stable executable, not necessarily the candidate checkout's current contracts.

A single-version schema can declare `schema_version` with `const`. A backward-compatible multi-version schema can declare the supported versions with `enum`. The release verifier interprets the highest positive integer in that declaration as the contract version recorded in `release/toolchain.json`. A verifier must explicitly understand that contract version before it can promote it; future schema versions are rejected until the verifier is extended.

`skills/agent-policy/runtime-manifest.json` must contain exactly the same `toolchain` object as the stable release descriptor. It additionally records the path and SHA-256 of the stable revision's `requirements-runtime.lock`, plus the stable project identity. `scripts/verify-release-state.py` extracts the stable tree and verifies this digest rather than trusting the promotion checkout's runtime lock implicitly.

Product configuration, adoption state, generated lock files, and rendered consumer workflows carry the same repository and revision when they are created for the stable release.

`release/verifier-requirements.lock` is independent of `requirements-ci.lock`. It records the complete exact dependency graph needed to import and exercise the stable revision. Candidate development may change its own CI dependencies without deleting dependencies still required by the previous stable revision.

`requirements-runtime.lock` is a third, separate dependency contract. It records the exact runtime-only distribution set expected beside the `takashisasaki-agent-policy` project in a consumer-style clean environment; development, test, and build-only distributions and the project distribution itself are excluded. `scripts/smoke_test_runtime_distribution.py` installs that set and the local project separately with dependency resolution disabled, and `scripts/verify_runtime_environment.py` requires the resulting installed set to match the runtime lock plus the project. The runtime-distribution CI matrix verifies this contract on Ubuntu and Windows across Python 3.11 through 3.14.

The single `agent-policy` skill consumes this runtime contract through a persistent cache keyed by stable repository/revision, runtime-lock SHA-256, Python major/minor, and platform. A validated cache entry may be reused without network access. This does not replace `release/verifier-requirements.lock`, whose purpose is to execute the already-pinned stable revision during promotion verification.

## Skill installer publication state

Remote skill distribution is a separate release concern from the stable CLI runtime. `release/skill-installer.json`, validated by `schemas/skill-installer-release.schema.json`, records two immutable identities:

- the **installer script revision** and path used by the public raw GitHub URL; and
- the **skill source revision** and `skills/agent-policy` subtree installed by that script.

The installer script may itself contain the skill-source full SHA, but the publication descriptor is the committed synchronization record. `scripts/verify_skill_installer_release.py` verifies the descriptor against Git history, confirms that the pinned installer embeds exactly the published skill-source SHA, confirms the required skill files exist at that source revision, and requires both revisions to precede the publication state when CI supplies a source ref.

The installer-script revision, skill-source revision, and stable runtime revision may legitimately differ. They represent distribution bootstrap, installed skill bytes, and executed CLI runtime respectively and must not be collapsed into one implicit notion of "current version."

## Candidate and promotion commits

A commit cannot contain its own SHA. Stable runtime movement therefore uses two distinct states:

1. A candidate commit contains the intended toolchain code, schemas, templates, dependency locks, tests, and documentation. Its CI must pass before promotion.
2. A later promotion change updates `release/toolchain.json` and `skills/agent-policy/runtime-manifest.json` to the candidate commit SHA. The runtime manifest also records the SHA-256 of the candidate's `requirements-runtime.lock`. If the candidate requires a different release-probe environment, the same promotion change updates `release/verifier-requirements.lock` to a fully resolved exact graph for that candidate.

The promotion commit is not the released executable revision. The candidate is a strict ancestor of the promotion state. This avoids recursive self-reference while preserving an auditable relationship between reviewed code and its distributed pin.

Remote installer publication uses the same two-step principle independently:

1. an installer candidate is reviewed and merged so its full commit SHA becomes knowable;
2. a later publication change writes that full SHA to `release/skill-installer.json` and to the documented raw GitHub command.

The installer candidate itself separately pins the reviewed skill-source revision. A publication update must therefore verify both levels instead of pointing the one-line command at a mutable branch.

A rollback uses the same mechanisms: stable runtime pins return to an earlier reviewed candidate with the matching runtime-lock digest, while installer publication may independently return to an earlier reviewed installer/skill-source pair. Do not force-move a tag or replace any executable/distribution pin with a branch name.

## Verification

Policy CI verifies both release families:

```bash
python scripts/verify-release-state.py \
  --git-ref refs/remotes/origin/policy-source
python scripts/verify_skill_installer_release.py \
  --git-ref refs/remotes/origin/policy-source
```

The stable-runtime verifier extracts the tree named by the stable revision. It verifies the single-skill runtime manifest against that tree, including the runtime-lock digest, then creates a temporary virtual environment, installs only the exact packages in `release/verifier-requirements.lock` with dependency resolution disabled, runs `pip check`, and executes the pinned tree with that environment. The candidate checkout's site-packages are not visible to the pinned probe.

The pinned environment loads that revision's configuration and adoption schemas and executes that revision's manifest, adoption-state, lock, and consumer-workflow generators. Candidate-side source or dependency changes therefore do not rewrite or invalidate the descriptor for the previous stable executable.

For an agent-policy contract at schema version 2, the pinned probe additionally creates an isolated temporary repository with distinct `coding` and `review` contexts. It validates, renders, and checks both outputs using only the pinned tree. The probe requires the coding output to contain only its coding-local rule, while the review output must contain its review-local rule plus the shared review and security rules. This proves that the promoted full SHA actually implements semantic context separation rather than merely publishing a schema that describes it.

The stable-runtime verifier requires:

- a schema-valid stable release descriptor;
- exact equality between the stable release and single-skill runtime-manifest toolchain pins;
- a runtime-manifest lock digest equal to `requirements-runtime.lock` in the stable revision;
- stable project metadata consistent with the pinned tree;
- an exact, duplicate-free stable verifier dependency graph;
- matching toolchain definitions in the pinned configuration and adoption-state schemas;
- pinned schema and generated-lock versions matching the descriptor;
- a recognized configuration schema-version declaration (`const` for a single version or a positive-integer `enum` for multiple versions);
- pinned generated configuration, adoption state, lock data, and consumer workflow output that use one full SHA;
- schema-v2 context validation/render/check behavior when contract version 2 is published;
- a stable revision that is a strict ancestor of the reviewed source history;
- the executable package, action, runtime lock, schemas, and workflow template at the pinned revision;
- the additional context-rendering modules and template when schema version 2 is published; and
- `TakashiSasaki/templates` and branch `policy` identity in the pinned revision.

The installer-publication verifier requires:

- a schema-valid `release/skill-installer.json`;
- immutable `TakashiSasaki/templates` full SHAs for installer and skill source;
- the published installer path at the installer revision;
- an installer-embedded skill-source SHA equal to the descriptor;
- `SKILL.md`, `runtime-manifest.json`, and `scripts/install.py` under the published skill-source subtree; and
- both pinned revisions as strict ancestors of the reviewed publication state.

For a pull request, CI fetches the pull-request head. For a push, it fetches the current `github.ref`, allowing a candidate or promotion branch to validate its own ancestry before review. The workflow contains no fixed fetch of `main`, `site`, or `webapp`.

## Consumer update boundary

Promoting the stable runtime does not rewrite existing product repositories. A consumer update is a separate reviewed operation that changes its `.agent-policy.yml` revision and then regenerates the lock, agent instructions, generated skills, and consumer workflow from the same new SHA.

Likewise, publishing a new remote installer does not rewrite already installed skills. The one-line command only affects a future installation invocation, and `--replace` remains separately explicit for an existing installation.

The installed `agent-policy` skill follows `.agent-policy.lock` for an already-managed repository. A full-SHA pin that differs from the skill's stable default may reuse an already validated cache entry for that revision; otherwise the skill fetches that revision's runtime lock once, computes its digest, constructs a new cache identity, and verifies the resulting runtime before use. Malformed or mutable managed-repository pins fail closed.

During adoption preparation, `.agent-policy/adoption.json` must match the configuration toolchain exactly. Finalization refuses a mismatched adoption state. Consumer repositories must never combine a manifest pin from one release with generated artifacts or a workflow from another release.

Every consumer configuration and adoption state requires an exact 40-character lowercase commit SHA. When execution starts from a source checkout without an explicit `--toolchain-revision`, the toolchain resolves the exact commit SHA of that checkout's `HEAD`; installed VCS runtimes resolve and verify their immutable PEP 610 provenance instead of using a development sentinel.
