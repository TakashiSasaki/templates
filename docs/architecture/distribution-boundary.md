# Skill template source and distribution boundary

## Decision

The `skill` branch is the source repository for a reusable, language-neutral Agent Skill template product. The branch root is not an installable Skill directory. The copyable distribution is `template/`.

The branch owns three distinct artifacts:

1. **Template source artifact** — the complete `skill` checkout used by template maintainers. It contains the copyable template, source-only validators, fixtures, publication integration, compatibility checks, audits, and maintenance documentation.
2. **Template distribution artifact** — the contents of `template/`, copied without content transformation to the root of a new Skill repository or an installed Skill directory.
3. **Concrete Skill artifact** — a Skill developed from the distribution after its identity, workflow, selected profiles, operational resources, implementation, tests, runtime decisions, interfaces, and license are completed.

The structural separation is complete. These artifact identities are not interchangeable. Source-repository validation does not by itself prove that the distribution is closed, and a concrete Skill must not inherit template-maintainer concerns merely because they exist in the same branch history.

## Required invariant

Let `S` be the complete source artifact, `D` the copyable distribution, and `M` the maintainer-only source content. Ownership satisfies:

```text
S = D union M
D intersection M = empty
```

The notation describes responsibility, not Git object identity. Source documentation may describe both sets, but every distributed path has a downstream purpose and no distributed file requires a maintainer-only sibling.

The source repository may project a bounded validator implementation into the distribution. Each projection is declared in `distribution-manifest.json` and must preserve path-relative behavior, bytes, and Git-significant mode. The source implementation remains maintainer-owned; the projected copy is usable from a concrete Skill root without the source checkout.

## Copy contract

The supported direct-copy operation is:

```sh
mkdir -p /path/to/new-skill
cp -a template/. /path/to/new-skill/
```

The copied bytes, file modes, hidden entries, and relative paths are authoritative. An archive or another packaging mechanism may preserve the same tree, but it must not rewrite file contents, rename paths, substitute placeholders, select profiles automatically, choose a runtime, choose a license, or silently omit files from `template/`.

The destination becomes the Skill root. `SKILL.md` is directly under that destination and no `template/` wrapper remains.

## Profile model

The distribution is one profile-aware scaffold. It is not a set of mutually exclusive directories such as `templates/mcp-enabled/` or `templates/packaged-cli/`.

The profile semantics are:

- `template-scaffold` identifies only the uncustomized template;
- `instruction-only` is the sole exclusive concrete profile;
- `knowledge-augmented`, `asset-driven`, `script-assisted`, `packaged-cli`, `mcp-enabled`, `browser-interface`, and `headless-service` are selectively composable;
- combined profiles retain the union of their required contracts;
- unsupported optional contracts and resources are pruned by the template consumer after copying the complete distribution.

Artifact separation does not reduce supported profiles, convert them into a maturity ladder, or make one runtime or implementation language mandatory.

## Source layout

```text
/
├── .github/                       # source CI, validators, fixtures, and review policy
├── README.md                      # template-product source overview
├── AGENTS.md                      # source-maintainer agent instructions
├── CONTRIBUTING.md                # source-maintainer contribution policy
├── CHANGELOG.md                   # template-product history
├── LICENSE                        # template-product source license
├── distribution-manifest.json     # exact distribution inventory and projections
├── docs/                          # source architecture and publication interface
├── maintainer/                    # source-maintainer ownership documentation
└── template/                      # directly copyable profile-aware Skill template
```

The branch root deliberately has no `SKILL.md`, runtime contract, interface contract, operational resource directory, or concrete-Skill placeholder. Those authorities exist only under `template/`.

GitHub-specific maintainer implementation stays under `.github/`. The `maintainer/` directory documents ownership and can hold future source-only utilities that do not belong to GitHub-specific integration. It is not necessary to relocate workflows or fixtures merely to make the source tree visually uniform.

## Distribution layout

```text
template/
├── .editorconfig
├── .github/
│   ├── scripts/                  # concrete-Skill validators and template baseline check
│   └── workflows/                # bounded concrete-Skill validation workflow
├── .gitignore
├── README.md
├── AGENTS.md
├── SKILL.md
├── RUNTIME.md
├── INTERFACES.md
├── CLI_INTERFACE.md
├── MCP_INTERFACE.md
├── WEB_INTERFACE.md
├── LICENSE
├── LICENSE.template
├── assets/
├── examples/
├── mcp/
├── references/
├── scripts/
├── src/
├── tests/
└── docs/
```

Optional files remain optional for a completed Skill. Their presence in the uncustomized distribution provides profile-aware starting material; it does not authorize a concrete Skill to retain unsupported contracts.

## Distribution manifest

`distribution-manifest.json` is the closed inventory for `template/`. It records:

- the source root and direct-copy destination;
- the prohibition on content transformation;
- the required top-level entries;
- bounded validator projections from source-maintainer implementations;
- files directly owned by the distribution; and
- source-only paths prohibited from the distribution.

Validation compares the tracked `template/` inventory with the manifest, rejects missing or undeclared files, rejects symbolic links, rejects source-only leakage, checks the top-level shape, and verifies bytes and modes for every projected validator.

The manifest is source-maintainer material and is not copied into a concrete Skill.

## Ownership classification

`docs/architecture/distribution-classification.json` classifies every top-level source entry as:

- `distribution`: the complete consumer-facing artifact root;
- `maintainer`: source-only material outside the copyable artifact; or
- `split`: an unresolved mixed-ownership entry.

The completed layout has `template` as the sole `distribution` entry and an empty `split` set. Introducing a new top-level path requires an explicit source/distribution decision. Reintroducing a root-level Skill contract or resource directory is prohibited even if the classification file is edited at the same time.

## Conformance strategy

Source CI validates three independent states:

1. the complete source checkout, including maintainer-only contracts and publication integration;
2. a clean copy of `template/`, executed as a Skill root without access to source siblings; and
3. representative concrete Skills produced from that copy, including minimal, executable, combined-profile, deployment-variant, and negative cases.

Canonical profile fixtures remain source-owned evidence. They are not consumer templates because many select concrete runtimes, contain complete example implementations, exercise deployment variants, or intentionally represent invalid combinations.

Clean-room consumption copies `template/.` into a path containing spaces and non-ASCII characters, verifies the complete copied tree, and runs adoption plus clone, submodule, and archive installation engines from that isolated copy. The canonical `template/` tree must remain unchanged.

Clone, submodule, archive, and parent-owned vendoring equivalence apply to completed concrete Skills, not to the complete template source repository.

## Publication boundary

`docs/publication-catalog.json` remains owned by the source artifact because it is an interface to the unrelated `site` branch. Stable public document IDs remain unchanged. The source overview resolves to root `README.md`; consumer contracts and guidance resolve below `template/`.

The `site` branch owns navigation, reader-facing titles, generated destinations, full-SHA source locking, assembly, provenance, repository-tree rendering, and GitHub Pages deployment. `skill` workflows call only the build-only compatibility workflow with contents-read permission.

GitHub Pages deployment remains suspended until the unrelated `site` branch locks the final reviewed `skill` merge commit, publishes separate complete-source and copyable-template views, and passes strict integration validation. Deployment restoration is a separate reviewed `site` change.

## Maintainer change rules

Before editing a path, classify it as:

- source-only;
- distribution-owned; or
- a projected validator.

A distribution-owned file is edited only under `template/`. A projected validator is updated in both declared locations with identical bytes and mode. A source-only file is never copied into `template/` merely to make the two trees resemble one another.

Profile changes update the applicable template contracts, validators, positive fixtures, combined fixtures, negative fixtures, consumer documentation, and publication sources. Deployment or trust-boundary changes require proportionate executable evidence.

## Completion criteria

The restructuring is complete because:

- the branch root is unambiguously the template-product source artifact;
- `template/` copies byte-for-byte to an empty Skill root;
- `SKILL.md` is directly under the copied root;
- every required copied reference resolves inside the copied tree;
- all eight profile tags and their composition semantics are preserved;
- no maintainer-only artifact is present in the copied tree;
- source CI validates source, distribution, and representative concrete Skills independently;
- adoption and installation tests begin from a clean copy of `template/`;
- publication IDs are stable and canonical consumer sources resolve below `template/`; and
- a dedicated completion audit rejects regression to the former mixed root.

Cross-branch publication is complete only after the final reviewed `skill` merge commit is integrated into `site` by full SHA and Pages deployment is restored by a separate `site` pull request.
