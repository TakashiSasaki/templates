# Skill template source and distribution boundary

## Decision

The `skill` branch is the development source for a reusable, language-neutral Agent Skill template. After this migration, the branch root will no longer be an installable Skill directory.

The branch owns three distinct artifacts:

1. **Template source artifact** — the complete `skill` branch checkout used by template maintainers. It contains the copyable template, source-only validators, fixtures, publication integration, compatibility checks, audits, and maintenance documentation.
2. **Template distribution artifact** — the contents of the future `template/` directory, copied without content transformation to the root of a new Skill repository or an installed Skill directory.
3. **Concrete Skill artifact** — a Skill developed from the distribution after its identity, workflow, selected profiles, operational resources, implementation, tests, runtime decisions, interfaces, and license are completed.

These identities are not interchangeable. Source-repository validation does not prove that the downstream distribution is closed, and a concrete Skill must not inherit template-maintainer concerns merely because they exist in the same branch history.

This document defines the target boundary before physical file movement. Until the structural migration is merged, the current branch root remains the pre-separation scaffold described by the existing operational documentation.

## Required invariant

Let `S` be the complete source artifact, `D` the copyable template distribution, and `M` the maintainer-only source content. The target structure satisfies:

```text
S = D union M
D intersection M = empty
```

The notation describes ownership rather than Git object identity. Source documentation may describe both sets, but every distributed path must have a downstream purpose and no distributed file may require a maintainer-only sibling.

## Copy contract

The supported direct-copy operation will be:

```sh
mkdir -p /path/to/new-skill
cp -a template/. /path/to/new-skill/
```

The copied bytes, file modes, hidden entries, and relative paths are authoritative. An archive or other packaging mechanism may preserve the same tree, but it must not rewrite file contents, rename paths, substitute placeholders, select profiles automatically, or silently omit files from `template/`.

The copy destination, not the `skill` branch root, becomes the Skill root. `SKILL.md` must therefore be directly under the copy destination rather than under a retained `template/` wrapper.

## Profile model

The distribution remains one profile-aware scaffold. It is not replaced by separate mutually exclusive directories such as `templates/mcp-enabled/` or `templates/packaged-cli/`.

The existing profile semantics remain authoritative:

- `template-scaffold` identifies only the uncustomized template;
- `instruction-only` is the sole exclusive concrete profile;
- `knowledge-augmented`, `asset-driven`, `script-assisted`, `packaged-cli`, `mcp-enabled`, `browser-interface`, and `headless-service` remain selectively composable;
- combined profiles retain the union of their required contracts;
- unsupported optional contracts and resources are pruned by the template consumer after copying the complete distribution.

The migration changes artifact ownership and physical location. It does not reduce the supported profiles, convert them into a maturity ladder, or make one runtime or implementation language mandatory.

## Distribution requirements

The future `template/` tree must satisfy all of the following:

- it is a closed Skill repository root;
- `SKILL.md` is directly present at that root;
- no required relative reference escapes `template/`;
- the initial Skill remains in explicit `template-scaffold` mode;
- all eight concrete profile tags and their composition rules remain representable;
- the copied contract templates, resource directories, instructions, examples, and validation guidance work without source-maintainer siblings;
- source publication catalogs, publication-maintenance instructions, canonical fixtures, negative fixtures, source-only workflows, review guidance, and template-maintainer tests are absent;
- a consumer can replace the template identity, select profiles, prune unsupported material, choose a license, and validate the resulting concrete Skill;
- source validation treats `template/` as a separate input rather than continuing to copy the complete branch root and delete maintainer files afterward.

## Target layout

The intended source layout is:

```text
/
├── .github/                       # GitHub-specific source-maintainer CI and review policy
├── README.md                      # template-product source overview
├── AGENTS.md                      # source-maintainer agent instructions
├── CONTRIBUTING.md                # source-maintainer contribution policy
├── CHANGELOG.md                   # template-product history
├── LICENSE                        # template-product source license
├── docs/                          # source architecture and publication interface
├── template/                      # directly copyable profile-aware Skill template
└── maintainer/                    # source-only fixtures, validators, tests, libraries, and audits
```

The intended distribution shape is:

```text
template/
├── .editorconfig
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

## Current-tree classification

`docs/architecture/distribution-classification.json` classifies every current top-level entry as one of:

- `distribution`: the complete entry is intended to move under `template/`;
- `split`: the entry contains both downstream and source-maintainer responsibilities and must be divided or independently rewritten;
- `maintainer`: the complete entry remains outside the copyable distribution.

The classification is transitional rather than the final distribution manifest. Its purpose is to ensure that every existing and newly added top-level entry receives exactly one ownership decision before structural movement begins.

The principal split points are:

- `.editorconfig` and `.gitignore`: both source and copied repositories need independently owned versions;
- `README.md`: the branch-root template-product overview and copied Skill-development overview become separate documents;
- `AGENTS.md`: source-maintainer instructions and concrete-Skill development instructions become separate authorities;
- `CONTRIBUTING.md`: canonical-template contribution rules are separated from any downstream contribution guidance;
- `LICENSE`: the source artifact retains its license while the distribution carries its initial concrete-Skill license choice;
- `docs/`: profile, runtime, transport, and consumer guidance is separated from publication, source architecture, audits, and maintenance material.

`.github/` is classified as maintainer-owned in the current model. A later downstream CI workflow may be added deliberately under `template/.github/`, but source workflows and fixtures must not be copied merely because they currently live under `.github/`.

## Conformance strategy

After physical separation, source CI must validate three independent states:

1. the complete source checkout, including maintainer-only contracts and publication integration;
2. a clean copy of `template/`, executed as a Skill root without access to source siblings; and
3. representative concrete Skills produced from that copy, including minimal, executable, combined-profile, and negative cases.

Existing profile fixtures remain source-owned evidence. They are not automatically promoted to consumer templates because many intentionally select concrete runtimes, contain complete example implementations, exercise deployment variants, or represent invalid combinations.

The current adoption and installation suites must be converted from “copy the branch root and prune maintainer content” to “copy `template/.` and then perform only consumer-owned customization and pruning.” Clone, submodule, and archive equivalence continue to apply to completed concrete Skills rather than to the complete template source repository.

## Publication boundary

`docs/publication-catalog.json` remains owned by the template source artifact because it is an interface to the unrelated `site` branch. It may publish explanatory distribution documents and selected files below `template/`, but the catalog itself is not part of the copyable template.

Stable publication document IDs should be preserved when canonical sources move below `template/`. The `site` branch continues to lock a reviewed full commit SHA and owns navigation, generated destinations, assembly, provenance, and deployment.

GitHub Pages deployment is suspended while this migration is incomplete. The unrelated `site` history will be updated only after the final reviewed `skill` merge commit is available and the integrated build can distinguish the complete source tree from the copyable template tree.

## Completion criteria

The migration is complete only when:

- the branch root is unambiguously the template-product source artifact;
- `template/` can be copied byte-for-byte to an empty Skill root;
- `SKILL.md` is directly under the copied root;
- every required copied reference resolves inside the copied tree;
- the existing profile tags and composition semantics are preserved;
- no maintainer-only artifact is present in the copied tree;
- source CI validates source, distribution, and representative concrete Skills independently;
- adoption and generated-Skill tests begin from the distribution;
- publication paths are updated without broadening the public allowlist;
- the final reviewed `skill` merge commit is integrated into `site` by full SHA; and
- Pages deployment is restored only by a separate reviewed `site` change.
