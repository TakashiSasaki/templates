# Template source and distribution boundary

## Decision

The `webapp` branch is the development source for a reusable Web-application repository template. The branch root is not itself the downstream template distribution.

The branch owns three distinct artifacts:

1. **Template source artifact** — the complete `webapp` branch checkout used by template maintainers. It contains the copyable template, source-only tests and fixture producers, publication integration, audits, and distribution validation.
2. **Template distribution artifact** — the committed contents of `template/`, copied without content transformation to the root of a newly created product repository.
3. **Product repository artifact** — a repository created from the distribution after product-specific contracts, implementation, evidence, commands, CI, release results, and deployment configuration are supplied.

These artifact identities are not interchangeable. Template-source validation does not by itself prove that the downstream distribution is closed, and a product repository must not inherit source-maintainer concerns merely because they are present in the same branch history.

## Required invariant

Let `S` be the complete source artifact, `D` the template distribution, and `M` the maintainer-only source content. The implemented ownership boundary satisfies:

```text
D is a proper subtree of S
D intersection M = empty
```

The set notation describes ownership rather than Git object identity. Source-owned canonical inputs may have byte-identical projections inside `template/`, but every distributed path has one downstream purpose and no distributed file may require a maintainer-only sibling.

## Copy contract

The supported direct-copy operation is:

```sh
cp -a template/. /path/to/new-product-repository/
```

The copied bytes and relative paths are authoritative. A packaging or attestation tool may transport the same tree, but it must not rewrite file contents, rename paths, substitute placeholders, or silently omit tracked files from `template/`.

The distribution satisfies the following requirements:

- `template/` is a closed repository root;
- no required relative reference below `template/` escapes that tree;
- the initial implementation, release-evidence, and release-bundle documents remain in explicit template mode;
- the copied validators, schemas, migrations, dependency lock, tests, documentation, and CI workflow execute from the copied repository root;
- template-source publication catalogs, distribution tooling, source audits, clean-room fixture producers, and review-history regressions are absent;
- a generated repository can replace example declarations, enter product mode, execute release evidence and bundle production, and retain only product-relevant validation; and
- source CI validates the branch root and `template/` as separate roots.

## Implemented source layout

The source layout uses one explicit copy boundary rather than requiring every source-only file to be nested under a directory named `maintainer`:

```text
/
├── .github/workflows/          # source-maintainer CI
├── README.md                   # source-maintainer overview
├── distribution-manifest.json # closed source-to-distribution definition
├── contracts/                  # source-owned canonical contract inputs
├── schemas/                    # source-owned canonical schema inputs
├── scripts/                    # reusable validators plus source-only validators
├── tests/                      # source-maintainer regression and clean-room suites
├── docs/                       # source architecture and publication interface
└── template/                   # directly copyable downstream repository root
```

The physical rule is simple and testable: every path below `template/` is distributed; every source-only path is outside `template/`. A separate `maintainer/` directory would not strengthen the downstream copy boundary and would require widespread path rewrites without changing which bytes are distributed. Source ownership is therefore enforced by the closed manifest and validator instead of by one additional naming layer.

The distribution tree contains:

```text
template/
├── .github/workflows/contract-validation.yml
├── .gitignore
├── README.md
├── TEMPLATE.md
├── contracts/
├── schemas/
├── scripts/
├── tests/
├── docs/
├── requirements-dev.txt
└── requirements-dev.lock
```

`distribution-manifest.json` closes this inventory. `scripts/validate_distribution.py` rejects missing entries, undeclared entries, unsafe paths, symbolic or non-regular tracked files, Git administration paths, destination collisions, maintainer-only residue, top-level inventory drift, and byte differences in mirrored files.

## Source-to-distribution projection

The distribution uses two file classes.

**Mirrored files** are source-owned canonical inputs whose exact bytes are also required downstream. The manifest maps the source path to its distribution destination and the validator compares the bytes. Contracts, schemas, reusable validators, migrations, dependency definitions, and shared guidance use this class.

**Distribution-owned files** exist only below `template/` because their meaning is specific to a generated repository. The downstream `README.md`, downstream contract-validation workflow, and distribution baseline tests use this class.

The projection is committed rather than generated only during CI. This makes the copyable tree directly inspectable and usable at every reviewed commit. The byte-identity validator prevents the committed projection from drifting from its source-owned canonical inputs.

## Current-tree classification

`docs/architecture/distribution-classification.json` classifies every source top-level entry as one of:

- `distribution`: the complete entry is the downstream copy root;
- `split`: the entry has source-owned material that is selectively projected into `template/`; or
- `maintainer`: the complete entry remains outside the distribution.

The classification and `distribution-manifest.json` have different roles. The classification closes ownership of source top-level entries. The manifest closes every tracked file in the downstream distribution and every source-to-distribution mirror.

The principal split points are:

- `.github`: source CI remains at the branch root; downstream contract validation is distribution-owned;
- `README.md`: the branch-root source overview and downstream repository overview are different files;
- `docs`: downstream contract, migration, evidence, and adoption guidance is separated from source audits and publication integration;
- `scripts`: reusable validators are separated from publication and distribution validators;
- `tests`: downstream baseline validation is separated from source clean-room generation, producer fixtures, publication tests, and review regressions.

## Conformance strategy

Source CI validates two independent roots:

1. the complete source checkout, including distribution closure and source-maintainer validation; and
2. `template/`, executed as a repository root without access to source siblings.

The shared generated-repository fixture copies `template/`, not the branch root. Implementation conformance, declarative release-evidence conformance, actual release-evidence production, and release-bundle production therefore begin from the same distribution bytes. Their generated repositories do not contain a nested template tree, distribution manifest, provider publication catalog, source-only validators, audits, or fixture tests.

Assertions after each fixture verify that source and distribution evidence remain in template mode and that no product directory leaks into either tree.

## Publication boundary

`docs/publication-catalog.json` remains owned by the template source artifact because it is an interface to the unrelated `site` branch. It publishes downstream explanatory documents and machine-readable assets from `template/`, while source architecture and audit documents remain sourced outside `template/`. The catalog itself is not copied into generated product repositories.

Stable document IDs and publication destinations are independent of source paths. Moving downstream canonical publication sources below `template/` therefore does not require changing their public identities or the `contracts` and `schemas` publication destinations.

The `site` branch must lock one reviewed full commit SHA. It is updated only after the `webapp` distribution work is complete and its final merge SHA is known. Deployment authority is restored only in a separate reviewed `site` change after integrated build-only validation succeeds.

## Webapp completion criteria

The `webapp` migration is internally complete when:

- the branch root is unambiguously a template-development source tree;
- `template/` can be copied directly to an empty repository root;
- every copied reference and validator resolves within the copied tree;
- no maintainer-only artifact is present in the copied tree;
- the manifest closes every tracked distribution file;
- mirrored files are byte-identical to their source-owned canonical inputs;
- source CI validates source and distribution independently;
- all generated-product stages begin from the distribution;
- publication sources are updated without broadening the public allowlist;
- all tests and validator entry points pass; and
- the final reviewed merge commit is recorded for coordinated `site` integration.

Repository-wide publication completion remains a later `site` responsibility: update the locked `webapp` full SHA, pass the integrated build while deployment is suspended, merge that compatibility change, and restore Pages deployment only through a separate reviewed pull request.
