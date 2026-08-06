# Agent Skill template source repository

This `skill` branch develops and validates a reusable, language-neutral Agent Skill template. The branch root is the template product’s source repository; it is not the directory users should install as a Skill.

## Copyable template

The canonical copyable artifact is `template/`. Copy its contents, including hidden files, into an empty destination:

```sh
mkdir -p /path/to/new-skill
cp -a template/. /path/to/new-skill/
```

After copying, the destination root is the installable Skill directory and contains `SKILL.md` directly. Do not retain a `template/` wrapper in the destination.

The distribution is byte-preserving. Copying does not rewrite placeholders, choose profiles, rename paths, select a runtime, or choose a license. Those decisions belong to the developer of the concrete Skill.

## Profile model

The template remains one profile-aware scaffold rather than a collection of mutually exclusive profile directories.

- `template-scaffold` identifies only the uncustomized template.
- `instruction-only` is the sole exclusive concrete profile.
- `knowledge-augmented`, `asset-driven`, `script-assisted`, `packaged-cli`, `mcp-enabled`, `browser-interface`, and `headless-service` remain selectively composable.
- Combined profiles retain the union of their required contracts.
- A concrete Skill removes unsupported optional contracts and resources after copying.

See `template/docs/skill-profiles.md` and `template/docs/profile-contract-map.md` for the consumer-facing rules.

## Repository areas

- `template/`: copyable Skill-development template and concrete-Skill validators;
- `distribution-manifest.json`: exact source-to-distribution inventory and byte-preserving mirror contract;
- `.github/scripts/`: source validators, canonical fixtures, adoption tests, publication checks, and distribution checks;
- `.github/fixtures/`: positive, combined-profile, deployment-variant, and negative concrete-Skill evidence;
- `.github/workflows/`: source-repository CI and build-only documentation compatibility checks;
- `docs/architecture/`: template-product architecture, distribution boundary, and migration records;
- `docs/publication-catalog.json`: stable public-document interface consumed by the unrelated `site` branch;
- `CHANGELOG.md`, `CONTRIBUTING.md`, and root `AGENTS.md`: template-product maintenance material.

Some root-level contract and resource files remain as byte-authoritative source mirrors during the staged migration. They are inputs to `template/` under `distribution-manifest.json`, not a supported installable Skill root. Later migration phases will reduce or relocate those mirrors after every adoption and installation suite consumes `template/` directly.

## Validation

Run the source boundary and copyable-distribution checks:

```sh
ruby .github/scripts/test-distribution-boundary.rb
ruby .github/scripts/test-skill-distribution.rb
ruby .github/scripts/validate-skill-distribution.rb
```

Validate the uncustomized copyable Skill root independently:

```sh
ruby .github/scripts/validate-skill-repository.rb template
ruby template/.github/scripts/test-template-baseline.rb
```

The complete source CI additionally validates all supported profile contracts, concrete fixtures, negative fixtures, portable paths, adoption, clone, submodule, archive, and parent-owned vendoring behavior.

## Publication and deployment

The `skill` branch owns stable publication document IDs and source paths. The unrelated `site` branch owns navigation, full-SHA source locking, assembly, provenance, and GitHub Pages deployment.

Pages deployment is suspended during this restructuring. Skill pull requests continue to invoke the build-only site compatibility workflow. After the final reviewed Skill merge commit, `site` will lock that full SHA, publish separate complete-source and copyable-template views, pass strict build validation, and restore deployment only in a separate reviewed pull request.

## Development constraints

- Do not merge, rebase, or cherry-pick unrelated `site`, `policy`, or `webapp` history into `skill`.
- Preserve the eight profile tags and their composition semantics.
- Keep concrete-Skill validators in the distribution only when they operate without source-maintainer siblings.
- Keep fixtures, publication integration, source audits, and template-maintainer tests outside `template/`.
- Change mirrored source and distribution bytes together; the distribution validator rejects drift, undeclared files, mode changes, symlinks, and maintainer-only leakage.
- Treat `template/` as the user-facing artifact and the complete branch as its source and conformance system.
