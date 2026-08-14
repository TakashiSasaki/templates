# Template source and distribution boundary

## Decision

The `webapp` branch is the development source for a reusable Web-application repository template. The branch root is not itself the downstream template distribution.

The branch owns three distinct artifacts:

1. **Template source artifact** — the complete `webapp` branch checkout used by template maintainers. It contains the copyable template, source-only tests and fixture producers, publication integration, audits, policy, and distribution validation.
2. **Template distribution artifact** — the committed contents of `template/`, copied without content transformation to the root of a newly created product repository.
3. **Product repository artifact** — a repository created from the distribution after product-specific contracts, implementation, evidence, commands, CI, release results, and deployment configuration are supplied.

These artifact identities are not interchangeable. `template/` is the sole canonical source tree for downstream-owned content. Source-maintainer tooling consumes that canonical tree directly; the source repository does not maintain byte-identical root projections of downstream canonical inputs.

## Required invariant

Let `S` be the complete source artifact, `D` the canonical downstream artifact rooted at `template/`, and `M` the maintainer-only source content outside that tree. The implemented ownership boundary satisfies:

```text
D is a proper subtree of S
D intersection M = empty   (responsibility)
```

The set notation describes responsibility, not Git blob identity. Two independently owned files may happen to contain identical bytes. For example, the source checkout and downstream repository may each need a `.gitignore`. Such coincidence does not create a mirror contract. What is prohibited is a second authoritative source path for the same downstream responsibility.

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
- source CI validates source-maintainer concerns and the canonical downstream tree as separate roots.

## Shared policy adoption boundary

The copy operation does not pre-enroll the product repository in the source repository's shared policy toolchain. Source-maintainer `.agent-policy.yml`, `.agent-policy.lock`, `.agent-policy/` state, generated `AGENTS.md`, repository-local `policy/` inputs, and `check-agent-policy` workflow authority are prohibited from the closed `template/` inventory.

The Web-application artifact contract does not require an agent-instruction entry point merely because the source branch consumes shared policy. After copying, a concrete product repository may explicitly adopt shared repository policy through a reviewed immutable toolchain revision. That adoption is a separate repository-maintenance operation and must preserve the Web-application contracts already established by the distribution and subsequent product customization.

## Implemented source layout

The source layout uses one explicit canonical copy boundary rather than duplicating downstream inputs at the branch root:

```text
/
├── .agent-policy.lock          # deterministic shared-policy lock
├── .agent-policy.yml           # source-maintainer shared-policy configuration
├── .github/workflows/          # source-maintainer CI
├── .gitignore                  # source-checkout ignore policy
├── AGENTS.md                   # generated source-maintainer agent instructions
├── README.md                   # source-maintainer overview
├── distribution-manifest.json  # closed canonical distribution inventory
├── policy/                     # repository-local maintainer policy
├── docs/                       # maintainer architecture, audits, publication interface
├── scripts/                    # source-only distribution/publication/translation tooling and import bridge
├── tests/                      # source-maintainer regression and clean-room suites
├── translations/               # non-authoritative reader/guided locale overlays
└── template/                   # sole canonical downstream repository source tree
```

Consumer contracts, schemas, reusable validators, dependency files, migrations, operational guidance, and downstream tests are authored only below `template/`. Source-maintainer tests and workflows reference those canonical paths directly. The root `scripts` package may expose an import bridge into `template/scripts` and may contain source-only validators such as translation metadata validation, but it does not contain duplicate downstream validator implementations.

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

`distribution-manifest.json` closes this inventory with schema version 2 and an explicit `distribution_files` list. `scripts/validate_distribution.py` rejects missing entries, undeclared entries, unsafe paths, symbolic or non-regular files, Git administration paths, forbidden maintainer residue, top-level inventory drift, and any mismatch between the declared canonical inventory and tracked files under `template/`.

## Canonical source and copy model

The previous root-to-`template/` mirror/projection model is retired. There is no source-to-distribution mirror mapping, no byte-parity authority check, and no requirement to edit equivalent files in two locations.

Downstream content has one authoring location:

```text
template/ canonical downstream source
        │
        ├── consumed directly by source-maintainer validation
        └── copied byte-for-byte to a new product repository root
```

Source-only tooling may inspect, validate, package, publish, or attest the canonical tree, but it must not synthesize an alternate authoritative copy of downstream inputs. Packaging that archives the exact `template/` bytes is transport, not a second generated distribution.

## Current-tree classification

`docs/architecture/distribution-classification.json` classifies every source top-level entry as one of:

- `distribution`: the complete entry is the downstream canonical copy root;
- `split`: the same conceptual area has separate source-maintainer and downstream responsibilities, with downstream authority only under `template/`; or
- `maintainer`: the complete entry remains outside the distribution.

The classification and `distribution-manifest.json` have different roles. The classification closes ownership of source top-level entries. The manifest closes every tracked file in the canonical downstream tree.

The principal split points are:

- `.github`: source CI remains at the branch root; downstream contract validation is canonical under `template/.github`;
- `.gitignore`: the branch root controls the source checkout, while `template/.gitignore` controls generated product repositories;
- `README.md`: the branch-root maintainer overview and `template/README.md` downstream overview have distinct responsibilities;
- `docs`: source audits and publication integration remain at root, while downstream contract, migration, evidence, and adoption guidance is canonical under `template/docs`;
- `scripts`: source distribution/publication tooling remains at root, while reusable validators are canonical under `template/scripts`;
- `tests`: source clean-room generation, producer fixtures, publication tests, and review regressions remain at root, while downstream baseline tests are canonical under `template/tests`.

Root `AGENTS.md` is wholly `maintainer`: it is generated from the source-maintainer policy configuration and must not be copied into the Webapp product template. The `translations/` tree is also wholly `maintainer`: it contains non-authoritative locale overlays for source-owned and downstream-canonical documentation without altering the copyable `template/` bytes.

## Conformance strategy

Source CI validates two independent responsibility roots:

1. the complete source checkout for maintainer policy, distribution closure, publication integration, clean-room fixtures, and source regressions; and
2. `template/`, executed as a repository root without access to source siblings.

Reusable validator implementations are executed from `template/scripts` in both cases. Source-maintainer tests that exercise downstream contracts, schemas, dependency locks, or guidance use `template/` as their artifact root. Tests that inspect source workflows, policy, audits, or publication metadata use the branch root explicitly.

The shared generated-repository fixture copies `template/`, not the branch root. Implementation conformance, declarative release-evidence conformance, actual release-evidence production, and release-bundle production therefore begin from the same canonical distribution bytes. Their generated repositories do not contain a nested template tree, distribution manifest, provider publication catalog, source-only validators, audits, or fixture tests.

Assertions after each fixture verify that the canonical `template/` evidence remains in template mode and that no generated `product/` directory leaks back into either the source checkout or the canonical distribution tree.

## Publication boundary

`docs/publication-catalog.json` remains owned by the template source artifact because it is an interface to the unrelated `site` branch. It publishes downstream explanatory documents and machine-readable assets from `template/`, while source architecture and audit documents remain sourced outside `template/`. The catalog itself is not copied into generated product repositories.

Stable document IDs and publication destinations are independent of source paths. Moving downstream canonical publication sources below `template/` therefore does not require changing their public identities or the `contracts` and `schemas` publication destinations.

GitHub Pages deployment is active on the unrelated `site` branch. The `webapp` branch has no deployment authority. Publishing newer Webapp bytes requires a separate reviewed `site` change that locks one reviewed Webapp full commit SHA, integrates the current publication catalog, and passes the site branch's strict validation and deployment boundary.

## Webapp completion criteria

The `webapp` migration is internally complete when:

- the branch root is unambiguously a template-development source tree;
- `template/` is the sole canonical source tree for downstream-owned content;
- `template/` can be copied directly to an empty repository root;
- every copied reference and validator resolves within the copied tree;
- no maintainer-only artifact is present in the copied tree;
- the schema-v2 manifest closes every tracked distribution file;
- no root path remains authoritative for a downstream contract, schema, reusable validator, dependency input, migration, or downstream guidance document;
- source CI validates maintainer concerns and the canonical distribution independently;
- all generated-product stages begin from the canonical distribution;
- publication sources resolve from their intended source or canonical downstream paths without broadening the public allowlist;
- all tests and validator entry points pass; and
- the final reviewed merge commit is recorded for coordinated `site` integration.

Repository-wide publication completion remains a `site` responsibility: update the locked `webapp` full SHA, integrate the reviewed publication catalog, pass strict site validation, and deploy only through the `site` branch's existing publication authority.
