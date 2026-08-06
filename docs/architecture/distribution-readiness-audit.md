# Copyable template distribution readiness audit

Audit scope: the `webapp` template-development source and the committed downstream distribution under `template/`.

Audit status: **Webapp-internal complete; coordinated `site` integration pending.**

This audit does not authorize GitHub Pages deployment. It establishes that the final `webapp` revision produced by this work may be supplied to the unrelated `site` branch for build-only compatibility validation.

## Artifact identity

| Criterion | Result | Evidence |
| --- | --- | --- |
| Branch root is the template-development source, not the downstream repository root | Pass | `README.md`, `docs/architecture/distribution-boundary.md` |
| `template/` is the sole direct-copy root | Pass | `distribution-manifest.json`, `docs/architecture/distribution-classification.json` |
| Generated product repositories are distinct from source and distribution artifacts | Pass | `template/TEMPLATE.md`, `tests/test_generated_repository_conformance.py` |
| Source-only publication, audits, producers, and review regressions are outside `template/` | Pass | `distribution-manifest.json`, `template/tests/test_template_baseline.py` |

## Distribution closure

| Criterion | Result | Evidence |
| --- | --- | --- |
| Every tracked distribution file is declared | Pass | `scripts/validate_distribution.py` |
| Missing and undeclared files are rejected | Pass | `scripts/validate_distribution.py`, `tests/test_distribution_boundary.py` |
| Unsafe, absolute, dot-component, `.git`, and nonportable paths are rejected | Pass | `scripts/validate_distribution.py` |
| Symbolic and non-regular tracked files are rejected | Pass | `scripts/validate_distribution.py` |
| Destination collisions are rejected | Pass | `scripts/validate_distribution.py` |
| Distribution top-level inventory is closed | Pass | `distribution-manifest.json`, `scripts/validate_distribution.py` |
| Maintainer-only residue is rejected | Pass | `distribution-manifest.json`, `template/tests/test_template_baseline.py` |
| Mirrored files are byte-identical to source-owned canonical inputs | Pass | `distribution-manifest.json`, `scripts/validate_distribution.py` |
| Distribution-owned files are explicit | Pass | `distribution-manifest.json` |

## Repository-root usability

| Criterion | Result | Evidence |
| --- | --- | --- |
| `cp -a template/. <new-root>/` is the supported operation | Pass | `docs/architecture/distribution-boundary.md` |
| Downstream README is independent of the source README | Pass | `template/README.md` |
| Downstream CI is independent of source CI | Pass | `template/.github/workflows/contract-validation.yml` |
| Validator dependencies are present in the copied root | Pass | `template/requirements-dev.txt`, `template/requirements-dev.lock` |
| Contracts, schemas, migrations, validators, and guidance resolve within the copied root | Pass | `template/contracts`, `template/schemas`, `template/docs`, `template/scripts` |
| Initial implementation, release-evidence, and release-bundle documents are in template mode | Pass | `template/tests/test_template_baseline.py` |
| All ten retained validator entry points execute from the distribution root | Pass | `.github/workflows/contract-validation.yml` |
| Distribution baseline tests execute from the distribution root | Pass | `.github/workflows/contract-validation.yml`, `template/tests/test_template_baseline.py` |

## Generated-product transition

| Criterion | Result | Evidence |
| --- | --- | --- |
| Shared generated-repository fixture copies `template/`, not the branch root | Pass | `tests/test_generated_repository_conformance.py` |
| Generated repository contains no nested `template/` | Pass | `tests/test_generated_repository_conformance.py`, `tests/test_copyable_distribution_conformance.py` |
| Generated repository contains no distribution manifest or provider publication catalog | Pass | same |
| Generated repository contains no source-only distribution or publication validator | Pass | same |
| Product implementation evidence reaches verified product mode | Pass | `tests/test_generated_repository_conformance.py` |
| Product proof executes all 52 positive and negative fixture checks | Pass | same |
| Declarative release evidence validates exact revision and command digest binding | Pass | `tests/test_generated_release_evidence_conformance.py` |
| Actual release evidence derives results from reviewed process execution | Pass | `tests/test_generated_release_evidence_production.py` |
| Release bundle binds approved evidence and exact active contract bytes | Pass | `tests/test_generated_release_bundle_production.py` |
| Source and distribution evidence remain in template mode after fixture disposal | Pass | generated-product suites |

## Source and distribution CI

The source workflow performs these independent layers:

1. validate the closed distribution through standalone and module entry points;
2. validate all source contracts and evidence through ten retained entry points;
3. run the complete source-maintainer suite, including all generated-product stages whose shared copy source is `template/`;
4. verify the installed validator dependency set;
5. execute all ten retained validator entry points from `template/` as the working repository root; and
6. run the distribution baseline tests from `template/`.

A success therefore proves both source-maintainer integrity and downstream-root usability. Neither layer substitutes for the other.

## Publication boundary

`docs/publication-catalog.json` remains source-owned. It publishes downstream documents from `template/` and source-only architecture from the branch root. Contract and schema asset sources are `template/contracts` and `template/schemas`, while their stable publication destinations remain `contracts` and `schemas`.

The provider catalog does not deploy Pages and does not determine the live deployment state. The unrelated `site` branch owns the reviewed full-SHA lock, integrated build, provenance, and deployment authority.

## Remaining repository-wide work

The `webapp` branch is not the final repository-wide completion point. After this audit and its CI pass:

1. merge the final `webapp` pull request and record its merge commit full SHA;
2. create a `site` pull request from the then-current suspended `site` head;
3. update `publication-sources.json` to the final `webapp` full SHA;
4. update site navigation and repository-tree presentation for the source and copyable-template views as required;
5. pass integrated build-only validation while deployment remains suspended;
6. merge the compatibility update without deploying; and
7. restore site-only Pages deployment through a separate reviewed pull request.

## Webapp release gate

The `webapp` distribution may be handed to `site` only when:

- this audit remains internally consistent with the final tree;
- distribution validation passes through both entry points;
- all source and distributed contract validator forms pass;
- all source-maintainer and downstream baseline tests pass;
- the final pull request has no unresolved blocking review findings; and
- the final merge commit full SHA is known.
