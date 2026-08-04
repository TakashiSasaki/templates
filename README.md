# Web application repository template

This orphan branch is the development source for a framework-neutral web-application repository template. Its history is intentionally unrelated to the other branches in `TakashiSasaki/templates`.

The template provides repository-level design contracts for browser-facing web applications. The current foundation covers application surfaces, routes, user-visible states, supported viewports, machine-readable implementation evidence, revision-bound release evidence, digest-closed release bundles, a closed contract manifest with active and retired version histories, stable migration ownership, JSON Schemas, validation, tests, and CI. It does not choose an application framework, package manager, deployment target, CI provider, authentication provider, backend architecture, artifact store, or coding-agent operating policy.

## Validation baseline

Remove externally supplied Python and pip inputs before the first Python invocation, clear and recreate an isolated environment, then install and verify the complete locked validation graph:

```sh
unset PYTHONHOME PYTHONPATH PYTHONSAFEPATH PYTHONPLATLIBDIR PYTHONHASHSEED PYTHONUTF8 PYTHONINTMAXSTRDIGITS PYTHONMALLOC PYTHONIOENCODING PYTHONTRACEMALLOC PYTHONINSPECT PIP_REQUIREMENT PIP_CONSTRAINT PIP_BUILD_CONSTRAINT PIP_REQUIRE_HASHES PIP_DRY_RUN PIP_NO_BINARY PIP_ONLY_BINARY PIP_PLATFORM PIP_PYTHON_VERSION PIP_IMPLEMENTATION PIP_ABI PIP_UPLOADED_PRIOR_TO PIP_INDEX_URL PIP_EXTRA_INDEX_URL PIP_NO_INDEX PIP_FIND_LINKS PIP_TARGET PIP_PREFIX PIP_ROOT PIP_USER PIP_PYTHON PIP_CACHE_DIR PIP_NO_CACHE_DIR PIP_QUIET PIP_PROGRESS_BAR PIP_EDITABLE PIP_GROUP PIP_REQUIREMENTS_FROM_SCRIPT PIP_REPORT PIP_CONFIG_SETTINGS PIP_USE_PEP517 PIP_COMPILE PIP_ISOLATED PIP_USE_FEATURE PIP_VERBOSE PIP_DEBUG PIP_NO_INPUT PIP_DISABLE_PIP_VERSION_CHECK PIP_NO_COLOR PIP_REQUIRE_VIRTUALENV PIP_USE_DEPRECATED PIP_NO_PYTHON_VERSION_WARNING PIP_KEYRING_PROVIDER PIP_EXISTS_ACTION PIP_IGNORE_REQUIRES_PYTHON PIP_LOG PIP_TRUSTED_HOST PIP_CERT PIP_CLIENT_CERT PIP_PROXY PIP_TIMEOUT PIP_DEFAULT_TIMEOUT PIP_RETRIES
export PIP_CONFIG_FILE=/dev/null
python -I -m venv --clear .venv
. .venv/bin/activate
python -m pip install --isolated --disable-pip-version-check --no-deps --requirement requirements-dev.lock
python scripts/verify_locked_environment.py
python -m pip check
```

Validate the complete machine-readable contract set through both supported entry points:

```sh
python scripts/validate_contracts.py
python -m scripts.validate_contracts
```

Validate active and retired contract histories and the closed migration-artifact inventory through both supported entry points:

```sh
python scripts/validate_contract_evolution.py
python -m scripts.validate_contract_evolution
```

Validate implementation-evidence coverage, command references, and release-gate definitions through both supported entry points:

```sh
python scripts/validate_implementation_evidence.py
python -m scripts.validate_implementation_evidence
```

Validate template-mode release requirements through both entry points:

```sh
python scripts/validate_release_evidence.py
python -m scripts.validate_release_evidence
```

A generated product validates completed release evidence by supplying the exact immutable candidate revision:

```sh
python scripts/validate_release_evidence.py --expected-revision <40-hex-commit-sha>
python -m scripts.validate_release_evidence --expected-revision <40-hex-commit-sha>
```

Validate template-mode release-bundle requirements through both entry points:

```sh
python scripts/validate_release_bundle.py
python -m scripts.validate_release_bundle
```

After approved release evidence exists, a generated product validates the digest-closed handoff bundle for the same candidate revision:

```sh
python scripts/validate_release_bundle.py --expected-revision <40-hex-commit-sha>
python -m scripts.validate_release_bundle --expected-revision <40-hex-commit-sha>
```

Run the standard-library test suite:

```sh
python -m unittest discover -s tests -v
```

The clean-room generated-repository classes are template-maintainer-only. When these test files are retained after a generated repository switches its source implementation evidence to `mode: product`, those classes report skipped and separate scope regressions verify the boundary.

`requirements-dev.txt` records the reviewed direct dependency input with arbitrary exact equality (`===`). `requirements-dev.lock` records the complete arbitrary-exact graph used by CI. Using `===` prevents an unrequested local build such as `4.26.0+corp` from satisfying a public-version pin such as `4.26.0`. Clearing `PYTHONHOME`, `PYTHONPATH`, `PYTHONSAFEPATH`, `PYTHONPLATLIBDIR`, `PYTHONHASHSEED`, `PYTHONUTF8`, `PYTHONINTMAXSTRDIGITS`, `PYTHONMALLOC`, `PYTHONIOENCODING`, and `PYTHONTRACEMALLOC`, `PYTHONINSPECT`, disabling user-site loading, and using isolated interpreter mode before environment creation prevents external modules and `sitecustomize` or `usercustomize` code from affecting the bootstrap interpreter. Job-wide neutralization of `PIP_PYTHON`, cache, quiet, progress-bar, log, keyring-provider, exists-action, use-pep517, compile, isolated, use-feature, verbose, debug, no-input, disable-pip-version-check, no-color, require-virtualenv, use-deprecated, no-python-version-warning, timeout, default-timeout, and retry settings protects the setup action's pre-venv cache lookup; removing requirement, runtime-constraint, build-constraint, hash, dry-run, source-format, binary-only, wheel-compatibility, upload-time, package-source, installation-destination, interpreter, cache, quiet, progress-bar (`PIP_PROGRESS_BAR`), editable, dependency-group, report, build-backend, Requires-Python, keyring-provider (`PIP_KEYRING_PROVIDER`), use-pep517 (`PIP_USE_PEP517`), compile (`PIP_COMPILE`), isolated (`PIP_ISOLATED`), use-feature (`PIP_USE_FEATURE`), verbose (`PIP_VERBOSE`), debug (`PIP_DEBUG`), no-input (`PIP_NO_INPUT`), disable-pip-version-check (`PIP_DISABLE_PIP_VERSION_CHECK`), no-color (`PIP_NO_COLOR`), require-virtualenv (`PIP_REQUIRE_VIRTUALENV`), use-deprecated (`PIP_USE_DEPRECATED`), no-python-version-warning (`PIP_NO_PYTHON_VERSION_WARNING`), exists-action (`PIP_EXISTS_ACTION`), and script-metadata, trusted-host (`PIP_TRUSTED_HOST`), certificate (`PIP_CERT`), client-certificate (`PIP_CLIENT_CERT`), proxy (`PIP_PROXY`), timeout (`PIP_TIMEOUT`), default-timeout (`PIP_DEFAULT_TIMEOUT`), and retry (`PIP_RETRIES`) inputs together with pip configuration files and the install command's `--isolated` mode prevent extra requirements, altered installation behavior, or runner-supplied transport and certificate policy from entering validation. `scripts/verify_locked_environment.py` then rejects any installed distribution outside the lock except the virtual environment's bootstrap `pip`. The branch-maintainer baseline is CPython 3.12.13 on Ubuntu 24.04; this validation environment is not a product runtime or deployment choice.

`contracts/manifest.json` is the inventory source of truth. Every active domain contract and schema is registered there; retired non-core families retain tombstones without live document or schema files. Each family has a stable `migrationSlug`, every manifest and contract version has a contiguous history, and every transition after version 1 registers exactly one deterministic migration. The evolution validator scans every artifact under `docs/migrations/`, regardless of extension, and rejects unregistered, missing, duplicated, unreadable, visually empty, non-regular, symbolic, version-mismatched, or evolution-incomplete artifacts.

`contracts/implementation-evidence.json` connects every surface, route, UI state, viewport, input capability, and registered version transition to implementation ownership, positive and negative evidence, authoritative commands, and release-gate definitions. The template ships an explicit requirement inventory in `mode: template`; generated repositories switch to `mode: product` only after replacing those requirements with verified repository-local evidence.

`contracts/release-evidence.json` records whether the current command and gate definitions actually passed for one exact product revision. Product mode covers every registered gate and every command executed by those gates, binds command results to current command text by SHA-256, records result locators and UTC chronology, and requires an approved release decision. The validator records no CI-provider assumptions and executes no command strings.

`contracts/release-bundle.json` records the exact active contract bytes handed to the next system after approval. Product mode binds the same candidate revision to every active contract except the bundle manifest itself, in manifest order, using the registered path and SHA-256 of current file bytes. The separate manifest avoids self-digest recursion while including release evidence as a digest-bound artifact. Packaging, signing, retention, release publication, deployment, and environment observation remain product-owned.

## Generated-repository conformance

`tests/test_generated_repository_conformance.py` copies the complete template into a temporary clean-room repository, excludes source-control and local-environment residue, explicitly settles the example contracts as declarations for a deterministic fixture product, converts only the copied implementation-evidence document to `mode: product`, and materializes repository-local implementation and proof locations for all 26 current targets.

The fixture registers one reviewed product proof command and one selected release gate. The test harness invokes the known proof script directly with a fixed argument vector; it does not parse or execute arbitrary command strings. The script verifies 52 positive and negative outcomes, after which the implementation fixture runs the first six validator entry points from the generated repository root.

`tests/test_generated_release_evidence_conformance.py` extends the generated product with revision-bound command and gate results and executes both release validator entry points. It proves stable rejection of revision mismatch and command-definition digest drift.

The existing clean-room coverage exercises the first eight retained validator entry points. CI additionally executes both release-bundle validator forms. Phase 3B will extend the clean room to produce exact artifact digests and exercise all ten forms from a generated product. Additional negative copies currently cover template residue, missing targets, unverified boundaries, unknown or unused commands, unused gates, release-gate closure gaps, false proof results, release revision mismatch, and command-definition drift. The template source remains in template mode before and after every fixture run. See [`docs/architecture/generated-repository-conformance.md`](docs/architecture/generated-repository-conformance.md).

## Template-development rule

Changes for this template branch must be based on `webapp`, not on `main`, `site`, or `policy`. The histories are unrelated and must not be merged merely to share files.

See `TEMPLATE.md` for scope and customization boundaries, [`docs/operationalization.md`](docs/operationalization.md) for the generated-repository workflow, `docs/architecture/responsibility-boundaries.md` for ownership of template, product, and operational concerns, [`docs/architecture/contract-completeness.md`](docs/architecture/contract-completeness.md) for the closed contract inventory and extension criteria, [`docs/architecture/contract-evolution.md`](docs/architecture/contract-evolution.md) for versioning, stable migration ownership, retirement, and rollback rules, [`docs/architecture/implementation-evidence.md`](docs/architecture/implementation-evidence.md) for implementation ownership and release-gate definitions, [`docs/architecture/release-evidence.md`](docs/architecture/release-evidence.md) for exact-revision release results, [`docs/architecture/release-bundle.md`](docs/architecture/release-bundle.md) for digest-closed provider-neutral handoff, [`docs/architecture/generated-repository-conformance.md`](docs/architecture/generated-repository-conformance.md) for the clean-room product transition, and `docs/architecture/validation-toolchain.md` for the validation environment and dependency-update procedure.
