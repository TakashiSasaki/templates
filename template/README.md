# Web application repository foundation

This repository foundation provides framework-neutral, repository-level contracts for browser-facing Web applications. It defines application surfaces, canonical routes, user-visible states, supported viewports and input capabilities, implementation evidence, revision-bound release evidence, digest-closed release bundles, contract evolution, schemas, validators, tests, and CI validation.

It intentionally does not select an application framework, package manager, rendering model, backend, authentication provider, persistence model, CI provider, artifact store, deployment target, browser matrix, signing system, or observability platform. A product repository created from this foundation must make those decisions explicitly.

## Start here

1. Read [`TEMPLATE.md`](TEMPLATE.md) for the scope and required customization contract.
2. Replace the example declarations registered by [`contracts/manifest.json`](contracts/manifest.json) with product-specific declarations.
3. Select one product toolchain and add the application implementation.
4. Change `contracts/implementation-evidence.json` from `mode: template` to `mode: product` only after every required implementation boundary and positive and negative proof is verified.
5. Materialize product release evidence and the release bundle for one exact immutable candidate revision.
6. Remove guidance that no longer applies to the product while preserving the contract, schema, migration, and evidence semantics that the product adopts.

The complete transition is described in [`docs/operationalization.md`](docs/operationalization.md).

## Validation environment

The included Python environment is isolated from the product runtime. Create and verify it before running the validators:

```sh
unset PYTHONHOME PYTHONPATH PYTHONSAFEPATH PYTHONPLATLIBDIR PYTHONHASHSEED PYTHONUTF8 PYTHONINTMAXSTRDIGITS PYTHONMALLOC PYTHONIOENCODING PYTHONTRACEMALLOC PYTHONINSPECT
export PYTHONNOUSERSITE=1
export PIP_CONFIG_FILE=/dev/null
python -I -m venv --clear .venv
. .venv/bin/activate
python -m pip install --isolated --disable-pip-version-check --no-deps --requirement requirements-dev.lock
python scripts/verify_locked_environment.py
python -m pip check
```

Run each validator through both supported entry points:

```sh
python scripts/validate_contracts.py
python -m scripts.validate_contracts
python scripts/validate_contract_evolution.py
python -m scripts.validate_contract_evolution
python scripts/validate_implementation_evidence.py
python -m scripts.validate_implementation_evidence
python scripts/validate_release_evidence.py
python -m scripts.validate_release_evidence
python scripts/validate_release_bundle.py
python -m scripts.validate_release_bundle
python -m unittest discover -s tests -v
```

While the repository remains in template mode, the release-evidence and release-bundle validators run without an expected revision. After product records are materialized, invoke both forms with the exact candidate commit:

```sh
python scripts/validate_release_evidence.py --expected-revision <40-hex-commit-sha>
python -m scripts.validate_release_evidence --expected-revision <40-hex-commit-sha>
python scripts/validate_release_bundle.py --expected-revision <40-hex-commit-sha>
python -m scripts.validate_release_bundle --expected-revision <40-hex-commit-sha>
```

## Contract inventory

`contracts/manifest.json` is the closed inventory of active contract families, retired-family tombstones, schemas, stable migration slugs, contiguous version histories, and migration artifacts. The validators reject unregistered contract or schema files, missing registered files, unsafe paths, inconsistent versions, incomplete histories, unregistered migrations, broken cross-contract references, incomplete implementation evidence, stale release results, and stale bundle bytes.

The initial documents use explicit template mode where applicable. Template mode states requirements without claiming that a product implementation, command execution, approval decision, or handoff already exists.

## Repository policy is optional

This copyable Web-application foundation is not pre-enrolled in the source repository's shared policy toolchain. It intentionally contains no inherited `.agent-policy.yml`, lock file, generated maintainer `AGENTS.md`, repository-local policy input, or shared-policy check workflow.

After copying, the owner of the concrete product repository may adopt shared repository policy separately if that operating model is desired. Treat that as an explicit repository-maintenance decision using a reviewed immutable toolchain revision, and preserve the Web-application contracts already established by this foundation. Policy adoption is not part of the byte-preserving copy operation and is not a prerequisite for validating the artifact contracts.

## Product ownership

The generated product owns all concrete implementation and operational decisions, including:

- the actual surfaces, routes, roles, states, viewports, and terminology;
- trusted authentication and authorization enforcement;
- framework, backend, persistence, package, CI, release, deployment, and observability choices;
- authoritative product commands and release gates;
- implementation-level accessibility, security, migration, rollback, and end-to-end tests;
- command execution, evidence retention, provenance, approval, signing, release publication, deployment, and environment verification.

Repository governance, coding-agent operating policy, and organization-specific approval rules are separate concerns. They may be adopted independently but are not prerequisites for validating these Web-application contracts.
