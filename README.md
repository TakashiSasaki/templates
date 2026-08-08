# Policy toolkit

This orphan branch is the development source for application-type-independent coding-agent operating policy in `TakashiSasaki/templates`. Its history is intentionally unrelated to the repository's `skill`, `site`, and `webapp` branches.

The toolkit compiles shared and repository-specific operating rules into reproducible agent instructions. It governs how coding and general-purpose agents investigate, change, validate, and report work; it does not define the architecture or product requirements of Web applications, command-line tools, libraries, services, or other artifact categories.

The Python package and command are named `agent-policy`.

Repository-maintainer operating authority for this branch is declared by `.agent-policy.yml` and the files under `repository-policy/`. Generated `AGENTS.md` and `.github/REVIEW_GUIDELINES.md` are projections of that authority. Other maintained documents may define toolkit contracts, release/readiness states, or explain the current implementation, but this README does not independently override the canonical operating rules.

## Commands

```bash
agent-policy init
agent-policy validate
agent-policy render
agent-policy check
```

A product repository keeps a single semantic configuration entry point, `.agent-policy.yml`. Project-specific policy text remains in files referenced by that manifest. Generated agent instructions and `.agent-policy.lock` are committed so cloud agents and historical checkouts remain self-contained.

## Bootstrap skill

The repository-maintainer rule governing stable release identity and promotion mechanics is `repository-policy/release-trust.md`; the following describes the current bootstrap implementation of that rule.

The onboarding trust seed is maintained at `skills/bootstrap-agent-policy/` in this branch. Its manifest pins one reviewed full commit SHA from `TakashiSasaki/templates`; it does not execute the mutable `policy` branch tip.

`release/toolchain.json` records the stable toolchain pin and contract versions. The bootstrap manifest carries exactly the same repository and revision. Stable-pin movement uses a reviewed candidate commit followed by a separate promotion change, so no commit attempts to contain its own SHA.

Install the bootstrap skill from a reviewed checkout:

```bash
python skills/bootstrap-agent-policy/scripts/install.py \
  /path/to/agent-skills/bootstrap-agent-policy
```

The bootstrap script may inspect, initialize, or prepare and preview adoption. It deliberately exposes no adoption-finalization route.

## Development

The canonical repository-maintainer requirement to run appropriate validation is `repository-policy/maintainer-validation.md`. The sequence below documents the current reproducible Policy CI baseline and its implementation-specific trust boundary; it is evidence and operational guidance rather than a second policy authority.

The validated CI baseline is CPython 3.12.13 on `ubuntu-24.04`. Remove externally supplied Python and pip inputs before the first Python invocation, disable pip configuration files, create the virtual environment with an isolated bootstrap interpreter, and install only the reviewed lock graph:

```bash
unset PYTHONHOME PYTHONPATH PYTHONUSERBASE PIP_REQUIREMENT PIP_CONSTRAINT PIP_BUILD_CONSTRAINT PIP_REQUIRE_HASHES PIP_DRY_RUN PIP_NO_BINARY PIP_ONLY_BINARY PIP_PLATFORM PIP_PYTHON_VERSION PIP_IMPLEMENTATION PIP_ABI PIP_UPLOADED_PRIOR_TO PIP_INDEX_URL PIP_EXTRA_INDEX_URL PIP_NO_INDEX PIP_FIND_LINKS PIP_TARGET PIP_PREFIX PIP_ROOT PIP_USER PIP_PYTHON PIP_CACHE_DIR PIP_NO_CACHE_DIR PIP_QUIET PIP_EDITABLE PIP_GROUP PIP_REQUIREMENTS_FROM_SCRIPT PIP_REPORT PIP_CONFIG_SETTINGS PIP_IGNORE_REQUIRES_PYTHON PIP_LOG
export PIP_CONFIG_FILE=/dev/null
python -I -m venv --clear .venv
. .venv/bin/activate
python -m pip install --disable-pip-version-check --no-deps --requirement requirements-ci.lock
python -m pip install --disable-pip-version-check --no-deps --no-build-isolation -e .
python scripts/verify_ci_environment.py
python -m pip check
python scripts/verify-release-state.py
python -m ruff check src tests scripts skills/bootstrap-agent-policy/scripts
python -m pytest
python -m compileall -q src scripts skills/bootstrap-agent-policy/scripts
agent-policy --help
```

`requirements-ci.txt` records the reviewed direct test and build inputs. `requirements-ci.lock` records the complete dependency graph for the selected CI baseline. Both use arbitrary exact equality (`===`), so an unrequested local version such as `4.26.0+corp` does not satisfy a reviewed public version such as `4.26.0`. The local project is installed separately with dependency resolution and build isolation disabled. `scripts/verify_ci_environment.py` requires the installed distribution set to equal the lock plus the editable `takashisasaki-agent-policy` project, excluding only the virtual environment's bootstrap `pip`. It also requires the installed project's `direct_url.json` to identify this repository root with `dir_info.editable` set to true, so a same-name, same-version wheel cannot stand in for the checked-out source.

The ordering is part of the implemented CI trust boundary. Policy CI neutralizes `PYTHONHOME`, `PIP_PYTHON`, `PIP_CACHE_DIR`, `PIP_NO_CACHE_DIR`, `PIP_QUIET`, and `PIP_LOG` in the job environment before `actions/setup-python` performs its cache lookup, so the action cannot redirect the pre-venv Python or pip invocation, select an external cache path, disable the cache command, suppress the cache-path output it relies on, or redirect pip's verbose log output. Isolated mode is then used before environment creation so user-site packages, `PYTHONUSERBASE`, `sitecustomize`, `usercustomize`, and other Python environment inputs cannot affect `venv` bootstrap. The existing `.venv` is cleared so packages from an earlier lock cannot remain. Pip configuration and requirement, runtime-constraint, build-constraint, hash-enforcement, dry-run, source-format, binary-only artifact-selection, wheel-compatibility, upload-time, package-source, installation-destination, interpreter-override, cache-location, cache-disable, quiet, editable, dependency-group, installation-report, build-backend configuration, Requires-Python compatibility, log-path, and script-metadata inputs are removed so additional packages, build rules, external hash requirements, skipped installation, forced sdist builds, foreign compatibility tags, time-filtered artifacts, alternate indexes or archive locations, writes outside the isolated environment, an external interpreter, backend-specific build settings, bypassed Requires-Python checks, altered cache behavior, or redirected pip log output cannot be injected into the validation paths. The same pip inputs remain absent while the stable-release verifier creates and populates its independent probe environment. The installed-set and editable-source comparisons run before `pip check`, release verification, linting, tests, compilation, and command smoke testing.

The lock fixes exact distribution version strings. It does not provide byte-for-byte artifact reproducibility or cryptographic index-origin reproducibility because hashes and source URLs are not recorded. Hash enforcement and explicit repository-origin enforcement are separate trust-boundary changes. Dependency-input and lock changes are made through the repository's reviewed change process.

The documentation build uses the same clean-runner boundary for its independent arbitrary-exact dependency lock, installed-distribution verification, strict MkDocs build, and full-SHA action pins. Its current deployment exclusion implements `repository-policy/documentation-boundary.md`: the `policy` workflow contains no GitHub Pages deployment route and has only `contents: read`, while Pages deployment belongs to the unrelated `site` branch. See `docs/documentation-publication.md` for the reproducible local sequence and deployment exclusion contract.

## Branch status

The authoritative development location is `TakashiSasaki/templates` branch `policy`.

The maintained branch provides:

- branch-appropriate policy CI;
- the application-type-independent policy boundary;
- one canonical shared-policy authority model with explicit repository-local exceptions;
- executable and generated toolchain identity rooted at `TakashiSasaki/templates`;
- the integrated bootstrap trust seed under `skills/bootstrap-agent-policy/`;
- a schema-validated stable release descriptor and full-SHA synchronization verifier;
- context-aware coding and review rendering, including the GitHub review JSON adapter;
- a `policy`-scoped strict documentation build with no Pages artifact upload, Pages write authority, or deployment job; and
- the reviewed toolkit-completion contract and audit record in `docs/policy-readiness.md` and `docs/policy-readiness-audit.md`.

Core capabilities or successful individual workflows do not, by themselves, declare the toolkit complete; completion requires the cross-cutting audit and release-alignment sequence defined by the readiness contract.

## Trust model

Repository-maintainer trust-model operating requirements are canonical in `repository-policy/release-trust.md` and `repository-policy/toolchain-safety.md`; this section summarizes the current implementation and verification surface.

Mutable branches are not used as executable toolchain references. The stable release descriptor, bootstrap metadata, product manifests, adoption state, generated lock files, and generated workflows identify the toolchain using a full Git commit SHA. `scripts/verify-release-state.py` checks the branch-local release contract, and Policy CI verifies that the stable revision is a strict ancestor of the reviewed `policy` source history.

Bootstrap pin, release descriptor, route, script, or safety-constraint changes are treated as trust-anchor changes by the maintained contract and review process.
