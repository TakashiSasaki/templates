# Agent Skill template source repository

This `skill` branch develops and validates a reusable, language-neutral Agent Skill template. The branch root is the template product’s source repository; it is not an installable Skill directory.

## Copyable template

The canonical user-facing artifact and its canonical source tree are `template/`. Copy its contents, including hidden files, into an empty destination:

```sh
mkdir -p /path/to/new-skill
cp -a template/. /path/to/new-skill/
```

After copying, the destination root is the installable Skill directory and contains `SKILL.md` directly. Do not retain a `template/` wrapper in the destination.

The distribution is byte-preserving. Copying does not rewrite placeholders, choose profiles, rename paths, select a runtime, or choose a license. Those decisions belong to the developer of the concrete Skill.

Consumer-facing files are authored under `template/` only. Source-maintainer CI and regression tests may consume validators and contracts directly from that canonical tree; they do not maintain byte-identical implementation projections at the branch root.

## Profile model

The template remains one profile-aware scaffold rather than a collection of mutually exclusive profile directories.

- `template-scaffold` identifies only the uncustomized template.
- `instruction-only` is the sole exclusive concrete profile.
- `knowledge-augmented`, `asset-driven`, `script-assisted`, `packaged-cli`, `mcp-enabled`, `browser-interface`, and `headless-service` remain selectively composable.
- Combined profiles retain the union of their required contracts.
- A concrete Skill removes unsupported optional contracts and resources after copying.

The consumer-facing contracts, profile definitions, resource placeholders, validators, and concrete-Skill validation guidance exist only under `template/`.

## Repository areas

- `template/`: the complete copyable Skill-development template and the sole canonical source of downstream-distributed content;
- `distribution-manifest.json`: the exact closed inventory of files canonically owned by `template/`;
- `.github/scripts/`: source-only distribution checks, canonical fixtures, clean-room adoption tests, publication checks, parity/regression harnesses, and other maintainer tooling;
- `.github/fixtures/`: positive, combined-profile, deployment-variant, and negative concrete-Skill evidence;
- `.github/workflows/`: source-repository CI and build-only documentation compatibility checks;
- `docs/architecture/`: template-product architecture and distribution-boundary records;
- `docs/publication-catalog.json`: stable public-document IDs and canonical sources consumed by the unrelated `site` branch;
- `docs/publication-maintenance.md`: cross-branch publication maintenance rules;
- `CHANGELOG.md`, `CONTRIBUTING.md`, root `AGENTS.md`, and root `LICENSE`: template-product maintenance material.

The branch root deliberately contains no `SKILL.md`, runtime contract, interface contract, operational resource directory, concrete-Skill placeholder, or alternate copy of a downstream validator implementation. Those files belong to `template/` alone.

## Validation

Run the source boundary and copyable-distribution checks:

```sh
ruby .github/scripts/test-distribution-boundary.rb
ruby .github/scripts/test-skill-distribution.rb
ruby .github/scripts/validate-skill-distribution.rb
```

Validate the uncustomized copyable Skill root independently with Python 3.12, PyYAML 6.0.3, and Git:

```sh
python template/.github/scripts/validate_skill_repository.py template
python template/.github/scripts/test_template_baseline.py
```

Validate adoption and installation from a source-independent copy with the authoritative Python harness:

```sh
python .github/scripts/test_copyable_template_consumption.py
```

The historical `ruby .github/scripts/test-copyable-template-consumption.rb` command remains only as a temporary compatibility shim for generated repository policy during the migration and delegates directly to the Python harness above.

The complete source CI additionally validates all supported profile contracts, concrete fixtures, negative fixtures, clone, submodule, archive, parent-owned vendoring, non-mutating consumption, and space/Unicode path behavior. Source-only parity and regression tests exercise the Python validators from their canonical locations below `template/.github/scripts/`.

## Publication and deployment

The `skill` branch owns stable publication document IDs and canonical repository-relative source paths. Public consumer contracts resolve below `template/`; the source overview remains `README.md`.

The unrelated `site` branch owns navigation, full-SHA source locking, assembly, provenance, repository-tree views, and GitHub Pages deployment. Skill pull requests continue to invoke the build-only site compatibility workflow.

Publishing a newer Skill revision requires a separate reviewed `site` change that locks the final reviewed Skill full SHA. No workflow on `skill` owns Pages deployment.

## Development constraints

- Do not merge, rebase, or cherry-pick unrelated `site`, `policy`, or `webapp` history into `skill`.
- Preserve the eight profile tags and their composition semantics.
- Do not reintroduce consumer-facing Skill contracts, validators, or resource placeholders at the branch root.
- Keep concrete-Skill validators canonical under `template/.github/scripts/` and independently usable without source-maintainer siblings.
- Keep fixtures, publication integration, source audits, review guidance, and template-maintainer tests outside `template/`.
- Treat `distribution-manifest.json` as a closed inventory of `template/`, not as a source-to-distribution projection map.
- Treat `template/` as both the user-facing artifact source tree and the complete branch’s downstream conformance target.
