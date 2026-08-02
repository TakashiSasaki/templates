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

The validated CI baseline is CPython 3.12.13 on `ubuntu-24.04`. Remove externally supplied Python and requirement-bearing pip inputs before the first Python invocation, disable pip configuration files, create the virtual environment with an isolated bootstrap interpreter, and install only the reviewed lock graph:

```bash
unset PYTHONPATH PYTHONUSERBASE PIP_REQUIREMENT PIP_CONSTRAINT PIP_BUILD_CONSTRAINT PIP_PYTHON PIP_EDITABLE PIP_GROUP PIP_REQUIREMENTS_FROM_SCRIPT
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

The ordering is part of the trust boundary. Policy CI neutralizes `PIP_PYTHON` in the job environment before `actions/setup-python` performs its cache lookup, so the action cannot redirect that pre-venv pip invocation to an external interpreter. Isolated mode is then used before environment creation so user-site packages, `PYTHONUSERBASE`, `sitecustomize`, `usercustomize`, and other Python environment inputs cannot affect `venv` bootstrap. The existing `.venv` is cleared so packages from an earlier lock cannot remain. Pip configuration and requirement, runtime-constraint, build-constraint, interpreter-override, editable, dependency-group, and script-metadata inputs are removed so additional packages, build rules, or an external interpreter cannot be injected. The same pip inputs remain absent while the stable-release verifier creates and populates its independent probe environment. The installed-set and editable-source comparisons run before `pip check`, release verification, linting, tests, compilation, and command smoke testing.

The lock fixes exact distribution version strings. It does not provide byte-for-byte artifact reproducibility or index-origin reproducibility because hashes and source URLs are not recorded. Hash enforcement and repository-origin enforcement are separate trust-boundary changes. Update dependency inputs and the lock only through a reviewed dependency-resolution change.

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
