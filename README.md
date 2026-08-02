# Web application repository template

This orphan branch is the development source for a framework-neutral web-application repository template. Its history is intentionally unrelated to the other branches in `TakashiSasaki/templates`.

The template provides repository-level design contracts for browser-facing web applications. The current foundation covers application surfaces, routes, user-visible states, supported viewports, a closed contract manifest, JSON Schemas, validation, tests, and CI. It does not choose an application framework, package manager, deployment target, authentication provider, backend architecture, or coding-agent operating policy.

## Validation baseline

Remove externally supplied Python and pip inputs before the first Python invocation, clear and recreate an isolated environment, then install and verify the complete locked validation graph:

```sh
unset PYTHONHOME PYTHONPATH PYTHONSAFEPATH PYTHONPLATLIBDIR PIP_REQUIREMENT PIP_CONSTRAINT PIP_BUILD_CONSTRAINT PIP_REQUIRE_HASHES PIP_DRY_RUN PIP_NO_BINARY PIP_ONLY_BINARY PIP_PLATFORM PIP_PYTHON_VERSION PIP_IMPLEMENTATION PIP_ABI PIP_UPLOADED_PRIOR_TO PIP_INDEX_URL PIP_EXTRA_INDEX_URL PIP_NO_INDEX PIP_FIND_LINKS PIP_TARGET PIP_PREFIX PIP_ROOT PIP_USER PIP_PYTHON PIP_CACHE_DIR PIP_NO_CACHE_DIR PIP_QUIET PIP_PROGRESS_BAR PIP_EDITABLE PIP_GROUP PIP_REQUIREMENTS_FROM_SCRIPT PIP_REPORT PIP_CONFIG_SETTINGS PIP_KEYRING_PROVIDER PIP_IGNORE_REQUIRES_PYTHON PIP_LOG PIP_TRUSTED_HOST PIP_CERT PIP_CLIENT_CERT PIP_PROXY PIP_TIMEOUT PIP_DEFAULT_TIMEOUT PIP_RETRIES
export PIP_CONFIG_FILE=/dev/null
python -I -m venv --clear .venv
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

`requirements-dev.txt` records the reviewed direct dependency input with arbitrary exact equality (`===`). `requirements-dev.lock` records the complete arbitrary-exact graph used by CI. Using `===` prevents an unrequested local build such as `4.26.0+corp` from satisfying a public-version pin such as `4.26.0`. Clearing `PYTHONHOME`, `PYTHONPATH`, `PYTHONSAFEPATH`, and `PYTHONPLATLIBDIR`, disabling user-site loading, and using isolated interpreter mode before environment creation prevents external modules and `sitecustomize` or `usercustomize` code from affecting the bootstrap interpreter. Job-wide neutralization of `PIP_PYTHON`, cache, quiet, progress-bar, log, keyring-provider, timeout, default-timeout, and retry settings protects the setup action's pre-venv cache lookup; removing requirement, runtime-constraint, build-constraint, hash, dry-run, source-format, binary-only, wheel-compatibility, upload-time, package-source, installation-destination, interpreter, cache, quiet, progress-bar (`PIP_PROGRESS_BAR`), editable, dependency-group, report, build-backend, Requires-Python, keyring-provider, and script-metadata, trusted-host (`PIP_TRUSTED_HOST`), certificate (`PIP_CERT`), client-certificate (`PIP_CLIENT_CERT`), proxy (`PIP_PROXY`), timeout (`PIP_TIMEOUT`), default-timeout (`PIP_DEFAULT_TIMEOUT`), and retry (`PIP_RETRIES`) inputs together with pip configuration files prevents extra requirements, altered installation behavior, or runner-supplied transport and certificate policy from entering validation. `scripts/verify_locked_environment.py` then rejects any installed distribution outside the lock except the virtual environment's bootstrap `pip`. The branch-maintainer baseline is CPython 3.12.13 on Ubuntu 24.04; this validation environment is not a product runtime or deployment choice.

`contracts/manifest.json` is the inventory source of truth. Every domain contract and schema must be registered there; unregistered, missing, duplicated, unsafe, or version-mismatched entries fail validation.

## Template-development rule

Changes for this template branch must be based on `webapp`, not on `main` or `site`. The histories are unrelated and must not be merged merely to share files.

See `TEMPLATE.md` for scope and customization boundaries, [`docs/operationalization.md`](docs/operationalization.md) for the generated-repository workflow, `docs/architecture/responsibility-boundaries.md` for ownership of template, product, and operational concerns, `docs/architecture/contract-completeness.md` for the contract inventory and extension criteria, and `docs/architecture/validation-toolchain.md` for the validation environment and dependency-update procedure.
