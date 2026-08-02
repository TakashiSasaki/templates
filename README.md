# Web application repository template

This orphan branch is the development source for a framework-neutral web-application repository template. Its history is intentionally unrelated to the other branches in `TakashiSasaki/templates`.

The template provides repository-level design contracts for browser-facing web applications. The current foundation covers application surfaces, routes, user-visible states, supported viewports, a closed contract manifest, JSON Schemas, validation, tests, and CI. It does not choose an application framework, package manager, deployment target, authentication provider, backend architecture, or coding-agent operating policy.

## Validation baseline

Remove externally supplied Python and pip inputs before the first Python invocation, clear and recreate an isolated environment, then install and verify the complete locked validation graph:

```sh
unset PYTHONPATH PIP_REQUIREMENT PIP_CONSTRAINT PIP_EDITABLE
export PIP_CONFIG_FILE=/dev/null
python -m venv --clear .venv
. .venv/bin/activate
python -m pip install --disable-pip-version-check --no-deps --requirement requirements-dev.lock
python scripts/verify_locked_environment.py
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

`requirements-dev.txt` records the reviewed direct dependency input with arbitrary exact equality (`===`). `requirements-dev.lock` records the complete arbitrary-exact graph used by CI. Using `===` prevents an unrequested local build such as `4.26.0+corp` from satisfying a public-version pin such as `4.26.0`. Clearing `PYTHONPATH` before environment creation prevents external modules and `sitecustomize` code from affecting the bootstrap interpreter. Disabling pip requirement injection and config files prevents extra requirements from being added to the install, and `scripts/verify_locked_environment.py` rejects any installed distribution outside the lock except the virtual environment's bootstrap `pip`. The branch-maintainer baseline is CPython 3.12.13 on Ubuntu 24.04; this validation environment is not a product runtime or deployment choice.

`contracts/manifest.json` is the inventory source of truth. Every domain contract and schema must be registered there; unregistered, missing, duplicated, unsafe, or version-mismatched entries fail validation.

## Template-development rule

Changes for this template branch must be based on `webapp`, not on `main` or `site`. The histories are unrelated and must not be merged merely to share files.

See `TEMPLATE.md` for scope and customization boundaries, `docs/architecture/responsibility-boundaries.md` for ownership of template, product, and operational concerns, `docs/architecture/contract-completeness.md` for the contract inventory and extension criteria, and `docs/architecture/validation-toolchain.md` for the validation environment and dependency-update procedure.
