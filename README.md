# Policy toolkit

This orphan branch is the development source for application-type-independent coding-agent operating policy in `TakashiSasaki/templates`. Its history is intentionally unrelated to the repository's `main`, `site`, and `webapp` branches.

The toolkit compiles shared and repository-specific operating rules into reproducible agent instructions. It governs how coding and general-purpose agents investigate, change, validate, and report work; it does not define the architecture or product requirements of Web applications, command-line tools, libraries, services, or other artifact categories.

The existing Python package and command remain named `agent-policy` for compatibility during repository migration.

## Commands

```bash
agent-policy init
agent-policy validate
agent-policy render
agent-policy check
```

A product repository keeps a single semantic configuration entry point, `.agent-policy.yml`. Project-specific policy text remains in files referenced by that manifest. Generated agent instructions and `.agent-policy.lock` are committed so cloud agents and historical checkouts remain self-contained.

## Bootstrap skill

The onboarding trust seed is maintained at `skills/bootstrap-agent-policy/` in this branch. Its manifest pins one reviewed full commit SHA from `TakashiSasaki/templates`; it does not execute the mutable `policy` branch tip.

`release/toolchain.json` records the stable toolchain pin and contract versions. The bootstrap manifest must carry exactly the same repository and revision. Stable-pin movement uses a reviewed candidate commit followed by a separate promotion change, so no commit attempts to contain its own SHA.

Install the bootstrap skill from a reviewed checkout:

```bash
python skills/bootstrap-agent-policy/scripts/install.py \
  /path/to/agent-skills/bootstrap-agent-policy
```

The bootstrap script may inspect, initialize, or prepare and preview adoption. It deliberately exposes no adoption-finalization route.

## Development

The validated candidate-CI baseline is CPython 3.12.13 on `ubuntu-24.04`. Remove externally supplied Python and pip inputs before the first Python invocation, disable pip configuration files, create the virtual environment with an isolated bootstrap interpreter, and install only the reviewed lock graph:

```bash
unset PYTHONHOME PYTHONPATH PYTHONSAFEPATH PYTHONPLATLIBDIR PYTHONHASHSEED PYTHONUTF8 PYTHONINTMAXSTRDIGITS PYTHONMALLOC PYTHONIOENCODING PYTHONTRACEMALLOC PYTHONINSPECT PYTHONUSERBASE PIP_REQUIREMENT PIP_CONSTRAINT PIP_BUILD_CONSTRAINT PIP_REQUIRE_HASHES PIP_DRY_RUN PIP_NO_BINARY PIP_ONLY_BINARY PIP_PLATFORM PIP_PYTHON_VERSION PIP_IMPLEMENTATION PIP_ABI PIP_UPLOADED_PRIOR_TO PIP_INDEX_URL PIP_EXTRA_INDEX_URL PIP_NO_INDEX PIP_FIND_LINKS PIP_TARGET PIP_PREFIX PIP_ROOT PIP_USER PIP_PYTHON PIP_CACHE_DIR PIP_NO_CACHE_DIR PIP_QUIET PIP_PROGRESS_BAR PIP_EDITABLE PIP_GROUP PIP_REQUIREMENTS_FROM_SCRIPT PIP_REPORT PIP_CONFIG_SETTINGS PIP_USE_PEP517 PIP_COMPILE PIP_ISOLATED PIP_USE_FEATURE PIP_VERBOSE PIP_DEBUG PIP_NO_INPUT PIP_DISABLE_PIP_VERSION_CHECK PIP_NO_COLOR PIP_REQUIRE_VIRTUALENV PIP_USE_DEPRECATED PIP_NO_PYTHON_VERSION_WARNING PIP_KEYRING_PROVIDER PIP_EXISTS_ACTION PIP_IGNORE_REQUIRES_PYTHON PIP_LOG PIP_TRUSTED_HOST PIP_CERT PIP_CLIENT_CERT PIP_PROXY PIP_TIMEOUT PIP_DEFAULT_TIMEOUT PIP_RETRIES
export PIP_CONFIG_FILE=/dev/null
python -I -m venv --clear .venv
. .venv/bin/activate
python -m pip install --isolated --disable-pip-version-check --no-deps --requirement requirements-ci.lock
python -m pip install --isolated --disable-pip-version-check --no-deps --no-build-isolation -e .
python scripts/verify_ci_environment.py
python -m pip check
python scripts/verify-release-state.py
python -m ruff check src tests scripts skills/bootstrap-agent-policy/scripts
python -m pytest
python -m compileall -q src scripts skills/bootstrap-agent-policy/scripts
agent-policy --help
```

`requirements-ci.txt` records the reviewed direct test and build inputs. `requirements-ci.lock` records the complete dependency graph for the selected CI baseline. Both use arbitrary exact equality (`===`), so an unrequested local version such as `4.26.0+corp` does not satisfy a reviewed public version such as `4.26.0`. The local project is installed separately with dependency resolution and build isolation disabled. `scripts/verify_ci_environment.py` requires the installed distribution set to equal the lock plus the editable `takashisasaki-agent-policy` project, excluding only the virtual environment's bootstrap `pip`. It also requires the installed project's `direct_url.json` to identify this repository root with `dir_info.editable` set to true, so a same-name, same-version wheel cannot stand in for the checked-out source.

The documentation build uses the same runner, Python patch, action revisions, startup-input boundary, isolated virtual-environment creation, and pip-input boundary, but keeps its own reviewed dependency input and lock because documentation packages are not candidate-CI dependencies:

```bash
rm -rf .venv
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

`requirements-docs.txt` records the reviewed direct documentation inputs, and `requirements-docs.lock` records the complete arbitrary-exact documentation graph. `scripts/verify_docs_environment.py` rejects missing, unexpected, or version-mismatched distributions before repository preview generation or the strict MkDocs build. This environment is a branch-maintainer documentation toolchain, not a product runtime or deployment choice.

The ordering is part of the trust boundary. Policy CI and Policy documentation neutralize `PYTHONHOME`, `PYTHONPATH`, `PYTHONSAFEPATH`, `PYTHONPLATLIBDIR`, `PYTHONHASHSEED`, `PYTHONUTF8`, `PYTHONINTMAXSTRDIGITS`, `PYTHONMALLOC`, `PYTHONIOENCODING`, `PYTHONTRACEMALLOC`, and `PYTHONINSPECT` before environment creation, disable user-site loading, and use isolated interpreter mode so externally supplied modules, `sitecustomize`, `usercustomize`, malformed startup settings, or interactive inspection cannot affect bootstrap. Job-wide neutralization of pip interpreter, cache, quiet, progress, log, keyring, exists-action, build-backend, isolated-mode, feature, verbosity, interaction, color, virtual-environment, deprecated-option, warning, timeout, and retry inputs protects the cache-enabled `actions/setup-python` step. The existing `.venv` is cleared so packages from an earlier lock cannot remain.

Candidate, documentation, and stable-release dependency installs remove requirement, constraint, build-constraint, hash, dry-run, source-format, binary-only, wheel-compatibility, upload-time, package-source, installation-destination, interpreter, cache, quiet, progress-bar, editable, dependency-group, report, build-backend, feature, interaction, Requires-Python, keyring, logging, transport, certificate, proxy, timeout, retry, and script-metadata inputs, and use pip's `--isolated` mode. Candidate CI then verifies the complete installed set and editable source; the documentation build verifies the complete documentation set; and the stable-release verifier creates an independent probe environment from `release/verifier-requirements.lock`, installs that arbitrary-exact graph with `--isolated --no-deps --only-binary=:all:`, and runs `pip check` before executing the pinned tree.

These locks fix exact distribution version strings. They do not provide byte-for-byte artifact reproducibility or cryptographic index-origin reproducibility because hashes and source URLs are not recorded. Hash enforcement and explicit repository-origin enforcement are separate trust-boundary changes. Update a direct input, its complete lock, its verifier expectations, and the applicable workflow and documentation together through a reviewed dependency-resolution change. Stable-probe lock changes additionally follow the candidate-and-promotion lifecycle described in `docs/release-lifecycle.md`.

## Branch and migration status

The authoritative development location is `TakashiSasaki/templates` branch `policy`. The branch was imported from `TakashiSasaki/agent-policy` while preserving the non-workflow source history; see `docs/migration-from-agent-policy.md` for the exact source revision and import boundary.

Completed migration work includes:

- branch-appropriate policy CI;
- the application-type-independent policy boundary;
- The former built-in `web-application` profile and its application-architecture rules were removed;
- executable toolchain identity migration to `TakashiSasaki/templates`;
- consolidation of the bootstrap trust seed into `skills/bootstrap-agent-policy/`;
- a schema-validated stable release descriptor and full-SHA synchronization verifier;
- restoration of a `policy`-scoped strict documentation build with retained but disabled GitHub Pages upload and deployment steps.

Consumer pin updates, any later decision to enable Pages deployment, Pages settings and custom-domain cutover, and deprecation and archival of the former repository remain separate follow-up changes. See `docs/documentation-publication.md` for the disabled deployment boundary.

## Trust model

Mutable branches are not used as executable toolchain references. The stable release descriptor, bootstrap metadata, product manifests, adoption state, generated lock files, and generated workflows identify the toolchain using a full Git commit SHA. `scripts/verify-release-state.py` checks the branch-local release contract, and Policy CI verifies that the stable revision is a strict ancestor of the reviewed `policy` source history.

Bootstrap pin, release descriptor, route, script, or safety-constraint changes are reviewed as trust-anchor changes even though the bootstrap skill shares the `policy` history.
