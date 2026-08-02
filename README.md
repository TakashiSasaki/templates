# Web application repository template

This orphan branch is the development source for a framework-neutral web-application repository template. Its history is intentionally unrelated to the other branches in `TakashiSasaki/templates`.

The template provides repository-level design contracts for browser-facing web applications. The current foundation covers application surfaces, routes, user-visible states, supported viewports, a closed contract manifest, JSON Schemas, validation, tests, and CI. It does not choose an application framework, package manager, deployment target, authentication provider, backend architecture, or coding-agent operating policy.

## Validation baseline

Clear and recreate an isolated environment, then install the complete locked validation graph:

```sh
python -m venv --clear .venv
. .venv/bin/activate
python -m pip install --disable-pip-version-check --no-deps --requirement requirements-dev.lock
python -m pip check
```

Validate the complete machine-readable contract set through both supported entry points:

```sh
python scripts/validate_contracts.py
python -m scripts.validate_contracts
```

Run the standard-library test suite:

```sh
python -m unittest discover -s tests -v
```

`requirements-dev.txt` records the reviewed direct dependency input with arbitrary exact equality (`===`). `requirements-dev.lock` records the complete arbitrary-exact graph used by CI. Using `===` prevents an unrequested local build such as `4.26.0+corp` from satisfying a public-version pin such as `4.26.0`. The branch-maintainer baseline is CPython 3.12.13 on Ubuntu 24.04; this validation environment is not a product runtime or deployment choice.

`contracts/manifest.json` is the inventory source of truth. Every domain contract and schema must be registered there; unregistered, missing, duplicated, unsafe, or version-mismatched entries fail validation.

## Template-development rule

Changes for this template branch must be based on `webapp`, not on `main` or `site`. The histories are unrelated and must not be merged merely to share files.

See `TEMPLATE.md` for scope and customization boundaries, `docs/architecture/responsibility-boundaries.md` for ownership of template, product, and operational concerns, `docs/architecture/contract-completeness.md` for the contract inventory and extension criteria, and `docs/architecture/validation-toolchain.md` for the validation environment and dependency-update procedure.
