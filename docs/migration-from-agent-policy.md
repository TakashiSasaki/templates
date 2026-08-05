# Migration from the former agent-policy repository

## Source boundary

The initial `policy` branch history was imported on 2026-08-01 JST from:

- source repository: `TakashiSasaki/agent-policy`;
- source branch: `main`;
- verified source head: `22ac788d456bf0d9904e1d23492b01296de167a1`;
- target repository: `TakashiSasaki/templates`;
- target branch: `policy`.

The source head was verified before the import. The old repository remains the historical authority for its original commit identifiers until it is archived.

## Import method

Git history was imported rather than copying only the source tree. Before pushing the history into `TakashiSasaki/templates`, `.github/workflows` was removed from every imported revision and commits made empty by that filter were pruned.

This filtering was deliberate:

- workflow triggers and permissions were written for the former repository and branches;
- documentation deployment depended on former repository settings;
- importing those workflows unchanged could run automation with incorrect targets or permissions;
- branch-appropriate CI and publication workflows require explicit review in the target repository.

Because the trees were rewritten, imported commit SHAs are not expected to equal the original SHAs. Non-workflow file contents, authorship, commit messages, dates, and ancestry were retained except where workflow-only commits became empty and were pruned.

## Included in the initial import

The import included the former `main` history for:

- policy sources and profiles;
- compiler, renderer, validation, and adoption code;
- schemas and templates;
- generated-skill sources;
- tests, documentation, and supporting scripts;
- package and command compatibility under the existing `agent-policy` name.

The initial import did not transfer the former orphan `bootstrap-agent-policy` branch, workflow history, tags, releases, issues, pull requests, repository settings, secrets, or other unrelated branches.

## Migration progress

Completed work:

1. Established branch-appropriate `Policy CI`.
2. Defined and tested the application-type-independent shared-policy boundary.
3. Removed the built-in application-specific profile and its application-architecture rules.
4. Migrated generated manifests, adoption state, schemas, and consumer workflow templates from `TakashiSasaki/agent-policy` to `TakashiSasaki/templates`.
5. Reviewed and integrated the bootstrap trust seed at `skills/bootstrap-agent-policy/`.
6. Initially pinned the integrated bootstrap to the reviewed repository-identity migration commit that preceded the bootstrap package, avoiding recursive self-reference.
7. Added `release/toolchain.json`, its JSON Schema, and a release-state verifier so later stable pins are promoted through a defined candidate and promotion lifecycle.
8. Restored a branch-appropriate strict documentation build for `templates:policy` without importing the former workflow history or fetching unrelated branches. The retained Pages artifact-upload and deployment paths are intentionally disabled.

The stable pin is now read from `release/toolchain.json` rather than repeated in migration prose. The bootstrap manifest must match that descriptor exactly, and Policy CI verifies the pin against the reviewed `policy` source history.

The old orphan branch was not merged into the new history. Its relevant source files were reviewed and adapted to the new repository, path layout, pin, route boundary, and documentation model.

## Remaining migration work

Branch-local toolkit completion and ecosystem migration completion are separate tracks. Their
criteria and sequencing are defined in `policy-readiness.md`.

1. Identify and update consumer repositories that still pin `TakashiSasaki/agent-policy` or a
   rewritten pre-migration SHA.
2. When selected policy documentation should appear on the repository site, coordinate catalog
   and navigation changes through the unrelated `skill` and `site` branches. The `policy`
   workflow remains build-only.
3. Add a deprecation notice to `TakashiSasaki/agent-policy` and stop active automation there.
4. Archive the former repository only after all active consumers have migrated.

The former repository must not be deleted during migration because existing full-SHA pins and
historical links depend on its objects remaining addressable.
