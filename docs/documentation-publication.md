# Documentation publication

The `policy` branch builds this documentation through `.github/workflows/pages.yml`. GitHub Pages artifact upload and deployment are retained in the workflow but intentionally disabled.

## Current workflow boundary

Both pull requests targeting `policy` and pushes to `policy` regenerate repository previews and documentation assets, verify the documented tree, and run a strict MkDocs build. The enabled build baseline is Ubuntu 24.04 with CPython 3.12.13. Checkout and Python setup actions are pinned to reviewed full commit SHAs, and every documentation command runs from a cleared branch-maintainer virtual environment rather than the runner's system environment.

Before `actions/setup-python` performs its cache lookup, the build job neutralizes Python startup inputs and pip cache, output, parser, behavior, and transport inputs that could redirect or terminate the pre-venv toolchain. It creates `.venv` with an isolated bootstrap interpreter, installs the arbitrary-exact documentation lock with dependency resolution disabled and pip isolated from unlisted environment inputs, verifies the complete installed distribution set, and runs `pip check` before generating or building documentation.

The Pages artifact-upload step and deployment job remain present for later use, but both are protected by a hard-coded false condition. Therefore no current `policy` event uploads a Pages artifact or deploys a site. Pull-request and push builds receive only `contents: read` unless the disabled deployment job is explicitly enabled by a reviewed change.

The workflow does not fetch `main`, `site`, `webapp`, the former orphan bootstrap branch, or the former `TakashiSasaki/agent-policy` repository. The repository default branch is `main`, while this workflow intentionally exists only in the unrelated `policy` history. GitHub manual dispatch requires the workflow file to exist on the default branch, so this workflow deliberately omits `workflow_dispatch`.

All third-party actions are pinned to full commit SHAs. `requirements-docs.txt` records the reviewed direct documentation dependencies with arbitrary exact equality (`===`), while `requirements-docs.lock` records the complete arbitrary-exact graph for CPython 3.12.13 on Ubuntu 24.04. `scripts/verify_docs_environment.py` rejects missing, extra, or version-mismatched distributions outside that lock, excluding only the virtual environment's bootstrap `pip`. Dependency updates require a reviewed re-resolution and successful strict build.

The lock fixes exact distribution version strings. It does not provide byte-for-byte artifact reproducibility or cryptographic index-origin reproducibility because hashes and source URLs are not recorded. Hash enforcement and explicit repository-origin enforcement are separate trust-boundary changes.

## Local build reproduction

Remove external Python and pip inputs before the first Python invocation, then reproduce the enabled documentation build from the reviewed lock:

```bash
unset PYTHONHOME PYTHONPATH PYTHONSAFEPATH PYTHONPLATLIBDIR PYTHONHASHSEED PYTHONUTF8 PYTHONINTMAXSTRDIGITS PYTHONMALLOC PYTHONIOENCODING PYTHONTRACEMALLOC PYTHONINSPECT PIP_REQUIREMENT PIP_CONSTRAINT PIP_BUILD_CONSTRAINT PIP_REQUIRE_HASHES PIP_DRY_RUN PIP_NO_BINARY PIP_ONLY_BINARY PIP_PLATFORM PIP_PYTHON_VERSION PIP_IMPLEMENTATION PIP_ABI PIP_UPLOADED_PRIOR_TO PIP_INDEX_URL PIP_EXTRA_INDEX_URL PIP_NO_INDEX PIP_FIND_LINKS PIP_TARGET PIP_PREFIX PIP_ROOT PIP_USER PIP_PYTHON PIP_CACHE_DIR PIP_NO_CACHE_DIR PIP_QUIET PIP_PROGRESS_BAR PIP_EDITABLE PIP_GROUP PIP_REQUIREMENTS_FROM_SCRIPT PIP_REPORT PIP_CONFIG_SETTINGS PIP_USE_PEP517 PIP_COMPILE PIP_ISOLATED PIP_USE_FEATURE PIP_VERBOSE PIP_DEBUG PIP_NO_INPUT PIP_DISABLE_PIP_VERSION_CHECK PIP_NO_COLOR PIP_REQUIRE_VIRTUALENV PIP_USE_DEPRECATED PIP_NO_PYTHON_VERSION_WARNING PIP_KEYRING_PROVIDER PIP_EXISTS_ACTION PIP_IGNORE_REQUIRES_PYTHON PIP_LOG PIP_TRUSTED_HOST PIP_CERT PIP_CLIENT_CERT PIP_PROXY PIP_TIMEOUT PIP_DEFAULT_TIMEOUT PIP_RETRIES
export PIP_CONFIG_FILE=/dev/null
python -I -m venv --clear .venv
. .venv/bin/activate
python -m pip install --isolated --disable-pip-version-check --no-deps --requirement requirements-docs.lock
python scripts/verify_docs_environment.py
python -m pip check
python scripts/generate_repository_preview.py
python scripts/verify-repository-structure.py --check
python scripts/generate-doc-assets.py
python -m mkdocs build --strict --clean
```

## Deployment enablement boundary

Do not enable Pages deployment as an incidental documentation or policy change. Enabling publication requires a dedicated reviewed change that:

1. removes the hard-coded false condition from both the Pages artifact-upload step and the deployment job while retaining the `policy` branch and non-pull-request guards;
2. confirms the repository Pages source and environment settings;
3. determines whether `agent-policy.moukaeritai.work` should be moved from the former repository;
4. runs and verifies the enabled deployment before describing publication as complete.

Until that change is approved and merged, Pages settings and custom-domain migration are deliberately deferred.

## Build verification

The currently enabled documentation build is successful only when all of the following pass:

- clean creation of the isolated documentation environment;
- installation from the complete arbitrary-exact dependency lock with dependency resolution disabled;
- exact installed-distribution verification and `pip check`;
- repository preview generation;
- documented-tree verification;
- documentation asset generation;
- build metadata generation;
- `mkdocs build --strict --clean`;
- regression tests confirming both deployment guards remain disabled.

A successful MkDocs build does not mean that documentation has been published. Publication remains incomplete while artifact upload and deployment are disabled.
