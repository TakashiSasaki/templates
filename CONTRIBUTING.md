# Contributing to the Skill template product

## Repository boundary

The `skill` branch root is the source repository for the template product. It is not an installable Skill directory.

The consumer-facing artifact is `template/`. Copy its contents into a new Skill root:

```sh
mkdir -p /path/to/new-skill
cp -a template/. /path/to/new-skill/
```

Do not add `SKILL.md`, runtime/interface contracts, resource placeholders, or implementation directories back to the branch root. Consumer-facing Skill content is maintained under `template/` only.

Before changing a path, classify it as:

- source-only maintenance material;
- distribution-owned content under `template/`; or
- a validator projected byte-for-byte from `.github/scripts/` to `template/.github/scripts/`.

Read `AGENTS.md`, `README.md`, `maintainer/README.md`, `docs/architecture/distribution-boundary.md`, and `distribution-manifest.json` before changing the artifact boundary.

## Profile invariants

The copyable artifact is one profile-aware scaffold, not a directory per profile.

- `template-scaffold` is valid only for the uncustomized template.
- `instruction-only` is the sole exclusive concrete profile.
- `knowledge-augmented`, `asset-driven`, `script-assisted`, `packaged-cli`, `mcp-enabled`, `browser-interface`, and `headless-service` are selectively composable.
- Combined profiles retain the union of their required contracts.
- A concrete Skill removes unsupported optional contracts and resources after copying.

Do not impose a runtime, package manager, CLI, MCP adapter, browser surface, service, or deployment topology on a Skill that does not need it.

## Distribution changes

For distribution-owned content:

1. edit the canonical file under `template/`;
2. keep the file listed under `distribution_owned_files` in `distribution-manifest.json`;
3. ensure every required relative reference resolves within `template/`; and
4. validate from the copied Skill root, not from the source root.

For a projected validator:

1. edit the source implementation under `.github/scripts/`;
2. update its declared projection under `template/.github/scripts/` to identical bytes and mode;
3. run distribution validation; and
4. run the applicable positive and negative concrete-Skill tests.

For source-only content, do not add a copy under `template/` merely to make the source and distribution trees look similar.

`distribution-manifest.json` must reject missing files, undeclared files, symbolic links, maintainer-only leakage, path traversal, content transformation, top-level shape drift, and projected-validator byte or mode drift.

## Profile and interface changes

Use the consumer documents under `template/` as the sources of truth:

- workflow, resources, outputs, safety, and selected profiles: `template/SKILL.md`;
- profile selection and retention: `template/docs/skill-profiles.md`;
- contract ownership: `template/docs/profile-contract-map.md`;
- runtime, commands, dependencies, protocol selection, process lifecycle, and deployment topology: `template/RUNTIME.md`;
- preferred public route and fallback: `template/INTERFACES.md`;
- packaged CLI caller behavior: `template/CLI_INTERFACE.md`;
- MCP caller behavior: `template/MCP_INTERFACE.md`;
- browser-visible behavior: `template/WEB_INTERFACE.md`.

Profile changes require synchronized contract templates, validators, positive fixtures, combined fixtures, negative fixtures, consumer documentation, and publication sources. Keep adapters thin only when multiple interfaces actually exist. Keep lifecycle ownership outside domain operations and caller protocols.

## Validation

Run the source/distribution checks:

```sh
ruby .github/scripts/test-distribution-boundary.rb
ruby .github/scripts/test-skill-distribution.rb
ruby .github/scripts/validate-skill-distribution.rb
ruby .github/scripts/test-restructure-completion.rb
```

Run the supported profile-aware validation entry point:

```sh
cd template
ruby .github/scripts/validate-profile-contracts.rb
```

Run complete repository validation against the copyable Skill root:

```sh
ruby .github/scripts/validate-skill-repository.rb template
ruby template/.github/scripts/test-template-baseline.rb
```

Run clean-room adoption and installation:

```sh
ruby .github/scripts/test-copyable-template-consumption.rb
```

The explicit-root validator resolves every contract and operational resource relative to the supplied Skill root rather than the caller's working directory. It clears inherited Git directory and index overrides before discovering the target context. A flattened archive uses a dedicated temporary empty index only for metadata checks and must not modify the target or a caller-owned alternate index.

## Fixture baseline

Reduced fixtures under `.github/fixtures/profiles/` cover instruction, knowledge, assets, private helpers, optional runtime records, packaged CLI, MCP, browser, headless service, combined resource profiles, combined CLI/MCP behavior, systemd service management, and intentionally unsupported combinations.

The executable application fixtures select concrete runtimes only to establish their specific claims. They do not make Ruby, one package manager, one transport, or one deployment topology mandatory for the language-neutral template.

The clean-room harness copies `template/.` into a path containing spaces and Japanese characters, verifies the copied inventory and modes, injects source-owned regression engines only into that temporary test copy, and exercises instruction-only, script-assisted, clone, submodule, flattened archive, vendoring, non-mutating consumption, and path safety. The canonical `template/` tree must remain unchanged.

This fixture matrix is the stable baseline for the current profile model. A new protocol era, transport, trust boundary, deployment topology, persistence layer, service manager, distribution service, or release mechanism requires an explicit contract and proportionate executable evidence.

## Documentation publication compatibility

The `skill` branch owns stable publication document IDs and canonical source paths in `docs/publication-catalog.json`. Consumer documents resolve below `template/`; the source-product overview remains root `README.md`.

Pull requests that change `README.md`, `docs/**`, `template/**`, or the compatibility workflow are assembled against the current unrelated `site` branch by **Check documentation site compatibility**. Pull-request runs use the proposed merge commit and never deploy.

The same non-deploying check can be started manually to detect drift. GitHub schedules workflows only from the repository default branch, which is `site`, so this `skill`-branch workflow does not claim a weekly scheduled run. No workflow on `skill` deploys GitHub Pages.

The `site`, `skill`, `policy`, and `webapp` histories remain unrelated. Do not merge, rebase, or cherry-pick across them. Cross-branch integration uses reviewed full commit SHAs and publication contracts.

## Pull requests

Describe:

- whether each changed path is source-only, distribution-owned, or a projected validator;
- the selected profile tags and behavior affected;
- the source-of-truth contracts changed;
- runtime, dependency, security, permission, lifecycle, portability, or deployment impact;
- positive, negative, clean-room, installation, and publication validation executed;
- modes explicitly unsupported by the change; and
- any required follow-up on the unrelated `site` branch.

Before merge, require all applicable source, distribution, profile, portable-consumption, and build-only site compatibility checks to pass and leave no unresolved review thread.
