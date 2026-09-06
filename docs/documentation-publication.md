# Documentation build and publication boundary

The `policy` branch builds its documentation through `.github/workflows/pages.yml`. Despite the historical filename, the workflow contains no GitHub Pages deployment route. It performs a strict branch-local documentation build only.

## Current workflow boundary

Pull requests targeting `policy` or authority-local `policy-*` stacked bases, and pushes to `policy`, regenerate repository previews and documentation assets, verify the documented tree, generate build metadata, and run a strict MkDocs build. The enabled build baseline is Ubuntu 24.04 with CPython 3.12.13. Checkout and Python setup actions are pinned to reviewed full commit SHAs, and every documentation command runs from a cleared branch-maintainer virtual environment rather than the runner's system environment.

The documentation build also consumes the Site-owned generic schema-v3 publication protocol. It sparse-checks out only `scripts/publication_contract.py` from reviewed Site merge commit `3ae5d1e60c65e7a8ebf5f9af0436044484e42983` (Site PR #313) and executes that exact stdlib-only file against the Policy checkout. This is an immutable development/publication protocol dependency, not a runtime dependency of `agent-policy`. Policy does not keep a duplicate generic publication parser or validator.

Before `actions/setup-python` performs its cache lookup, the build job neutralizes Python startup inputs and pip cache, output, parser, behavior, and transport inputs that could redirect or terminate the pre-venv toolchain. It creates `.venv` with an isolated bootstrap interpreter, installs the arbitrary-exact documentation lock with dependency resolution disabled and pip isolated from unlisted environment inputs, verifies the complete installed distribution set, and runs `pip check` before generating or building documentation.

The workflow has only `contents: read`. It contains no Pages artifact upload, Pages deployment or configuration action, `pages: write`, `id-token: write`, `github-pages` environment, deployment job, reusable deployment entry point, or manual publication trigger. No `policy` event can upload or deploy a GitHub Pages site.

The workflow does not check out Composition or any retired provider branch. Its only cross-authority checkout is the single Site protocol file at the reviewed full SHA above; it does not execute a mutable `site` branch tip or consume Site's reader IA as Policy semantics. The repository default branch is irrelevant to the Policy event boundary. The workflow is scoped explicitly to pushes on `policy` and pull requests targeting `policy` or authority-local `policy-*` bases, and deliberately omits `workflow_dispatch` and `workflow_call`.

All third-party actions are pinned to full commit SHAs. `requirements-docs.txt` records the reviewed direct documentation dependencies with arbitrary exact equality (`===`), while `requirements-docs.lock` records the complete arbitrary-exact graph for CPython 3.12.13 on Ubuntu 24.04. `scripts/verify_docs_environment.py` rejects missing, extra, or version-mismatched distributions outside that lock, excluding only the virtual environment's bootstrap `pip`. Dependency updates require a reviewed re-resolution and successful strict build.

The lock fixes exact distribution version strings. It does not provide byte-for-byte artifact reproducibility or cryptographic index-origin reproducibility because hashes and source URLs are not recorded. Hash enforcement and explicit repository-origin enforcement are separate trust-boundary changes.

## Local build reproduction

Remove external Python and pip inputs before the first Python invocation, then reproduce the enabled documentation build from the reviewed lock. Make a separate checkout of Site commit `3ae5d1e60c65e7a8ebf5f9af0436044484e42983` available before the protocol step:

```bash
unset PYTHONHOME PYTHONPATH PYTHONSAFEPATH PYTHONPLATLIBDIR PYTHONHASHSEED PYTHONUTF8 PYTHONINTMAXSTRDIGITS PYTHONMALLOC PYTHONIOENCODING PYTHONTRACEMALLOC PYTHONINSPECT PIP_REQUIREMENT PIP_CONSTRAINT PIP_BUILD_CONSTRAINT PIP_REQUIRE_HASHES PIP_DRY_RUN PIP_NO_BINARY PIP_ONLY_BINARY PIP_PLATFORM PIP_PYTHON_VERSION PIP_IMPLEMENTATION PIP_ABI PIP_UPLOADED_PRIOR_TO PIP_INDEX_URL PIP_EXTRA_INDEX_URL PIP_NO_INDEX PIP_FIND_LINKS PIP_TARGET PIP_PREFIX PIP_ROOT PIP_USER PIP_PYTHON PIP_CACHE_DIR PIP_NO_CACHE_DIR PIP_QUIET PIP_PROGRESS_BAR PIP_EDITABLE PIP_GROUP PIP_REQUIREMENTS_FROM_SCRIPT PIP_REPORT PIP_CONFIG_SETTINGS PIP_USE_PEP517 PIP_COMPILE PIP_ISOLATED PIP_USE_FEATURE PIP_VERBOSE PIP_DEBUG PIP_NO_INPUT PIP_DISABLE_PIP_VERSION_CHECK PIP_NO_COLOR PIP_REQUIRE_VIRTUALENV PIP_USE_DEPRECATED PIP_NO_PYTHON_VERSION_WARNING PIP_KEYRING_PROVIDER PIP_EXISTS_ACTION PIP_IGNORE_REQUIRES_PYTHON PIP_LOG PIP_TRUSTED_HOST PIP_CERT PIP_CLIENT_CERT PIP_PROXY PIP_TIMEOUT PIP_DEFAULT_TIMEOUT PIP_RETRIES
export PIP_CONFIG_FILE=/dev/null
python -I -m venv --clear .venv
. .venv/bin/activate
python -m pip install --isolated --disable-pip-version-check --no-deps --requirement requirements-docs.lock
python scripts/verify_docs_environment.py
python -m pip check
SITE_PUBLICATION_PROTOCOL_ROOT=/path/to/site-checkout-at-3ae5d1e60c65e7a8ebf5f9af0436044484e42983
python -I "$SITE_PUBLICATION_PROTOCOL_ROOT/scripts/publication_contract.py" \
  --source-root . \
  --catalog docs/publication-catalog.json
python scripts/generate_repository_preview.py
python scripts/verify-repository-structure.py --check
python scripts/validate_translations.py
python scripts/generate-doc-assets.py
python scripts/generate_docs_build_info.py \
  --commit "$(git rev-parse HEAD)" \
  --repository TakashiSasaki/templates
python -m mkdocs build --strict --clean
```

The Site checkout used for `SITE_PUBLICATION_PROTOCOL_ROOT` must identify exactly the reviewed full SHA above. A mutable branch checkout is not equivalent evidence. The local metadata command uses the checked-out Policy commit and records `run_id` and `run_number` as `0`, distinguishing a local build from a GitHub Actions run while preserving the same `docs/build-info.json` shape and footer behavior. The workflow calls the same generator with the actual repository and run identifiers.

## Deployment ownership

GitHub Pages deployment for `TakashiSasaki/templates` belongs exclusively to the independent `site` authority. It must not be introduced into `policy` as an incidental documentation, migration, release, or toolchain change. Publishing policy documentation through the repository site requires the Site-owned publication integration and source lock; the `policy` workflow remains build-only.

A future change to `.github/workflows/pages.yml` must continue to reject all of the following:

- `actions/upload-pages-artifact`;
- `actions/configure-pages`;
- `actions/deploy-pages`;
- `pages: write`;
- `id-token: write`;
- a `github-pages` environment;
- a deployment job;
- `workflow_call` or `workflow_dispatch` as a publication path.

The Site publication protocol checkout must remain pinned to a reviewed full Site commit SHA. Updating that pin is a cross-authority protocol-consumption change and requires review of the exact Site revision; it must not silently follow `site`, another branch, a tag, or a pull-request merge ref.

## Build verification

The documentation build is successful only when all of the following pass:

- clean creation of the isolated documentation environment;
- installation from the complete arbitrary-exact dependency lock with dependency resolution disabled;
- exact installed-distribution verification and `pip check`;
- generic publication catalog validation by the reviewed full-SHA Site-owned protocol;
- Policy-owned publication declaration and documentation-boundary regression tests;
- repository preview generation;
- documented-tree verification;
- translation validation;
- documentation asset generation;
- shared build metadata generation;
- `mkdocs build --strict --clean`;
- regression tests confirming that no Pages deployment route exists.

A successful MkDocs build does not mean that documentation has been published.


Authority-local stacked pull requests using `policy-*` base branches receive the same read-only documentation build as root PRs targeting `policy`. Push-triggered documentation builds remain restricted to `policy`; this does not introduce a Site deployment route or join authority histories.