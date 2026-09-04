# Policy toolkit

Policy turns shared coding-agent rules plus repository-specific policy into reproducible agent instructions for a product repository. It governs how coding and general-purpose agents investigate, change, validate, review, and report work; it does not define the architecture or product requirements of Web applications, command-line tools, libraries, services, or other artifact categories, and it does not choose the product stack.

## Start here: adopt Policy in a product repository

Prerequisites are Git on `PATH`, a target Git repository, and supported CPython 3.11 through 3.14. Install the single `agent-policy` skill using the reviewed immutable installer:

```bash
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/f4457c90854db34c3ce8e1c381f67a4d7d5ea523/scripts/install_agent_policy_skill.py', timeout=30).read())" /path/to/agent-skills/agent-policy
```

From the installed skill directory, inspect an unmanaged product repository before changing it:

```bash
python scripts/bootstrap.py \
  --repository /path/to/product-repository
```

Bootstrap is a dry run by default. Review the reported state and plan before applying anything.

- `unmanaged-empty`: rerun the same command with `--apply` to complete fresh adoption.
- `unmanaged-existing`: follow the migration flow in [Getting started](docs/getting-started.md); bootstrap can prepare and preview the migration but does not finalize it.
- `managed`: stop using bootstrap for ordinary operation and use the repository-pinned runner below.
- `inconsistent`: repair the reported partial or unsafe state before adoption.

For a managed repository, the normal verification and regeneration loop is:

```bash
python scripts/run.py --repository /path/to/product-repository validate
python scripts/run.py --repository /path/to/product-repository render
python scripts/run.py --repository /path/to/product-repository check
```

`.agent-policy.yml` is the product repository's human-edited semantic configuration entry point. `.agent-policy.lock`, generated agent instructions, and generated validation skills are managed outputs. Start with [Getting started](docs/getting-started.md) for profile selection, migration adoption, and the exact unmanaged-to-managed workflow; use [Managed repository operation](docs/managed-operation.md) after adoption.

## Authority and branch role

This orphan branch is the development source for application-type-independent coding-agent operating policy in `TakashiSasaki/templates`. Its history is intentionally unrelated to the repository's `site` and `composition` authority histories. Agent Skill and Web application artifact semantics are owned by `composition`, not by separate provider branches.

The Python package and command are named `agent-policy`.

Repository-maintainer operating authority for this branch is declared by `.agent-policy.yml` and the files under `repository-policy/`. Generated `AGENTS.md` and `.review-authority/review-policy.md` are context projections of that authority; `.agents/skills/pr-review/` is the generated provider-neutral review procedure. Other maintained documents may define toolkit contracts, release/readiness states, or explain the current implementation, but this README does not independently override the canonical operating rules.

Policy and Composition may coexist in one consumer repository without a direct runtime dependency. Policy owns `.agent-policy.yml`, `.agent-policy.lock`, and `.agent-policy/**`; Composition owns `.template-composition/**`. The canonical cross-authority boundary, including ordinary-path ownership handoffs such as a consumer-owned `AGENTS.md`, is the Site-owned [Policy–Composition coexistence contract](https://templates.moukaeritai.work/coexistence/).

## Commands

The public onboarding operation is adoption. The hidden `init` command is an implementation primitive used for fresh adoption and is not a separate user-facing onboarding model.

```bash
agent-policy adopt inspect
agent-policy adopt prepare
agent-policy validate
agent-policy render
agent-policy check
```

A product repository keeps a single semantic configuration entry point, `.agent-policy.yml`. Project-specific policy text remains in files referenced by that manifest. Generated agent instructions and `.agent-policy.lock` are committed so cloud agents and historical checkouts remain self-contained.

## Single agent-policy skill

`skills/agent-policy/` is the single installable repository-facing skill. It handles both initial adoption and normal operation; there is no separate bootstrap skill.

For an unmanaged repository, `scripts/bootstrap.py` inspects repository state and chooses the fresh or migration adoption strategy. Fresh adoption may complete directly to managed state. Migration adoption may prepare and preview only; bootstrap never finalizes migration.

For a managed repository, `scripts/run.py` reads `.agent-policy.lock` and runs the repository-pinned full-SHA toolchain. Malformed, mutable, or unsupported lock pins fail closed rather than falling back to the skill default.

The bare `agent-policy ...` examples above describe the canonical toolchain CLI. Normal consumers run `python scripts/bootstrap.py ...` from the installed skill directory for unmanaged repositories and `python scripts/run.py ...` for managed operations. Installing the skill does not by itself install an `agent-policy` executable globally on `PATH`.

### Immutable one-line installation

Install the reviewed skill with an installer script whose URL is itself pinned to a full commit SHA:

```bash
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/TakashiSasaki/templates/f4457c90854db34c3ce8e1c381f67a4d7d5ea523/scripts/install_agent_policy_skill.py', timeout=30).read())" /path/to/agent-skills/agent-policy
```

For an existing installation, append `--replace`; replacement is accepted only when the destination is already identified as this skill.

The distribution has three distinct immutable roles:

- **installer script revision** `f4457c90854db34c3ce8e1c381f67a4d7d5ea523` identifies the remotely executed stdlib-only bootstrap script;
- **skill source revision** `344aaf0b140e3c066363297012bb866efbc106e4` identifies the `skills/agent-policy/` tree that the installer downloads and atomically installs; and
- the skill's **stable runtime revision** remains the full SHA in `skills/agent-policy/runtime-manifest.json`, independently selected for CLI execution.

`release/skill-installer.json` records the first two identities. The one-line command never executes the mutable `policy` branch or a tag.

A reviewed checkout is also available as a repository-development installation path:

```bash
python skills/agent-policy/scripts/install.py \
  /path/to/agent-skills/agent-policy
```

That command installs the skill tree from the checkout being reviewed. It is not necessarily byte-for-byte identical to the currently published remote distribution unless the checkout matches the skill-source revision in `release/skill-installer.json`. Use the published remote command when reproducing the published distribution is the goal.

`skills/agent-policy/runtime-manifest.json` records the stable default full SHA and the SHA-256 of that revision's `requirements-runtime.lock`. `release/toolchain.json` carries the same stable toolchain pin. Stable-pin movement uses a reviewed candidate commit followed by a separate promotion change, so no commit attempts to contain its own SHA.

### Persistent runtime cache

The skill does not reinstall the toolchain on every use. It reuses a validated persistent runtime identified by:

- toolchain repository and full commit SHA;
- SHA-256 of `requirements-runtime.lock`;
- Python major/minor version; and
- platform plus machine architecture.

The default cache root is the platform cache directory under `agent-policy/runtime-v1`; `AGENT_POLICY_RUNTIME_CACHE` may override it for controlled environments and tests.

A valid cache hit requires no network access. A cache miss downloads the runtime lock from the exact full SHA, creates an isolated virtual environment in a staging directory, installs the exact runtime distribution set with dependency resolution disabled, installs the same pinned `agent-policy` project with dependencies disabled, runs `pip check`, verifies the installed distribution set, and writes the cache marker only after validation succeeds. The staged runtime is then switched into place atomically.

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
python scripts/verify_skill_installer_release.py
python -m ruff check src tests scripts skills/agent-policy/scripts
python -m pytest
python -m compileall -q src scripts skills/agent-policy/scripts
agent-policy --help
```

`requirements-ci.txt` records the reviewed direct test and build inputs. `requirements-ci.lock` records the complete dependency graph for the selected CI baseline. Both use arbitrary exact equality (`===`), so an unrequested local version such as `4.26.0+corp` does not satisfy a reviewed public version such as `4.26.0`. The local project is installed separately with dependency resolution and build isolation disabled. `scripts/verify_ci_environment.py` requires the installed distribution set to equal the lock plus the editable `takashisasaki-agent-policy` project, excluding only the virtual environment's bootstrap `pip`. It also requires the installed project's `direct_url.json` to identify this repository root with `dir_info.editable` set to true, so a same-name, same-version wheel cannot stand in for the checked-out source.

Consumer-runtime validation has a separate, narrower contract. `requirements-runtime.lock` records the exact runtime-only distribution set, excluding development, test, and build-only packages and excluding the local `takashisasaki-agent-policy` distribution itself. `scripts/smoke_test_runtime_distribution.py` creates a fresh virtual environment, removes inherited Python and pip package-selection inputs, installs every locked runtime distribution with `--no-deps`, installs the local project separately with `--no-deps`, runs `pip check`, verifies the installed set, and invokes `agent-policy --help`. `scripts/verify_runtime_environment.py` requires that dedicated environment to equal `requirements-runtime.lock` plus the local project, excluding only virtual-environment bootstrap distributions (`pip`, `setuptools`, and `wheel`). `.github/workflows/runtime-distribution.yml` exercises this contract on Ubuntu and Windows across Python 3.11 through 3.14.

The dependency locks fix exact distribution version strings. They do not provide byte-for-byte artifact reproducibility or cryptographic index-origin reproducibility because hashes and source URLs are not recorded. Hash enforcement and explicit repository-origin enforcement are separate trust-boundary changes. Dependency-input and lock changes are made through the repository's reviewed change process.

The documentation build uses the same clean-runner boundary for its independent arbitrary-exact dependency lock, installed-distribution verification, strict MkDocs build, and full-SHA action pins. Its current deployment exclusion implements `repository-policy/documentation-boundary.md`: the `policy` workflow contains no GitHub Pages deployment route and has only `contents: read`, while Pages deployment belongs to the independent `site` authority. See `docs/documentation-publication.md` for the reproducible local sequence and deployment exclusion contract.

## Branch status

The authoritative development location is `TakashiSasaki/templates` branch `policy`.

The maintained branch provides:

- branch-appropriate policy CI;
- the application-type-independent policy boundary;
- one canonical shared-policy authority model with explicit repository-local exceptions;
- executable and generated toolchain identity rooted at `TakashiSasaki/templates`;
- the single cached `agent-policy` skill under `skills/agent-policy/`;
- an immutable full-SHA remote installer publication descriptor;
- a schema-validated stable release descriptor and full-SHA synchronization verifier;
- context-aware coding and review semantic rendering plus the provider-neutral `pr-review` procedure;
- a `policy`-scoped strict documentation build with no Pages artifact upload, Pages write authority, or deployment job; and
- the reviewed toolkit-completion contract and audit record in `docs/policy-readiness.md` and `docs/policy-readiness-audit.md`.

Core capabilities or successful individual workflows do not, by themselves, declare the toolkit complete; completion requires the cross-cutting audit and release-alignment sequence defined by the readiness contract.

## Trust model

Repository-maintainer trust-model operating requirements are canonical in `repository-policy/release-trust.md` and `repository-policy/toolchain-safety.md`; this section summarizes the current implementation and verification surface.

Mutable branches are not used as executable toolchain references. The stable release descriptor, skill runtime manifest, skill-installer publication descriptor, product manifests, adoption state, generated lock files, and generated workflows identify executable or distributed components using full Git commit SHAs. `scripts/verify-release-state.py` checks runtime synchronization, while `scripts/verify_skill_installer_release.py` verifies that the pinned installer revision embeds the published skill source revision and that the required skill subtree exists at that revision. Policy CI also verifies ancestry against the reviewed `policy` source history.

Runtime-manifest pin, release descriptor, installer publication descriptor, route, script, cache-identity, or safety-constraint changes are treated as trust-anchor changes by the maintained contract and review process.
