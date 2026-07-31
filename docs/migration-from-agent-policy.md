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

- workflow triggers and permissions were written for the former repository and its `main` and `bootstrap-agent-policy` branches;
- documentation deployment depended on branch and repository settings that do not yet exist for `templates:policy`;
- importing those workflows unchanged could run repository-specific automation with incorrect targets or permissions;
- branch-appropriate CI and documentation workflows must be reviewed and rebuilt in the target repository.

Because the trees were rewritten, imported commit SHAs are not expected to equal the original SHAs. Non-workflow file contents, authorship, commit messages, dates, and ancestry were retained except where workflow-only commits became empty and were pruned.

## Included

The import includes the `main` branch history for:

- policy sources and profiles;
- compiler, renderer, validation, and adoption code;
- schemas and templates;
- generated-skill sources;
- tests, documentation, and supporting scripts;
- package and command compatibility under the existing `agent-policy` name.

## Not included

The import did not transfer:

- `.github/workflows` history;
- the `bootstrap-agent-policy` branch;
- tags and releases;
- issues, pull requests, discussions, or review history;
- repository secrets, variables, environments, Pages settings, branch protection, webhooks, or installed-app settings;
- unrelated source branches.

These items require explicit review rather than implicit repository copying.

## Follow-up sequence

1. Restore branch-appropriate CI for `templates:policy`.
2. Define and test the application-type-independent policy scope.
3. Remove or relocate application-specific profiles and rules.
4. Consolidate the bootstrap skill into the `policy` branch or define another explicit retained boundary.
5. Update consumers to use `TakashiSasaki/templates` and a full commit SHA from `policy`.
6. Restore documentation publication from the new source.
7. Add a deprecation notice to `TakashiSasaki/agent-policy`, stop active automation there, and archive it after all consumers have migrated.

The former repository must not be deleted during migration because existing full-SHA pins and historical links depend on its objects remaining addressable.
