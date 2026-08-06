# Template source and distribution boundary

## Decision

The `webapp` branch is the development source for a reusable Web-application repository template. The branch root is not itself the downstream template distribution.

The branch owns three distinct artifacts:

1. **Template source artifact** — the complete `webapp` branch checkout used by template maintainers. It contains the copyable template, maintainer-only tests and fixtures, publication integration, source-level audits, and distribution validation.
2. **Template distribution artifact** — the contents of the future `template/` directory, copied without content transformation to the root of a newly created product repository.
3. **Product repository artifact** — a repository created from the distribution after product-specific contracts, implementation, evidence, commands, CI, release results, and deployment configuration are supplied.

These artifact identities are not interchangeable. Template-maintainer success does not prove that the downstream distribution is closed, and a product repository must not inherit source-maintainer concerns merely because they are present in the same branch history.

## Required invariant

Let `S` be the complete source artifact, `D` the template distribution, and `M` the maintainer-only source content. The target structure satisfies:

```text
S = D union M
D intersection M = empty
```

The set notation describes ownership rather than Git object identity. Source documentation may describe both sets, but every distributed path has one downstream purpose and no distributed file may require a maintainer-only sibling.

## Copy contract

The supported direct-copy operation is:

```sh
cp -a template/. /path/to/new-product-repository/
```

The copied bytes and relative paths are authoritative. An export tool may package or attest the same tree, but it must not rewrite file contents, rename paths, substitute placeholders, or silently omit files from `template/`.

The distribution must therefore satisfy all of the following:

- `template/` is a closed repository root;
- no file below `template/` resolves a required relative reference outside `template/`;
- the initial contracts remain in explicit template mode;
- the copied validators, schemas, migrations, dependency lock, tests, documentation, and CI instructions work from the copied repository root;
- template-source publication catalogs, source audits, clean-room fixture producers, review-history fixtures, and source-only workflows are absent;
- a generated repository can replace example declarations, enter product mode, and retain only product-relevant validation;
- the source artifact validates the distribution as a separate input rather than treating a copy of the complete branch as the generated repository.

## Target layout

The intended source layout is:

```text
/
├── .github/workflows/          # source-maintainer CI
├── README.md                   # source-maintainer overview
├── distribution-manifest.json # closed distribution definition
├── docs/                       # source architecture and publication interface
├── template/                   # directly copyable downstream repository root
└── maintainer/                 # source-only tests, fixtures, audits, and tools
```

The future `template/` tree contains the reusable contract set and downstream validation path:

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

The exact distribution inventory will be closed by `distribution-manifest.json`. A source-level validator will reject missing entries, undeclared entries, unsafe paths, symbolic links, Git administration paths, destination collisions, and maintainer-only residue.

## Current-tree classification

`docs/architecture/distribution-classification.json` classifies every current top-level entry as one of:

- `distribution`: the complete entry is intended to move under `template/`;
- `split`: the entry contains both downstream and source-maintainer material and must be divided during migration;
- `maintainer`: the complete entry remains outside the distribution.

The classification is transitional. It is not the final distribution manifest. Its purpose is to prevent an existing or newly added top-level entry from escaping an ownership decision during the structural migration.

The principal split points are:

- `.github`: source CI remains at the branch root; downstream contract validation moves below `template/`;
- `README.md`: the branch-root source overview and downstream repository overview become separate files;
- `docs`: downstream contract, migration, evidence, and adoption guidance is separated from source completion audits and publication integration;
- `scripts`: reusable validators are separated from publication and distribution tooling;
- `tests`: reusable validator regressions are separated from source clean-room generation, producer fixtures, publication tests, and source-only review regressions.

## Conformance strategy

After physical separation, source CI must validate two independent roots:

1. the complete source checkout, including maintainer-only validation; and
2. a clean copy or deterministic export of `template/`, executed as a repository root without access to source siblings.

Clean-room product tests must start from the distribution artifact. Copying the branch root and skipping maintainer-only tests in product mode is no longer sufficient evidence of a clean downstream boundary.

## Publication boundary

`docs/publication-catalog.json` remains owned by the template source artifact because it is an interface to the unrelated `site` branch. It may publish explanatory downstream documents and machine-readable assets from `template/`, but it is not copied into generated product repositories.

The `site` branch must continue to lock a reviewed full commit SHA. It will be updated only after the `webapp` source and distribution migration is complete. GitHub Pages deployment remains suspended during that interval.

## Completion criteria

The migration is complete only when:

- the branch root is unambiguously a template-development source tree;
- `template/` can be copied directly to an empty repository root;
- every copied reference and validator resolves within the copied tree;
- no maintainer-only artifact is present in the copied tree;
- source CI validates both source and distribution independently;
- clean-room product conformance begins from the distribution;
- publication paths are updated without broadening the public allowlist;
- the final reviewed `webapp` merge commit is integrated into `site` by full SHA; and
- Pages deployment is restored only by a separate reviewed `site` change.
