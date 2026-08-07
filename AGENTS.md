# Repository instructions

## Repository identity

This branch is the source repository for a reusable Agent Skill template product. The repository root is not an installable Skill directory.

The user-facing artifact is `template/`. Its contents are copied directly to a new Skill root:

```sh
cp -a template/. /path/to/new-skill/
```

The destination, not the source checkout, must contain `SKILL.md` directly at its root.

## Artifact boundary

Treat these as distinct artifacts:

1. the complete source checkout;
2. the copyable `template/` distribution; and
3. a concrete Skill developed from that distribution.

Consumer-facing Skill contracts, profile documentation, operational resource placeholders, and concrete-Skill instructions exist only under `template/`. Do not recreate root-level `SKILL.md`, runtime/interface contracts, or resource directories as alternate authorities.

Source-only fixtures, negative cases, publication integration, review policy, migration audits, and canonical adoption tests remain outside `template/`. Concrete-Skill validators may be distributed only when they operate from the copied Skill root without requiring source-maintainer siblings.

`distribution-manifest.json` is authoritative for the exact copyable inventory. Validator implementations projected from `.github/scripts/` into `template/.github/scripts/` must retain identical bytes and Git-significant modes. All other template files are directly owned below `template/`.

## Profile invariants

The distribution is one profile-aware scaffold, not a directory per profile.

- `template-scaffold` is reserved for the uncustomized template.
- `instruction-only` is the sole exclusive profile.
- `knowledge-augmented`, `asset-driven`, `script-assisted`, `packaged-cli`, `mcp-enabled`, `browser-interface`, and `headless-service` are selectively composable.
- A combination retains the union of its required contracts.
- Do not impose a runtime, CLI, MCP, browser, service, or deployment layer on a Skill that does not need it.

Changes to profile semantics require synchronized updates to the template contracts, validators, positive fixtures, combined fixtures, negative fixtures, consumer documentation, distribution manifest where applicable, and publication material.

## Reading order

Always read:

- this file;
- `README.md`;
- `docs/architecture/distribution-boundary.md`;
- `docs/architecture/distribution-classification.json`;
- files directly named by the task.

Read additionally when applicable:

- distribution inventory: `distribution-manifest.json` and `.github/scripts/validate-skill-distribution.rb`;
- consumer contract changes: the corresponding files under `template/`;
- profile changes: `template/docs/skill-profiles.md`, `template/docs/profile-contract-map.md`, and profile validators;
- runtime or interface changes: the applicable template contracts and fixture implementations;
- publication changes: `docs/publication-catalog.json` and `docs/publication-maintenance.md`;
- site compatibility changes: `.github/workflows/pages.yml` and the unrelated `site` contract, without importing its history;
- adoption or installation changes: `.github/scripts/test-copyable-template-consumption.rb` and its source-owned engines.

Do not load advanced MCP, browser, or service material for unrelated changes.

## Source versus distribution changes

For a consumer-owned file, change the file below `template/` and keep it listed under `distribution_owned_files`. Do not add a root-level duplicate.

For a projected validator:

1. change the source implementation under `.github/scripts/`;
2. update the corresponding file below `template/.github/scripts/` to identical bytes and mode;
3. run distribution validation;
4. run the copied Skill validator; and
5. run profile-specific regression tests.

For a source-only file, do not add it to `template/` merely to make the trees look similar.

## Validation

At minimum, run:

```sh
ruby .github/scripts/test-distribution-boundary.rb
ruby .github/scripts/test-skill-distribution.rb
ruby .github/scripts/validate-skill-distribution.rb
python .github/scripts/validate_skill_repository.py template
python template/.github/scripts/test_template_baseline.py
ruby .github/scripts/test-copyable-template-consumption.rb
```

The Python validation host requires Python 3.12 or newer, PyYAML 6.0.3, and Git. Then run all tests proportionate to the affected profiles and source boundaries. Networked or executable profile changes require real fixture and negative-path evidence, not only Markdown checks.

The distribution must reject:

- untracked or undeclared copied files;
- missing declared files;
- validator projection byte or mode drift;
- symbolic links and Git links where prohibited;
- path traversal or `.git` components;
- maintainer-only leakage;
- automatic content transformation;
- profile reduction or accidental exclusivity changes; and
- dependence on the source checkout at runtime or validation time.

The source boundary must reject reintroduction of consumer-facing Skill files at the branch root.

## Publication and branch boundaries

`skill`, `site`, `policy`, and `webapp` have unrelated histories. Do not merge, rebase, or cherry-pick across them.

The `skill` branch owns its publication catalog and stable document IDs. Public consumer documents resolve below `template/`. The `site` branch consumes a reviewed full commit SHA and owns navigation, assembly, provenance, repository-tree rendering, and deployment. Keep Pages compatibility build-only from provider branches.

GitHub Pages deployment is suspended during this migration. Do not restore it from `skill`; restoration belongs to a separate reviewed `site` pull request after final integration.

## Completion criteria

Before reporting a source change complete:

1. confirm the source/distribution ownership of every changed path;
2. preserve the profile model and contract ownership;
3. keep `template/` closed and directly copyable;
4. validate the complete distribution inventory and validator projections;
5. validate `template/` as an independent Skill root;
6. run affected fixture, adoption, installation, publication, and site-compatibility tests;
7. confirm no secrets or environment-specific credentials are committed;
8. confirm source-only files did not leak into the distribution;
9. confirm consumer-facing Skill files did not reappear at the source root;
10. confirm the PR is based on the current target-branch full SHA; and
11. leave no unresolved review thread before merge.
