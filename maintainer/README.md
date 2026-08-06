# Template maintainer boundary

This directory documents the source-only maintenance boundary of the `skill` branch. It is not part of the copyable Agent Skill template.

## Artifact ownership

The branch owns three distinct artifacts:

1. the complete source checkout used to maintain the template product;
2. the copyable `template/` directory; and
3. a concrete Skill developed from a copy of `template/.`.

The complete source checkout includes GitHub workflows, canonical fixtures, negative fixtures, publication integration, distribution validation, clean-room adoption tests, and architecture records. None of those source concerns becomes an operational Skill resource merely because it is stored in the same branch.

## Physical ownership

Source-maintainer implementation remains in the locations appropriate to its execution boundary:

- `.github/workflows/`: source CI and build-only documentation compatibility;
- `.github/scripts/`: source validators, fixture tests, distribution tests, and clean-room consumption tests;
- `.github/fixtures/`: positive, combined, deployment-variant, and intentionally invalid concrete-Skill evidence;
- `docs/architecture/`: source architecture and distribution decisions;
- `docs/publication-catalog.json`: the stable publication interface consumed by `site`;
- `docs/publication-maintenance.md`: the cross-branch publication process;
- `distribution-manifest.json`: the exact copyable inventory and validator-projection contract;
- `maintainer/`: source-maintainer ownership documentation and future source-only utilities that do not belong under `.github/`.

Do not move GitHub-specific workflows out of `.github/` solely to make the source tree visually uniform. Do not place source-only fixtures or publication machinery under `template/`.

## Copyable artifact

The consumer-facing artifact is only `template/`:

```sh
mkdir -p /path/to/new-skill
cp -a template/. /path/to/new-skill/
```

The destination root becomes the Skill root and contains `SKILL.md` directly. The copy operation preserves bytes, paths, hidden entries, and Git-significant modes. It does not choose profiles, select a runtime, replace placeholders, or choose a license.

## Change classification

Before changing a path, classify it as one of:

- **source-only**: used to maintain, test, publish, or audit the template product;
- **distribution-owned**: canonically maintained under `template/`;
- **projected validator**: implemented under `.github/scripts/` and copied byte-for-byte to `template/.github/scripts/` because concrete Skills need it.

Source-only files must not leak into `template/`. Distribution-owned files must not acquire a second root-level authority. Projected validators must remain byte- and mode-identical on both sides of the projection declared by `distribution-manifest.json`.

## Completion checks

Source changes are complete only after:

- source/distribution classification passes;
- the complete distribution manifest passes;
- `template/` validates as an independent Skill root;
- clean-room adoption and installation start from `template/.`;
- affected positive and negative fixtures pass;
- Ubuntu, macOS, and Windows portable consumption pass when the boundary is affected;
- the publication catalog resolves every declared source;
- the build-only `site` compatibility workflow passes; and
- no source-only file or obsolete root Skill authority is reintroduced.
