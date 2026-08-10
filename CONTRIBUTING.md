# Contributing to the Skill template product

## Repository boundary

The `skill` branch root is the source repository for the template product. It is not an installable Skill directory.

The consumer-facing artifact and its sole canonical source tree are `template/`. Copy its contents into a new Skill root:

```sh
mkdir -p /path/to/new-skill
cp -a template/. /path/to/new-skill/
```

Do not add `SKILL.md`, runtime/interface contracts, resource placeholders, or downstream validator implementations back to the branch root. Consumer-facing Skill content is maintained under `template/` only.

Before changing a path, classify it as:

- **source-only maintenance material**, outside `template/`; or
- **distribution-owned content**, canonically maintained under `template/`.

There is no source-to-template validator projection class. Source-maintainer tests and CI consume downstream validators directly from their canonical paths below `template/.github/scripts/`.

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
2. keep the path listed under `distribution_files` in `distribution-manifest.json`;
3. do not create a byte-identical implementation authority outside `template/`;
4. ensure every required relative reference resolves within `template/`; and
5. validate both the source checkout and a copied Skill root.

For a downstream validator, edit only its canonical implementation under `template/.github/scripts/`. Source-only parity and regression harnesses may import or invoke that file by path, but must not copy its implementation back into `.github/scripts/`.

For source-only content, do not add a copy under `template/` merely to make the source and distribution trees look similar.

`distribution-manifest.json` must reject missing files, undeclared files, symbolic links, maintainer-only leakage, path traversal, content transformation, top-level shape drift, and any reintroduction of alternate root authorities for distributed validators.

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

Profile changes require synchronized contract templates, validators, positive fixtures, negative fixtures, consumer documentation, and publication sources. Add a combined fixture only when it proves an interaction that independent profile fixtures and contract validation cannot establish. Keep adapters thin only when multiple interfaces actually exist. Keep lifecycle ownership outside domain operations and caller protocols.

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
(cd template && python .github/scripts/validate_profile_contracts.py)
```

This command runs from the canonical downstream root; the source checkout does not maintain a second Python implementation copy.

Run complete repository validation against the copyable Skill root:

```sh
python template/.github/scripts/validate_skill_repository.py template
python template/.github/scripts/test_template_baseline.py
```

Run clean-room adoption and installation:

```sh
ruby .github/scripts/test-copyable-template-consumption.rb
```

The explicit-root Python validator resolves every contract and operational resource relative to the supplied Skill root rather than the caller's working directory and runs without requiring a second source-side implementation copy.

## Fixture baseline

Reduced fixtures under `.github/fixtures/profiles/` cover instruction, knowledge, assets, private helpers, optional runtime records, packaged CLI, a representative MCP `2026-07-28` Modern implementation, browser behavior, headless service behavior, combined resource profiles, and intentionally unsupported combinations.

The executable application fixtures select concrete runtimes only to establish their specific claims. They do not make one language, package manager, MCP transport, or deployment topology mandatory for the language-neutral template. The representative MCP fixture is intentionally Modern stdio-only; Streamable HTTP remains a conditional template capability rather than an unproven fixture claim.

The clean-room harness copies `template/.` into a path containing spaces and Japanese characters, verifies the copied inventory and modes, injects source-owned regression engines only into that temporary test copy, and exercises instruction-only, script-assisted, clone, submodule, flattened archive, vendoring, non-mutating consumption, and path safety. The canonical `template/` tree must remain unchanged.

This fixture matrix is the stable baseline for the current profile model. A new protocol revision, transport, trust boundary, deployment topology, persistence layer, service manager, distribution service, or release mechanism requires an explicit contract and proportionate executable evidence.

## Documentation publication compatibility

The `skill` branch owns stable publication document IDs and canonical source paths in `docs/publication-catalog.json`. Consumer documents resolve below `template/`; the source-product overview remains root `README.md`.

Pull requests that change `README.md`, `docs/**`, `template/**`, or the compatibility workflow are assembled against the current unrelated `site` branch by **Check documentation site compatibility**. Pull-request runs use the proposed merge commit and never deploy.

The same non-deploying check can be started manually to detect drift. GitHub schedules workflows only from the repository default branch, which is `site`, so this `skill`-branch workflow does not claim a weekly scheduled run. No workflow on `skill` deploys GitHub Pages.

The `site`, `skill`, `policy`, and `webapp` histories remain unrelated. Do not merge, rebase, or cherry-pick across them. Cross-branch integration uses reviewed full commit SHAs and publication contracts.

## Pull requests

Describe:

- whether each changed path is source-only or distribution-owned;
- the selected profile tags and behavior affected;
- the source-of-truth contracts changed;
- runtime, dependency, security, permission, lifecycle, portability, or deployment impact;
- positive, negative, clean-room, installation, and publication validation executed;
- modes explicitly unsupported by the change; and
- any required follow-up on the unrelated `site` branch.

Before merge, require all applicable source, distribution, profile, portable-consumption, and build-only site compatibility checks to pass and leave no unresolved review thread.
