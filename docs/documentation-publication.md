# Documentation publication

The `policy` branch builds this documentation through `.github/workflows/pages.yml`. GitHub Pages artifact upload and deployment are retained in the workflow but intentionally disabled.

## Current workflow boundary

Both pull requests targeting `policy` and pushes to `policy` install the exactly pinned documentation dependencies, regenerate repository previews and documentation assets, verify the documented tree, and run `mkdocs build --strict --clean`.

The Pages artifact-upload step and deployment job remain present for later use, but both are protected by a hard-coded false condition. Therefore no current `policy` event uploads a Pages artifact or deploys a site. Pull-request and push builds receive only `contents: read` unless the disabled deployment job is explicitly enabled by a reviewed change.

The workflow does not fetch `main`, `site`, `webapp`, the former orphan bootstrap branch, or the former `TakashiSasaki/agent-policy` repository. The repository default branch is `main`, while this workflow intentionally exists only in the unrelated `policy` history. GitHub manual dispatch requires the workflow file to exist on the default branch, so this workflow deliberately omits `workflow_dispatch`.

All third-party actions are pinned to full commit SHAs. Documentation dependencies are exactly pinned in `requirements-docs.txt`.

## Deployment enablement boundary

Do not enable Pages deployment as an incidental documentation or policy change. Enabling publication requires a dedicated reviewed change that:

1. removes the hard-coded false condition from both the Pages artifact-upload step and the deployment job while retaining the `policy` branch and non-pull-request guards;
2. confirms the repository Pages source and environment settings;
3. determines whether `agent-policy.moukaeritai.work` should be moved from the former repository;
4. runs and verifies the enabled deployment before describing publication as complete.

Until that change is approved and merged, Pages settings and custom-domain migration are deliberately deferred.

## Build verification

The currently enabled documentation build is successful only when all of the following pass:

- repository preview generation;
- documented-tree verification;
- documentation asset generation;
- build metadata generation;
- `mkdocs build --strict --clean`;
- regression tests confirming both deployment guards remain disabled.

A successful MkDocs build does not mean that documentation has been published. Publication remains incomplete while artifact upload and deployment are disabled.
