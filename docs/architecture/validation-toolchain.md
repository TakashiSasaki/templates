# Validation toolchain boundary

The Webapp branch carries a small Python toolchain only to validate the repository-local contracts, schemas, and regression tests. This toolchain is part of template maintenance; it is not a framework, product runtime, package-manager choice, deployment target, or coding-agent policy for repositories generated from the template.

## Reproducible validation baseline

The branch-maintainer CI baseline is:

- Ubuntu 24.04;
- CPython 3.12.13;
- immutable commit pins for the checkout and Python-setup actions;
- empty `PYTHONPATH`, `PYTHONSAFEPATH`, and `PYTHONPLATLIBDIR` before the first Python invocation and throughout validation;
- every requirement-bearing or installation-shaping pip environment input removed and pip configuration files disabled during installation;
- a cleared and recreated virtual environment without system site packages;
- arbitrary exact direct dependencies in `requirements-dev.txt`;
- the complete arbitrary exact dependency graph in `requirements-dev.lock`;
- an exact comparison between the installed distribution set and the lock, excluding only the virtual environment's bootstrap `pip`.

Dependency entries use the requirement operator `===`, not PEP 440 version matching with `==`. A public-version specifier such as `name==1.2.3` can also match a candidate carrying an unrequested local label such as `1.2.3+corp`; `name===1.2.3` requires the candidate version string to match exactly. A local build may be selected only when its full local version is intentionally recorded in the reviewed input and lock.

CI clears `PYTHONPATH`, `PYTHONSAFEPATH`, and `PYTHONPLATLIBDIR` before environment creation, disables pip configuration files, removes requirement, constraint, editable, dependency-group, script-metadata, keyring-provider, and transport/certificate override inputs from the install command, clears and recreates `.venv`, and installs only the entries enumerated in `requirements-dev.lock` with dependency resolution disabled. It then compares the installed distributions with the lock before running `pip check`, both public validator entry points, and the complete unit-test suite.

The ordering is significant. `PYTHONPATH` must be cleared before `python -m venv` because external directories can replace the standard-library `venv` module or run `sitecustomize` during bootstrap. `PYTHONSAFEPATH` must also remain empty throughout validation because later non-isolated `.venv/bin/python` invocations honor it. `PYTHONPLATLIBDIR` must likewise remain empty because later non-isolated invocations use it to override Python's standard-library directory selection. The virtual environment must be cleared because `venv` otherwise reuses an existing directory and can retain distributions installed by an earlier lock. Pip configuration and every requirement-bearing or installation-shaping environment input must be removed because requirement, runtime-constraint, build-constraint, hash-enforcement, dry-run, source-format, binary-only, wheel-compatibility, upload-time, package-source, installation-destination, interpreter, cache, quiet, progress-bar (`PIP_PROGRESS_BAR`), keyring-provider (`PIP_KEYRING_PROVIDER`), editable, dependency-group, report, build-backend, Requires-Python, log-path, trusted-host, certificate, client-certificate, proxy, timeout, default-timeout, retry, and script-metadata settings can add packages, change installation behavior, or redirect transport and certificate policy even when the explicit install uses `--no-deps`. The installed-set comparison is the final completeness check: any extra distribution, missing lock entry, or version mismatch fails validation. Isolation from the setup interpreter is also required because `pip check` validates the currently visible installed graph. Disabling dependency resolution prevents an omitted transitive or conditional dependency from being silently retrieved from the package index.

The lock provides exact version-string reproducibility for the selected index configuration. It does not claim byte-for-byte artifact reproducibility or index-origin reproducibility because wheel and source-distribution hashes and source URLs are not recorded. Adding hash enforcement or repository-origin enforcement is a separate trust-boundary change.

## Local verification

Remove external Python and pip inputs before the first Python invocation, clear and recreate the environment, then install and verify exactly the locked graph:

```sh
unset PYTHONHOME PYTHONPATH PYTHONSAFEPATH PYTHONPLATLIBDIR PIP_REQUIREMENT PIP_CONSTRAINT PIP_BUILD_CONSTRAINT PIP_REQUIRE_HASHES PIP_DRY_RUN PIP_NO_BINARY PIP_ONLY_BINARY PIP_PLATFORM PIP_PYTHON_VERSION PIP_IMPLEMENTATION PIP_ABI PIP_UPLOADED_PRIOR_TO PIP_INDEX_URL PIP_EXTRA_INDEX_URL PIP_NO_INDEX PIP_FIND_LINKS PIP_TARGET PIP_PREFIX PIP_ROOT PIP_USER PIP_PYTHON PIP_CACHE_DIR PIP_NO_CACHE_DIR PIP_QUIET PIP_PROGRESS_BAR PIP_EDITABLE PIP_GROUP PIP_REQUIREMENTS_FROM_SCRIPT PIP_REPORT PIP_CONFIG_SETTINGS PIP_KEYRING_PROVIDER PIP_IGNORE_REQUIRES_PYTHON PIP_LOG PIP_TRUSTED_HOST PIP_CERT PIP_CLIENT_CERT PIP_PROXY PIP_TIMEOUT PIP_DEFAULT_TIMEOUT PIP_RETRIES
export PIP_CONFIG_FILE=/dev/null
python -I -m venv --clear .venv
. .venv/bin/activate
python -m pip install --disable-pip-version-check --no-deps --requirement requirements-dev.lock
python scripts/verify_locked_environment.py
python -m pip check
```

Run both supported validator forms and the tests:

```sh
python scripts/validate_contracts.py
python -m scripts.validate_contracts
python -m unittest discover -s tests -v
```

A different local Python may be useful for compatibility investigation, but CI is authoritative for the selected baseline.

## Dependency update procedure

A dependency update must be an intentional reviewed change that:

1. changes the arbitrary exact direct pin in `requirements-dev.txt` when required;
2. resolves and records the complete arbitrary-exact graph for CPython 3.12.13 on Ubuntu 24.04 in `requirements-dev.lock`;
3. updates the reproducibility regression expectations;
4. clears `PYTHONPATH`, `PYTHONSAFEPATH`, and `PYTHONPLATLIBDIR` before the first Python invocation, removes requirement, constraint, editable, dependency-group, script-metadata, progress-bar, keyring-provider, and transport, certificate, timeout, default-timeout, and retry pip inputs, disables pip configuration files, and clears and recreates the virtual environment without system site packages;
5. installs the lock with dependency resolution disabled, runs `scripts/verify_locked_environment.py`, and runs `pip check` there;
6. runs the standalone validator, module validator, and complete unit-test suite from that environment;
7. records any baseline, compatibility, or diagnostic changes in the pull request.

Do not update the lock incidentally with contract, schema, documentation, or fixture work.

## Product-repository boundary

A repository generated from this template still selects its own implementation runtime, framework, package manager, build commands, browser matrix, and deployment mechanism. It may retain this validator toolchain, replace it with an equivalent verified integration, or isolate it from the product runtime. Such a change must preserve the contract-validation semantics and public diagnostics relied on by that repository.
